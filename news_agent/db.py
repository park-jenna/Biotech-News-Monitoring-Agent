# SQLite helpers: schema init, run lifecycle, article storage, and queries.

import sqlite3
from datetime import datetime, timezone

import config
from news_agent.models import ArticleInput, RunStats

_ARTICLES_SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
    id TEXT PRIMARY KEY,
    title TEXT,
    url TEXT,
    source TEXT,
    published_at TEXT,
    content_excerpt TEXT,
    summary TEXT,
    relevance_score INTEGER,
    status TEXT,
    error TEXT,
    created_at TEXT,
    processed_at TEXT
);
"""

_RUNS_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT,
    finished_at TEXT,
    articles_seen INTEGER,
    articles_new INTEGER,
    articles_failed INTEGER,
    status TEXT,
    error TEXT
);
"""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript(_ARTICLES_SCHEMA + _RUNS_SCHEMA)


def create_run(started_at: str) -> int:
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO runs (
                started_at, finished_at, articles_seen, articles_new,
                articles_failed, status, error
            )
            VALUES (?, NULL, 0, 0, 0, 'running', NULL)
            """,
            (started_at,),
        )
        conn.commit()
        return cursor.lastrowid


def finish_run(
    run_id: int,
    stats: RunStats,
    status: str,
    error: str | None,
) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE runs
            SET finished_at = ?,
                articles_seen = ?,
                articles_new = ?,
                articles_failed = ?,
                status = ?,
                error = ?
            WHERE id = ?
            """,
            (
                _utc_now_iso(),
                stats.articles_seen,
                stats.articles_new,
                stats.articles_failed,
                status,
                error,
                run_id,
            ),
        )
        conn.commit()


def article_exists(article_id: str) -> bool:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM articles WHERE id = ? LIMIT 1",
            (article_id,),
        ).fetchone()
        return row is not None


def insert_article(
    article: ArticleInput,
    status: str,
    summary: str | None,
    relevance_score: int | None,
    error: str | None,
) -> None:
    now = _utc_now_iso()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO articles (
                id, title, url, source, published_at, content_excerpt,
                summary, relevance_score, status, error, created_at, processed_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                article.id,
                article.title,
                article.url,
                article.source,
                article.published_at,
                article.content_excerpt,
                summary,
                relevance_score,
                status,
                error,
                now,
                now,
            ),
        )
        conn.commit()


def get_latest_run() -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM runs ORDER BY id DESC LIMIT 1",
        ).fetchone()
        if row is None:
            return None
        return dict(row)


def get_processed_articles() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM articles
            WHERE status = 'processed'
            ORDER BY relevance_score DESC, published_at DESC
            """,
        ).fetchall()
        return [dict(row) for row in rows]
