# Unit tests for news_agent/db.py (implemented in Step 2).

import os
import tempfile

import pytest

import config
from news_agent.db import (
    article_exists,
    create_run,
    finish_run,
    get_latest_run,
    get_processed_articles,
    init_db,
    insert_article,
)
from news_agent.models import ArticleInput, RunStats


@pytest.fixture
def temp_db(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        monkeypatch.setattr(config, "DATABASE_PATH", db_path)
        init_db()
        yield db_path


def _sample_article(article_id: str = "article-1") -> ArticleInput:
    return ArticleInput(
        id=article_id,
        title="Test Article",
        url="https://example.com/article",
        guid=None,
        source="Example Feed",
        published_at="2026-06-01T12:00:00+00:00",
        content_excerpt="Sample excerpt.",
    )


def test_init_db_creates_both_tables(temp_db):
    import sqlite3

    conn = sqlite3.connect(temp_db)
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    conn.close()
    assert {"articles", "runs"}.issubset(tables)


def test_run_lifecycle(temp_db):
    run_id = create_run("2026-06-01T10:00:00+00:00")
    latest = get_latest_run()

    assert run_id == 1
    assert latest["status"] == "running"
    assert latest["articles_seen"] == 0
    assert latest["finished_at"] is None

    stats = RunStats(articles_seen=5, articles_new=2, articles_failed=1)
    finish_run(run_id, stats, "partial_success", "one feed failed")

    latest = get_latest_run()
    assert latest["status"] == "partial_success"
    assert latest["error"] == "one feed failed"
    assert latest["articles_seen"] == 5
    assert latest["articles_new"] == 2
    assert latest["articles_failed"] == 1
    assert latest["finished_at"] is not None


def test_article_exists_and_insert(temp_db):
    article = _sample_article()
    assert article_exists(article.id) is False

    insert_article(
        article,
        status="processed",
        summary="A relevant summary.",
        relevance_score=80,
        error=None,
    )

    assert article_exists(article.id) is True


def test_get_processed_articles_excludes_other_statuses(temp_db):
    insert_article(
        _sample_article("processed-1"),
        status="processed",
        summary="High relevance.",
        relevance_score=90,
        error=None,
    )
    insert_article(
        _sample_article("low-1"),
        status="low_relevance",
        summary=None,
        relevance_score=10,
        error=None,
    )
    insert_article(
        _sample_article("failed-1"),
        status="failed",
        summary=None,
        relevance_score=None,
        error="Claude error",
    )

    processed = get_processed_articles()
    assert len(processed) == 1
    assert processed[0]["id"] == "processed-1"
    assert processed[0]["relevance_score"] == 90


def test_get_processed_articles_ordered_by_score_then_date(temp_db):
    insert_article(
        ArticleInput(
            id="older-high",
            title="Older High",
            url=None,
            guid="g1",
            source="Feed",
            published_at="2026-06-01T12:00:00+00:00",
            content_excerpt="",
        ),
        status="processed",
        summary="Summary",
        relevance_score=90,
        error=None,
    )
    insert_article(
        ArticleInput(
            id="newer-high",
            title="Newer High",
            url=None,
            guid="g2",
            source="Feed",
            published_at="2026-06-02T12:00:00+00:00",
            content_excerpt="",
        ),
        status="processed",
        summary="Summary",
        relevance_score=90,
        error=None,
    )
    insert_article(
        ArticleInput(
            id="low-score",
            title="Low Score",
            url=None,
            guid="g3",
            source="Feed",
            published_at="2026-06-03T12:00:00+00:00",
            content_excerpt="",
        ),
        status="processed",
        summary="Summary",
        relevance_score=50,
        error=None,
    )

    processed = get_processed_articles()
    assert [row["id"] for row in processed] == ["newer-high", "older-high", "low-score"]
