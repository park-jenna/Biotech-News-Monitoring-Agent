# Biotech News Monitoring Agent

Local MVP that monitors biotech and FDA news from RSS feeds, uses Claude to
summarize and score new articles for relevance, stores results in SQLite,
and shows relevant articles on a simple read-only Flask page.

## What It Does

1. Fetches articles from configured RSS feeds (RSS entry fields only; no page scraping).
2. Deduplicates articles in SQLite so already-seen items are not reprocessed.
3. Calls Claude once per new article to produce a summary and relevance score.
4. Stores results with status `processed`, `low_relevance`, or `failed`.
5. Runs on a schedule via APScheduler after you start `scheduler.py`.
6. Exposes a read-only web view at `/` for relevant articles and latest run status.

## Requirements

- Python 3.11+ (tested with 3.14)
- Anthropic API key in `ANTHROPIC_API_KEY`

On macOS, if RSS fetch fails with SSL certificate errors, run:

```bash
/Applications/Python\ 3.14/Install\ Certificates.command
```

Adjust the path for your Python version if needed.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY="your_key_here"
```

Never commit the API key. It is read from the environment only.

## Commands

### Run one monitoring job immediately

```bash
python3 run_once.py
```

Initializes SQLite if needed, validates config, fetches feeds, processes new
articles, and updates the latest run row.

### Start the scheduler

```bash
python3 scheduler.py
```

Starts APScheduler with `max_instances=1` and `coalesce=True` so overlapping
runs do not execute. The first run is scheduled at startup; later runs use
`SCHEDULE_INTERVAL_HOURS` from `config.py`.

Stop with `Ctrl+C`.

### Start the web app

```bash
python3 app.py
```

Open http://127.0.0.1:5000/

The page shows only articles with `status = "processed"` (relevance score at
or above `RELEVANCE_THRESHOLD`), ordered by score then recency.

## Configuration

All MVP settings live in `config.py`:

| Setting | Purpose |
|---------|---------|
| `RSS_FEEDS` | RSS feed URLs to monitor |
| `RELEVANCE_KEYWORDS` | Topics passed to Claude for scoring |
| `CLAUDE_MODEL` | Anthropic model name |
| `SCHEDULE_INTERVAL_HOURS` | Scheduler interval |
| `RELEVANCE_THRESHOLD` | Minimum score (0–100) for web display |
| `DATABASE_PATH` | SQLite database file |
| `FAILURE_LOG_PATH` | Local global failure log |

## Architecture

```text
run_once.py / scheduler.py
        │
        ▼
   news_agent/agent.py          orchestration, run lifecycle
        │
        ├── news_agent/rss.py           fetch and parse RSS entries
        ├── news_agent/claude_client.py summarize and score via Claude
        ├── news_agent/db.py            SQLite storage and queries
        ├── news_agent/utils.py         dedup, timestamps, truncation
        └── news_agent/logging_utils.py feed warnings and global failures

app.py
        │
        └── reads processed articles and latest run from SQLite
```

### Data flow for one run

1. Insert a `runs` row with status `running`.
2. Validate `ANTHROPIC_API_KEY`.
3. For each feed: fetch, parse, skip duplicates, call Claude for new articles.
4. Store each article as `processed`, `low_relevance`, or `failed`.
5. Finish the run as `success`, `partial_success`, or `failed`.

Article identity uses a SHA-256 hash of the normalized URL, or of the GUID
when no URL exists.

## Inspecting Data

```bash
sqlite3 news_agent.db ".tables"
sqlite3 news_agent.db "select id, status, articles_seen, articles_new, articles_failed from runs order by id desc limit 5;"
sqlite3 news_agent.db "select title, status, relevance_score from articles order by processed_at desc limit 10;"
tail -n 20 failures.log
```

## Failure Handling

| Failure type | Behavior |
|--------------|----------|
| Feed unreachable / malformed | Log feed URL and error, continue other feeds, run may finish as `partial_success` |
| Claude / validation error | Store article as `failed`, increment `articles_failed`, continue run |
| Global run failure | Mark run as `failed`, append one line to `failures.log` |

Global failures include missing `ANTHROPIC_API_KEY`, database errors during
run recording, and unexpected top-level exceptions.

Each `failures.log` line includes a UTC timestamp, run id when available,
and an error message. Feed failures are logged to application logs only,
not to `failures.log`.

### Production alert mapping

For production, treat `failures.log` as the alert source:

- **Slack:** ship the log with Fluent Bit, Vector, or CloudWatch Logs and trigger a Slack webhook when a new line appears (e.g. AWS Lambda, Datadog monitor, or Grafana Loki alert).
- **Email:** use the same log tail pattern with a small watcher process or cron job that emails on new lines, or route through PagerDuty/Opsgenie from your log platform.

Feed-level warnings stay in application logs unless you add separate alerting
for repeated `partial_success` runs.

## Scheduler Production Mapping

Local APScheduler maps to:

- **Cron:** run `python3 run_once.py` on the desired interval, e.g. `0 * * * *` for hourly.
- **Cloud scheduler:** AWS EventBridge + ECS/Fargate task, GCP Cloud Scheduler + Cloud Run job, or Kubernetes CronJob invoking the same entrypoint in a container.

Use `max_instances=1` / coalescing semantics in your orchestrator so a long
run does not overlap the next scheduled execution.

## Development Checks

```bash
python3 -m pytest
python3 -m py_compile config.py run_once.py scheduler.py app.py news_agent/*.py
```

## Intentionally Not Implemented

- User accounts or authentication
- Configuration UI or YAML config files
- Web scraping of linked article pages
- Cloud deployment artifacts
- Real Slack or email alert sending
- Automatic retry of failed articles
- Admin controls for retry, delete, edit, or re-score
- Pagination, search, or filtering on the web page
- React or other frontend build tooling

See `SPEC.md` for full acceptance criteria and `IMPLEMENTATION_PLAN.md` for
the build sequence used to implement this MVP.
