# Entrypoint: create Flask app and render the read-only article view at /.

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

DISPLAY_TIMEZONE = ZoneInfo("America/Los_Angeles")

from flask import Flask, render_template_string

import config
from news_agent.db import get_connection, get_latest_run, get_processed_articles, init_db

PAGE_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Biotech News Monitor</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    :root {
      --brand-navy: #00263d;
      --brand-navy-mid: #0d3547;
      --brand-teal: #14b8a6;
      --brand-teal-dark: #0e9a8a;
      --brand-orange: #e07030;
      --bg-page: #f6f8f9;
      --bg-card: #ffffff;
      --bg-muted: #f0f3f5;
      --text-body: #5a6e7a;
      --text-muted: #7a909c;
      --text-light: #9aabb5;
      --border: #e2e8eb;
      --teal-light: #e8f6f3;
      --teal-border: #c5e8e0;
      --shadow: 0 1px 2px rgba(0, 38, 61, 0.04);
    }
    body {
      font-family: "Montserrat", system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      line-height: 1.5;
      margin: 0;
      background: #e2e8eb7a;
      color: var(--text-body);
      -webkit-font-smoothing: antialiased;
    }
    main {
      max-width: 860px;
      margin: 0 auto;
      padding: 2rem 1.25rem 3rem;
    }
    header {
      background: var(--brand-navy-mid);
      border: none;
      border-radius: 8px;
      padding: 1.75rem 1.5rem;
      margin-bottom: 1.5rem;
      box-shadow: var(--shadow);
    }
    header h1 {
      margin: 0 0 0.35rem;
      font-size: 1.75rem;
      font-weight: 700;
      color: #ffffff;
      letter-spacing: -0.02em;
    }
    header .subtitle {
      margin: 0 0 1.25rem;
      color: var(--brand-orange);
      font-size: 1.2rem;
      font-weight: 500;
      line-height: 1.4;
    }
    .summary-bar {
      display: flex;
      flex-direction: column;
      gap: 0.85rem;
      padding-top: 1rem;
      border-top: 1px solid rgba(255, 255, 255, 0.12);
    }
    .summary-line {
      margin: 0;
      color: rgba(255, 255, 255, 0.55);
      font-size: 0.875rem;
      font-weight: 400;
      line-height: 1.45;
    }
    .summary-line.schedule {
      color: rgba(255, 255, 255, 0.55);
    }
    .summary-note,
    .metric-label,
    .status-text {
      color: rgba(255, 255, 255, 0.55);
      font-weight: 400;
    }
    .summary-value {
      color: #ffffff;
      font-weight: 600;
      font-variant-numeric: tabular-nums;
    }
    .summary-run {
      display: flex;
      flex-direction: column;
      gap: 0.55rem;
    }
    .summary-line.run-time {
      display: flex;
      flex-wrap: wrap;
      align-items: baseline;
      gap: 0.35rem 0.5rem;
    }
    .summary-bar .field-label {
      color: var(--brand-teal);
      font-size: 0.72rem;
      font-weight: 600;
      letter-spacing: 0.06em;
      text-transform: uppercase;
    }
    .summary-metrics {
      display: flex;
      flex-wrap: wrap;
      gap: 0.4rem;
      margin: 0;
      padding: 0;
      list-style: none;
    }
    .summary-metrics li {
      margin: 0;
      padding: 0.35rem 0.7rem;
      background: rgba(0, 0, 0, 0.22);
      border-radius: 4px;
      font-size: 0.8125rem;
      line-height: 1.3;
    }
    .summary-metrics .summary-value {
      margin-right: 0.25rem;
    }
    .summary-line.status {
      font-size: 0.875rem;
      line-height: 1.45;
    }
    .summary-topics {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 0.4rem;
      margin: 0;
    }
    .summary-topics .field-label {
      margin-right: 0.1rem;
    }
    .topic-tag {
      font-size: 0.72rem;
      padding: 0.3rem 0.55rem;
      background: rgba(0, 0, 0, 0.22);
      border-radius: 4px;
      color: rgba(255, 255, 255, 0.55);
      line-height: 1.3;
    }
    .meta {
      color: var(--text-muted);
      font-size: 0.95rem;
    }
    .empty {
      background: var(--bg-card);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 2rem;
      text-align: center;
      color: var(--text-muted);
      box-shadow: var(--shadow);
    }
    .article {
      background: var(--bg-card);
      border: 1px solid var(--border);
      border-radius: 5px;
      padding: 1.5rem;
      margin-bottom: 1.25rem;
      box-shadow: var(--shadow);
      display: flex;
      flex-direction: column;
      gap: 0.75rem;
    }
    .article h2 {
      margin: 0;
      font-size: 1.35rem;
      font-weight: 600;
      line-height: 1.35;
      letter-spacing: -0.01em;
      color: var(--brand-navy);
    }
    .article h2 a {
      color: inherit;
      text-decoration: none;
    }
    .article h2 a:hover {
      color: var(--brand-teal-dark);
      text-decoration: underline;
    }
    .article-meta {
      margin: 0;
      color: var(--text-muted);
      font-size: 0.875rem;
      line-height: 1.4;
    }
    .score {
      display: inline-block;
      border-radius: 999px;
      padding: 0.15rem 0.6rem;
      font-size: 0.8125rem;
      font-weight: 600;
      margin-right: 0.5rem;
      vertical-align: baseline;
    }
    .score-high {
      background: var(--brand-navy-mid);
      color: #ffffff;
    }
    .score-medium {
      background: var(--teal-light);
      color: var(--brand-teal-dark);
    }
    .score-low {
      background: #f1f3f5;
      color: var(--text-light);
      border: 1px solid var(--border);
    }
    .summary-label {
      margin: 0;
      color: var(--brand-orange);
      font-size: 0.7rem;
      font-weight: 600;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }
    .summary {
      margin: 0;
      color: var(--brand-navy-mid);
      font-size: 0.975rem;
      line-height: 1.65;
    }
  </style>
