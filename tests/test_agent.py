# Integration tests for news_agent/agent.py (Steps 6-7).

import os
import sqlite3
import tempfile

import pytest

import config
from news_agent.agent import run_monitoring_once
from news_agent.db import get_latest_run, init_db
from news_agent.models import ArticleInput, ClaudeResult


@pytest.fixture
def agent_env(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        failure_log = os.path.join(tmpdir, "failures.log")
        monkeypatch.setattr(config, "DATABASE_PATH", db_path)
        monkeypatch.setattr(config, "FAILURE_LOG_PATH", failure_log)
        monkeypatch.setattr(config, "RSS_FEEDS", ["https://example.com/feed.xml"])
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        init_db()
        yield {"db_path": db_path, "failure_log": failure_log}


@pytest.fixture
def multi_feed_env(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        failure_log = os.path.join(tmpdir, "failures.log")
        monkeypatch.setattr(config, "DATABASE_PATH", db_path)
        monkeypatch.setattr(config, "FAILURE_LOG_PATH", failure_log)
        monkeypatch.setattr(
            config,
            "RSS_FEEDS",
            [
                "https://example.com/bad-feed.xml",
                "https://example.com/good-feed.xml",
            ],
        )
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        init_db()
        yield {"db_path": db_path, "failure_log": failure_log}


def _sample_article(article_id: str = "article-1") -> ArticleInput:
    return ArticleInput(
        id=article_id,
        title="CAR-T trial update",
        url="https://example.com/car-t",
        guid=None,
        source="Test Feed",
        published_at="2026-06-01T12:00:00+00:00",
        content_excerpt="Trial results look promising.",
    )


def test_missing_api_key_records_failed_run_and_writes_failure_log(
    agent_env, monkeypatch
):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    run_id = run_monitoring_once()
    latest = get_latest_run()

    assert run_id == latest["id"]
    assert latest["status"] == "failed"
    assert "ANTHROPIC_API_KEY" in latest["error"]
    assert os.path.exists(agent_env["failure_log"])
    assert "ANTHROPIC_API_KEY" in open(agent_env["failure_log"], encoding="utf-8").read()


def test_run_stores_processed_and_low_relevance_articles(agent_env, monkeypatch):
    articles = [_sample_article("high"), _sample_article("low")]
    claude_calls = {"count": 0}

    def fake_parse_feed(feed_url, parsed_feed):
        return articles

    def fake_fetch_feed(feed_url):
        return {"feed": {"title": "Test Feed"}, "entries": []}

    def fake_call_claude(article, keywords):
        claude_calls["count"] += 1
        if article.id == "high":
            return ClaudeResult(summary="Highly relevant.", relevance_score=90)
        return ClaudeResult(summary="Not relevant enough.", relevance_score=10)

    monkeypatch.setattr("news_agent.agent.parse_feed", fake_parse_feed)
    monkeypatch.setattr("news_agent.agent.fetch_feed", fake_fetch_feed)
    monkeypatch.setattr("news_agent.agent.call_claude", fake_call_claude)

    run_monitoring_once()
    latest = get_latest_run()

    assert latest["status"] == "success"
    assert latest["articles_seen"] == 2
    assert latest["articles_new"] == 2
    assert claude_calls["count"] == 2

    conn = sqlite3.connect(agent_env["db_path"])
    rows = {
        row[0]: row
        for row in conn.execute(
            "SELECT id, status, summary, relevance_score FROM articles"
        ).fetchall()
    }
    conn.close()

    assert rows["high"][1] == "processed"
    assert rows["high"][2] == "Highly relevant."
    assert rows["low"][1] == "low_relevance"
    assert rows["low"][2] is None
    assert rows["low"][3] == 10


def test_second_run_skips_existing_articles(agent_env, monkeypatch):
    article = _sample_article("dup-1")
    claude_calls = {"count": 0}

    def fake_parse_feed(feed_url, parsed_feed):
        return [article]

    def fake_fetch_feed(feed_url):
        return {"feed": {"title": "Test Feed"}, "entries": []}

    def fake_call_claude(article, keywords):
        claude_calls["count"] += 1
        return ClaudeResult(summary="Summary.", relevance_score=80)

    monkeypatch.setattr("news_agent.agent.parse_feed", fake_parse_feed)
    monkeypatch.setattr("news_agent.agent.fetch_feed", fake_fetch_feed)
    monkeypatch.setattr("news_agent.agent.call_claude", fake_call_claude)

    run_monitoring_once()
    run_monitoring_once()

    assert claude_calls["count"] == 1

    conn = sqlite3.connect(agent_env["db_path"])
    count = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    conn.close()
    assert count == 1


def test_article_failure_is_stored_and_run_continues(agent_env, monkeypatch):
    articles = [_sample_article("ok"), _sample_article("bad")]

    def fake_parse_feed(feed_url, parsed_feed):
        return articles

    def fake_fetch_feed(feed_url):
        return {"feed": {"title": "Test Feed"}, "entries": []}

    def fake_call_claude(article, keywords):
        if article.id == "bad":
            raise RuntimeError("Claude unavailable")
        return ClaudeResult(summary="Summary.", relevance_score=80)

    monkeypatch.setattr("news_agent.agent.parse_feed", fake_parse_feed)
    monkeypatch.setattr("news_agent.agent.fetch_feed", fake_fetch_feed)
    monkeypatch.setattr("news_agent.agent.call_claude", fake_call_claude)

    run_monitoring_once()
    latest = get_latest_run()

    assert latest["status"] == "partial_success"
    assert latest["articles_failed"] == 1

    conn = sqlite3.connect(agent_env["db_path"])
    failed = conn.execute(
        "SELECT status, error FROM articles WHERE id = 'bad'"
    ).fetchone()
    conn.close()

    assert failed[0] == "failed"
    assert "Claude unavailable" in failed[1]


def test_bad_feed_and_good_feed_results_in_partial_success(
    multi_feed_env, monkeypatch
):
    def fake_fetch_feed(feed_url):
        if "bad-feed" in feed_url:
            raise RuntimeError("Feed unreachable")
        return {"feed": {"title": "Good Feed"}, "entries": []}

    def fake_parse_feed(feed_url, parsed_feed):
        return [_sample_article("from-good-feed")]

    def fake_call_claude(article, keywords):
        return ClaudeResult(summary="Summary.", relevance_score=80)

    monkeypatch.setattr("news_agent.agent.fetch_feed", fake_fetch_feed)
    monkeypatch.setattr("news_agent.agent.parse_feed", fake_parse_feed)
    monkeypatch.setattr("news_agent.agent.call_claude", fake_call_claude)

    run_monitoring_once()
    latest = get_latest_run()

    assert latest["status"] == "partial_success"
    assert latest["articles_new"] == 1
    assert not os.path.exists(multi_feed_env["failure_log"])


def test_feed_failure_does_not_write_failures_log(agent_env, monkeypatch):
    def fake_fetch_feed(feed_url):
        raise RuntimeError("Feed unreachable")

    monkeypatch.setattr("news_agent.agent.fetch_feed", fake_fetch_feed)

    run_monitoring_once()
    latest = get_latest_run()

    assert latest["status"] == "partial_success"
    assert not os.path.exists(agent_env["failure_log"])


def test_claude_failure_after_retries_creates_failed_article(agent_env, monkeypatch):
    def fake_fetch_feed(feed_url):
        return {"feed": {"title": "Test Feed"}, "entries": []}

    def fake_parse_feed(feed_url, parsed_feed):
        return [_sample_article("retry-fail")]

    def fake_request_claude(prompt):
        raise RuntimeError("persistent API failure")

    monkeypatch.setattr("news_agent.agent.fetch_feed", fake_fetch_feed)
    monkeypatch.setattr("news_agent.agent.parse_feed", fake_parse_feed)
    monkeypatch.setattr("news_agent.claude_client._request_claude", fake_request_claude)
    monkeypatch.setattr("news_agent.claude_client.time.sleep", lambda _: None)

    run_monitoring_once()
    latest = get_latest_run()

    assert latest["status"] == "partial_success"
    assert latest["articles_failed"] == 1

    conn = sqlite3.connect(agent_env["db_path"])
    failed = conn.execute(
        "SELECT status, error FROM articles WHERE id = 'retry-fail'"
    ).fetchone()
    conn.close()

    assert failed[0] == "failed"
    assert "persistent API failure" in failed[1]


def test_database_error_during_article_storage_is_global_failure(
    agent_env, monkeypatch
):
    def fake_fetch_feed(feed_url):
        return {"feed": {"title": "Test Feed"}, "entries": []}

    def fake_parse_feed(feed_url, parsed_feed):
        return [_sample_article("db-error")]

    def fake_call_claude(article, keywords):
        return ClaudeResult(summary="Summary.", relevance_score=80)

    def failing_insert(article, status, summary, relevance_score, error):
        raise RuntimeError("database is locked")

    monkeypatch.setattr("news_agent.agent.fetch_feed", fake_fetch_feed)
    monkeypatch.setattr("news_agent.agent.parse_feed", fake_parse_feed)
    monkeypatch.setattr("news_agent.agent.call_claude", fake_call_claude)
    monkeypatch.setattr("news_agent.agent.insert_article", failing_insert)

    run_id = run_monitoring_once()
    latest = get_latest_run()

    assert latest["status"] == "failed"
    assert "database is locked" in latest["error"]
    assert os.path.exists(agent_env["failure_log"])
    failure_log = open(agent_env["failure_log"], encoding="utf-8").read()
    assert f"run_id={run_id}" in failure_log
    assert "database is locked" in failure_log
