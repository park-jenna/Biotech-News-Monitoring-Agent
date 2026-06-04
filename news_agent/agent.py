# Main orchestration: validate config, process articles, run monitoring loop.

import logging
import os

import config
from news_agent.claude_client import call_claude
from news_agent.db import (
    article_exists,
    create_run,
    finish_run,
    init_db,
    insert_article,
)
from news_agent.logging_utils import (
    configure_logging,
    log_feed_warning,
    log_global_failure,
)
from news_agent.models import ArticleInput, RunStats
from news_agent.rss import fetch_feed, parse_feed
from news_agent.utils import utc_now_iso


def validate_runtime_config() -> None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError("ANTHROPIC_API_KEY is not set")


def process_article(article: ArticleInput, run_stats: RunStats) -> None:
    if article_exists(article.id):
        return

    run_stats.articles_new += 1
    try:
        result = call_claude(article, config.RELEVANCE_KEYWORDS)
        if result.relevance_score >= config.RELEVANCE_THRESHOLD:
            insert_article(
                article,
                status="processed",
                summary=result.summary,
                relevance_score=result.relevance_score,
                error=None,
            )
        else:
            insert_article(
                article,
                status="low_relevance",
                summary=None,
                relevance_score=result.relevance_score,
                error=None,
            )
    except Exception as exc:
        run_stats.articles_failed += 1
        run_stats.had_article_failure = True
        insert_article(
            article,
            status="failed",
            summary=None,
            relevance_score=None,
            error=str(exc),
        )


def _determine_run_status(stats: RunStats) -> tuple[str, str | None]:
    if stats.had_feed_failure or stats.had_article_failure:
        return "partial_success", None
    return "success", None


def _fetch_articles(feed_url: str) -> list[ArticleInput]:
    parsed = fetch_feed(feed_url)
    if getattr(parsed, "bozo", False) and not parsed.entries:
        bozo_exception = getattr(parsed, "bozo_exception", None)
        message = str(bozo_exception) if bozo_exception else "Feed parse failed"
        raise RuntimeError(message)

    return parse_feed(feed_url, parsed)


def run_monitoring_once() -> int:
    configure_logging()
    init_db()
    run_id = create_run(utc_now_iso())
    stats = RunStats()

    try:
        validate_runtime_config()
        for feed_url in config.RSS_FEEDS:
            try:
                articles = _fetch_articles(feed_url)
            except Exception as exc:
                stats.had_feed_failure = True
                log_feed_warning(feed_url, str(exc))
                continue

            for article in articles:
                stats.articles_seen += 1
                if article_exists(article.id):
                    continue
                process_article(article, stats)

        status, error = _determine_run_status(stats)
        finish_run(run_id, stats, status, error)
        return run_id
    except Exception as exc:
        finish_run(run_id, stats, "failed", str(exc))
        log_global_failure(run_id, str(exc))
        logging.exception("Monitoring run failed")
        return run_id
