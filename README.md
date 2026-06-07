# Biotech News Monitoring Agent

Local MVP that monitors biotech and FDA news plus AL amyloidosis clinical
trials from RSS feeds, uses Claude to summarize and score new items for
relevance, stores results in SQLite, and shows relevant articles on a
read-only Flask dashboard.

**Live demo:** [news-monitoring-agent-e8ns.onrender.com](https://news-monitoring-agent-e8ns.onrender.com)

## What It Does

1. Fetches entries from configured RSS feeds (RSS fields only; no page scraping).
2. Deduplicates items in SQLite so already-seen articles are not reprocessed.
3. Calls Claude once per new item to produce a summary and relevance score (0–100).
4. Stores results with status `processed`, `low_relevance`, or `failed`.
5. Runs on a schedule via APScheduler after you start `scheduler.py`.
6. Exposes a read-only web view at `/` with a summary bar, scored article cards,
   and plain-language run status.

## Data Sources

All feed URLs are configured in `config.py` (`RSS_FEEDS`). Current sources:

| Source | URL | Notes |
|--------|-----|-------|
| FDA Press Releases | `https://www.fda.gov/.../press-releases/rss.xml` | Stable |
| BioPharma Dive | `https://www.biopharmadive.com/feeds/news/` | Stable |
| Fierce Biotech | `https://www.fiercebiotech.com/rss/news` | Often fails (malformed XML); run continues as `partial_success` |
| ClinicalTrials.gov | `https://clinicaltrials.gov/ct2/results/rss.xml?cond=AL+Amyloidosis` | Search-based RSS; trials first posted in the last 14 days |

### ClinicalTrials.gov RSS

ClinicalTrials.gov does not publish one static feed. You build a feed URL from
search parameters (same as the **RSS** button on search results). Important:

- Use the **`rss.xml`** endpoint (without `.xml`, the server returns HTML and
  parsing fails).
- The default window is **first posted in the last 14 days**.
- To change scope, edit the query string in `config.py` (for example
  `?cond=AL+Amyloidosis&term=BCMA` for a narrower BCMA focus).

Article identity is a SHA-256 hash of the normalized URL. Different query
params in the trial URL produce different hashes, so avoid switching between
broad and narrow ClinicalTrials queries on the same database if you want a
clean snapshot without duplicates. A more robust fix would deduplicate on the
trial's stable registry id (NCT number) rather than the full URL.

## Requirements

- Python 3.11+ (tested with 3.14.3)
- Anthropic API key in `ANTHROPIC_API_KEY` (agent runs only; not needed on Render read-only deploy)

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
`SCHEDULE_INTERVAL_HOURS` from `config.py` (currently **6 hours**).

Stop with `Ctrl+C`.

### Start the web app

```bash
python3 app.py
```

Open http://127.0.0.1:5000/

On macOS, if port 5000 is in use (often AirPlay Receiver), stop the other
process or run on another port:

```bash
python3 -c "from app import create_app; create_app().run(host='127.0.0.1', port=5001)"
```

The page shows only articles with `status = "processed"` (relevance score at
or above `RELEVANCE_THRESHOLD`), ordered by score then recency.

## Dashboard

The read-only page (`app.py`) includes:

- **Summary bar:** last run time, feed count, cumulative scanned / relevant /
  filtered counts, and plain-language status (for example "2 of 4 feeds
  processed, 1 temporarily unavailable").
- **Scoring topics:** relevance keywords from `config.py`.
- **Article cards:** title (linked when URL exists), color-coded score badge,
  source, published date, and AI-generated summary.

Summary stats pull from the `runs` and `articles` tables. Feed success counts
are derived from article sources when run-level feed columns are not stored.

## Configuration

All MVP settings live in `config.py`:

| Setting | Purpose |
|---------|---------|
| `RSS_FEEDS` | RSS feed URLs to monitor |
| `RELEVANCE_KEYWORDS` | Topics passed to Claude for scoring |
| `CLAUDE_MODEL` | Anthropic model name |
| `SCHEDULE_INTERVAL_HOURS` | Scheduler interval (hours) |
| `RELEVANCE_THRESHOLD` | Minimum score (0–100) for web display |
| `DATABASE_PATH` | SQLite database file (overridable via env var) |
| `FAILURE_LOG_PATH` | Local global failure log |

## Database Files

| Path | Purpose |
|------|---------|
| `news_agent.db` | Local runtime database (gitignored) |
| `data/news_agent.db` | Committed snapshot for Render demo deploy |

Render serves the snapshot at `data/news_agent.db` via `DATABASE_PATH`. After
local agent runs, copy the local DB into `data/` before pushing to refresh the
live dashboard.

### Refresh the demo snapshot

```bash
python3 run_once.py
cp news_agent.db data/news_agent.db
git add data/news_agent.db
git commit -m "Update demo database snapshot"
git push
```

### Start a clean snapshot (no duplicate trials)

Use this when changing ClinicalTrials query params or resetting after broad
feed experiments:

```bash
cp news_agent.db news_agent.db.bak-$(date +%Y%m%d)
rm news_agent.db
export ANTHROPIC_API_KEY="your_key_here"
python3 run_once.py
cp news_agent.db data/news_agent.db
```

A fresh run calls Claude for every new RSS entry across all feeds (~30+ API
calls typical).

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
sqlite3 news_agent.db "select title, status, relevance_score, source from articles where status='processed' order by relevance_score desc;"
sqlite3 news_agent.db "select title, count(*) from articles group by title having count(*) > 1;"
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

- **Cron:** run `python3 run_once.py` on the desired interval, e.g. `0 */6 * * *` for every 6 hours.
- **Cloud scheduler:** AWS EventBridge + ECS/Fargate task, GCP Cloud Scheduler + Cloud Run job, or Kubernetes CronJob invoking the same entrypoint in a container.

Use `max_instances=1` / coalescing semantics in your orchestrator so a long
run does not overlap the next scheduled execution.

## Deployment

The web view is deployed on [Render](https://render.com) as a read-only demo
dashboard. The agent and scheduler run locally in this demo setup.

Build runs `pip install -r requirements.txt`. The app is served with gunicorn
via `wsgi.py`. Render settings live in `render.yaml`; the web service sets
`DATABASE_PATH=data/news_agent.db`.

The scheduler does not run on Render. In production it would move to a cron job
or cloud scheduler (Render Cron, GitHub Actions, or AWS EventBridge), and the
SQLite file would move to a hosted database. Failure logging would become a
Slack or email alert.

`ANTHROPIC_API_KEY` is not required on Render when you only serve the
pre-seeded read-only page. Render does not auto-update when you run the agent
locally; push an updated `data/news_agent.db` snapshot to refresh the live
dashboard.

### Render setup

1. Push this repo to GitHub.
2. In Render: **New → Blueprint** and select the repo (`render.yaml`), or
   create a **Web Service** manually with:
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `gunicorn wsgi:app --bind 0.0.0.0:$PORT`
   - **Environment:** `DATABASE_PATH=data/news_agent.db`
3. Open the service URL (for example
   [news-monitoring-agent-e8ns.onrender.com](https://news-monitoring-agent-e8ns.onrender.com)).

Free tier services may cold-start; open the URL once before a demo.

## Development Checks

```bash
python3 -m pytest
python3 -m py_compile config.py run_once.py scheduler.py app.py news_agent/*.py
```

## Intentionally Not Implemented

- User accounts or authentication
- Configuration UI or YAML config files
- Web scraping of linked article pages
- ClinicalTrials.gov API integration (RSS only for trials in this MVP)
- Real Slack or email alert sending
- Automatic retry of failed articles
- Admin controls for retry, delete, edit, or re-score
- Pagination, search, or filtering on the web page
- React or other frontend build tooling
- Hosted database (Render demo uses committed SQLite snapshot only)

See `SPEC.md` for full acceptance criteria and `IMPLEMENTATION_PLAN.md` for
the build sequence used to implement this MVP.