</head>
<body>
  <main>
    <header>
      <h1>Biotech News Monitor</h1>
      <p class="subtitle">Automated AI agent tracking AL Amyloidosis &amp; CAR-T news</p>
      <div class="summary-bar">
        <p class="summary-line schedule">
          Scheduled every <span class="summary-value">6 hours</span>
          <span class="summary-note">(runs locally in this demo)</span>
        </p>
        {% if run_summary %}
        <div class="summary-run">
          <p class="summary-line run-time">
            <span class="field-label">Last run</span>
            <span class="summary-value">{{ format_run_datetime(run_summary.last_run_time) }}</span>
          </p>
          <ul class="summary-metrics">
            <li><span class="summary-value">{{ run_summary.feeds_scanned }}</span><span class="metric-label">feeds</span></li>
            <li><span class="summary-value">{{ run_summary.articles_scanned }}</span><span class="metric-label">scanned</span></li>
            <li><span class="summary-value">{{ run_summary.articles_relevant }}</span><span class="metric-label">relevant</span></li>
            <li><span class="summary-value">{{ run_summary.articles_filtered }}</span><span class="metric-label">filtered</span></li>
          </ul>
          {% if run_summary.status_kind == 'partial_feeds' %}
          <p class="summary-line status">
            <span class="summary-value">{{ run_summary.feeds_processed }}</span><span class="status-text"> of </span>
            <span class="summary-value">{{ run_summary.feeds_scanned }}</span><span class="status-text"> feeds processed, </span>
            <span class="summary-value">{{ run_summary.feeds_unavailable }}</span><span class="status-text"> temporarily unavailable </span>
            <span class="summary-note">(handled automatically)</span>
          </p>
          {% elif run_summary.status_kind == 'partial_articles' %}
          <p class="summary-line status">
            <span class="status-text">All feeds processed, some articles could not be analyzed </span>
            <span class="summary-note">(handled automatically)</span>
          </p>
          {% elif run_summary.status_kind == 'failed' %}
          <p class="summary-line status"><span class="status-text">Run failed before completing</span></p>
          {% elif run_summary.status_kind == 'running' %}
          <p class="summary-line status"><span class="status-text">Run in progress</span></p>
          {% else %}
          <p class="summary-line status"><span class="status-text">{{ run_summary.status_message }}</span></p>
          {% endif %}
        </div>
        {% else %}
        <p class="summary-line">No monitoring runs yet.</p>
        {% endif %}
        {% if relevance_keywords %}
        <p class="summary-topics">
          <span class="field-label">Scored for</span>
          {% for keyword in relevance_keywords %}
          <span class="topic-tag">{{ keyword }}</span>
          {% endfor %}
        </p>
        {% else %}
        <p class="summary-line summary-note">Articles are scored by relevance to configured biotech topics.</p>
        {% endif %}
      </div>
    </header>

    {% if articles %}
      {% for article in articles %}
      <article class="article">
        <h2>
          {% if article.url %}
          <a href="{{ article.url }}" target="_blank" rel="noopener noreferrer">{{ article.title }}</a>
          {% else %}
          {{ article.title }}
          {% endif %}
        </h2>
        <p class="article-meta">
          <span class="score {% if article.relevance_score >= 80 %}score-high{% elif article.relevance_score >= 50 %}score-medium{% else %}score-low{% endif %}">Score {{ article.relevance_score }}</span>
          {{ article.source }}
          {% if article.published_at %}
          · {{ format_article_date(article.published_at) }}
          {% endif %}
        </p>
        <p class="summary-label">AI-generated summary</p>
        <p class="summary">{{ article.summary }}</p>
      </article>
      {% endfor %}
    {% else %}
      <div class="empty">
        <p>No relevant processed articles yet.</p>
      </div>
    {% endif %}
  </main>
