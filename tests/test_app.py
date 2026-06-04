# Unit tests for app.py (implemented in Step 9).

import os
import sqlite3
import tempfile

import pytest

import config
from app import create_app
from news_agent.db import create_run, finish_run, init_db, insert_article
from news_agent.models import ArticleInput, RunStats


@pytest.fixture
def app_client(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        monkeypatch.setattr(config, "DATABASE_PATH", db_path)
        init_db()
        app = create_app()
        app.config["TESTING"] = True
        yield app.test_client(), db_path


def _insert_processed(
    article_id: str,
    title: str,
    score: int,
    published_at: str | None,
) -> None:
    insert_article(
        ArticleInput(
            id=article_id,
            title=title,
            url=f"https://example.com/{article_id}",
            guid=None,
            source="Test Feed",
            published_at=published_at,
            content_excerpt="Excerpt",
        ),
        status="processed",
        summary=f"Summary for {title}.",
        relevance_score=score,
        error=None,
    )


def test_index_renders_cleanly_with_no_runs_or_articles(app_client):
    client, _ = app_client
    response = client.get("/")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "No monitoring runs yet." in body
    assert "No relevant processed articles yet." in body


def test_index_shows_latest_run_and_processed_articles_only(app_client):
    client, _ = app_client

    run_id = create_run("2026-06-01T10:00:00+00:00")
    finish_run(run_id, RunStats(articles_seen=3, articles_new=3), "success", None)

    _insert_processed("high-new", "Newer High Score", 95, "2026-06-02T12:00:00+00:00")
    _insert_processed("high-old", "Older High Score", 95, "2026-06-01T12:00:00+00:00")

    insert_article(
        ArticleInput(
            id="low-1",
            title="Low relevance",
            url="https://example.com/low",
            guid=None,
            source="Test Feed",
            published_at="2026-06-03T12:00:00+00:00",
            content_excerpt="Excerpt",
        ),
        status="low_relevance",
        summary=None,
        relevance_score=10,
        error=None,
    )
    insert_article(
        ArticleInput(
            id="failed-1",
            title="Failed article",
            url="https://example.com/failed",
            guid=None,
            source="Test Feed",
            published_at="2026-06-03T12:00:00+00:00",
            content_excerpt="Excerpt",
        ),
        status="failed",
        summary=None,
        relevance_score=None,
        error="Claude error",
    )

    response = client.get("/")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "status success" in body
    assert "Newer High Score" in body
    assert "Older High Score" in body
    assert "Low relevance" not in body
    assert "Failed article" not in body
    assert body.index("Newer High Score") < body.index("Older High Score")


def test_index_renders_title_without_link_when_url_missing(app_client):
    client, _ = app_client

    insert_article(
        ArticleInput(
            id="no-url",
            title="Guid only article",
            url=None,
            guid="guid-123",
            source="Test Feed",
            published_at=None,
            content_excerpt="Excerpt",
        ),
        status="processed",
        summary="Summary without URL.",
        relevance_score=80,
        error=None,
    )

    response = client.get("/")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Guid only article" in body
    assert "Summary without URL." in body
    assert "href=" not in body.split("Guid only article")[1].split("</h2>")[0]
