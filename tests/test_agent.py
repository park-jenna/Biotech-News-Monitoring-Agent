# Integration tests for news_agent/agent.py (implemented in Step 6).

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