</body>
</html>
"""


def _parse_iso_datetime(value: str) -> datetime | None:
    try:
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def format_run_datetime(value: str | None) -> str:
    if not value:
        return "unknown time"

    parsed = _parse_iso_datetime(value)
    if parsed is None:
        return value

    local = parsed.astimezone(DISPLAY_TIMEZONE)
    hour = local.hour % 12 or 12
    minute = local.minute
    am_pm = "AM" if local.hour < 12 else "PM"
    tz_label = local.strftime("%Z")
    return (
        f"{local.strftime('%b')} {local.day}, {local.year}, "
        f"{hour}:{minute:02d} {am_pm} {tz_label}"
    )


def format_article_date(value: str | None) -> str:
    if not value:
        return ""

    parsed = _parse_iso_datetime(value)
    if parsed is None:
        return value

    local = parsed.astimezone(DISPLAY_TIMEZONE)
    return f"{local.strftime('%b')} {local.day}, {local.year}"


def _feed_counts_from_run_table(run: dict) -> tuple[int, int] | None:
    feeds_processed = run.get("feeds_processed")
    feeds_unavailable = run.get("feeds_unavailable")
    if feeds_processed is not None and feeds_unavailable is not None:
        return int(feeds_processed), int(feeds_unavailable)
    return None


def _distinct_sources_during_run(run: dict) -> int:
    started_at = run.get("started_at")
    finished_at = run.get("finished_at") or started_at
    if not started_at or not finished_at:
        return 0

    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT COUNT(DISTINCT source)
            FROM articles
            WHERE created_at >= ? AND created_at <= ?
            """,
            (started_at, finished_at),
        ).fetchone()
    return int(row[0]) if row and row[0] is not None else 0


def _distinct_source_count_from_articles() -> int:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(DISTINCT source) FROM articles",
        ).fetchone()
    return int(row[0]) if row and row[0] is not None else 0


def _feed_status_counts(run: dict, total_feeds: int) -> tuple[int, int]:
    table_counts = _feed_counts_from_run_table(run)
    if table_counts is not None:
        feeds_processed, feeds_unavailable = table_counts
        return feeds_processed, feeds_unavailable

    feeds_from_run = _distinct_sources_during_run(run)
    feeds_from_articles = _distinct_source_count_from_articles()
    feeds_processed = max(feeds_from_run, feeds_from_articles)
    feeds_processed = min(feeds_processed, total_feeds)
    feeds_unavailable = total_feeds - feeds_processed
    return feeds_processed, feeds_unavailable


def _article_status_counts_from_articles() -> tuple[int, int, int]:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT
                SUM(CASE WHEN status = 'processed' THEN 1 ELSE 0 END),
                SUM(CASE WHEN status = 'low_relevance' THEN 1 ELSE 0 END),
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END)
            FROM articles
            """,
        ).fetchone()
    relevant = int(row[0] or 0)
    filtered = int(row[1] or 0)
    failed = int(row[2] or 0)
    return relevant, filtered, failed


def _article_stats_for_summary(latest_run: dict) -> tuple[int, int, int]:
    relevant, filtered, failed = _article_status_counts_from_articles()
    analyzed_total = relevant + filtered + failed
    if analyzed_total > 0:
        return analyzed_total, relevant, filtered

    scanned = latest_run.get("articles_seen")
    return int(scanned or 0), 0, 0


def build_articles_line(scanned: int, relevant: int, filtered: int) -> str:
    return (
        f"{scanned} articles scanned · {relevant} relevant · "
        f"{filtered} filtered out"
    )


def build_scoring_topics_line(keywords: list[str]) -> str:
    if not keywords:
        return "Articles are scored by relevance to configured biotech topics."
    topics = ", ".join(keywords)
    return f"Articles are scored by relevance to: {topics}"


def build_run_summary(latest_run: dict | None) -> dict | None:
    if latest_run is None:
        return None

    total_feeds = len(config.RSS_FEEDS)
    status = latest_run.get("status")
    articles_scanned, articles_relevant, articles_filtered = (
        _article_stats_for_summary(latest_run)
    )
    last_run_time = (
        latest_run.get("finished_at")
        or latest_run.get("started_at")
        or "unknown time"
    )

    feeds_processed = None
    feeds_unavailable = None
    status_kind = "success"
    if status == "success":
        status_message = "All feeds processed"
    elif status == "partial_success":
        feeds_processed, feeds_unavailable = _feed_status_counts(
            latest_run, total_feeds
        )
        if feeds_unavailable > 0:
            status_kind = "partial_feeds"
            status_message = (
                f"{feeds_processed} of {total_feeds} feeds processed, "
                f"{feeds_unavailable} temporarily unavailable (handled automatically)"
            )
        else:
            status_kind = "partial_articles"
            status_message = (
                "All feeds processed, some articles could not be analyzed "
                "(handled automatically)"
            )
    elif status == "failed":
        status_kind = "failed"
        status_message = "Run failed before completing"
    elif status == "running":
        status_kind = "running"
        status_message = "Run in progress"
    else:
        status_kind = "other"
        status_message = str(status)

    return {
        "last_run_time": last_run_time,
        "feeds_scanned": total_feeds,
        "articles_scanned": articles_scanned,
        "articles_relevant": articles_relevant,
        "articles_filtered": articles_filtered,
        "articles_line": build_articles_line(
            articles_scanned, articles_relevant, articles_filtered
        ),
        "status_message": status_message,
        "status_kind": status_kind,
        "feeds_processed": feeds_processed,
        "feeds_unavailable": feeds_unavailable,
    }


def create_app() -> Flask:
    app = Flask(__name__)

    @app.get("/")
    def index():
        init_db()
        latest_run = get_latest_run()
        return render_template_string(
            PAGE_TEMPLATE,
            run_summary=build_run_summary(latest_run),
            relevance_keywords=config.RELEVANCE_KEYWORDS,
            format_run_datetime=format_run_datetime,
            format_article_date=format_article_date,
            articles=get_processed_articles(),
        )

    return app


def main() -> None:
    app = create_app()
    app.run(host="127.0.0.1", port=5000)


if __name__ == "__main__":
    main()
