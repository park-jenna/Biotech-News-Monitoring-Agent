# IMPLEMENTATION PLAN: Scheduled Biotech News Monitoring Agent

This plan turns `SPEC.md` into a one-week MVP implementation path. It is
organized so each step can be built, manually verified, and tested before
moving to the next step.

---

## 1. Proposed File Structure

```text
news_monitoring_agent/
+-- SPEC.md
+-- IMPLEMENTATION_PLAN.md
+-- README.md
+-- requirements.txt
+-- config.py
+-- run_once.py
+-- scheduler.py
+-- app.py
+-- news_agent/
|   +-- __init__.py
|   +-- agent.py
|   +-- claude_client.py
|   +-- db.py
|   +-- logging_utils.py
|   +-- models.py
|   +-- rss.py
|   +-- utils.py
+-- tests/
    +-- __init__.py
    +-- test_claude_client.py
    +-- test_db.py
    +-- test_rss.py
    +-- test_utils.py
```

Runtime-generated files should not be committed:

```text
news_agent.db
failures.log
__pycache__/
.pytest_cache/
```

Add these to `.gitignore` if the file does not already exist.

---

## 2. Modules, Functions, And Responsibilities

### `config.py`

Defines MVP settings:

- `RSS_FEEDS`
- `RELEVANCE_KEYWORDS`
- `CLAUDE_MODEL`
- `SCHEDULE_INTERVAL_HOURS`
- `RELEVANCE_THRESHOLD`
- `DATABASE_PATH`
- `FAILURE_LOG_PATH`

### `news_agent/models.py`

Use simple dataclasses for internal data movement:

- `ArticleInput`: normalized RSS article before Claude processing.
- `ClaudeResult`: validated Claude output.
- `RunStats`: mutable counters for one agent run.

Recommended fields:

```python
from dataclasses import dataclass


@dataclass
class ArticleInput:
    id: str
    title: str
    url: str | None
    guid: str | None
    source: str
    published_at: str | None
    content_excerpt: str


@dataclass
class ClaudeResult:
    summary: str
    relevance_score: int


@dataclass
class RunStats:
    articles_seen: int = 0
    articles_new: int = 0
    articles_failed: int = 0
    had_feed_failure: bool = False
    had_article_failure: bool = False
```

Keep these lightweight. Do not add an ORM.

### `news_agent/utils.py`

Utility functions:

- `utc_now_iso() -> str`
- `normalize_url(url: str) -> str`
- `make_article_id(url: str | None, guid: str | None) -> str | None`
- `truncate_text(text: str, max_chars: int = 4000) -> str`

### `news_agent/db.py`

SQLite functions:

- `get_connection() -> sqlite3.Connection`
- `init_db() -> None`
- `create_run(started_at: str) -> int`
- `finish_run(run_id: int, stats: RunStats, status: str, error: str | None) -> None`
- `article_exists(article_id: str) -> bool`
- `insert_article(article: ArticleInput, status: str, summary: str | None, relevance_score: int | None, error: str | None) -> None`
- `get_latest_run() -> dict | None`
- `get_processed_articles() -> list[dict]`

Use one connection per operation or per run. Set `row_factory` to
`sqlite3.Row` for readable query results.

### `news_agent/rss.py`

RSS parsing functions:

- `fetch_feed(feed_url: str) -> feedparser.FeedParserDict`
- `parse_feed(feed_url: str, parsed_feed) -> list[ArticleInput]`
- `extract_content_excerpt(entry) -> str`
- `parse_published_at(entry) -> str | None`

This module must use only RSS entry fields and must not fetch linked
article pages.

### `news_agent/claude_client.py`

Claude integration:

- `build_prompt(article: ArticleInput, keywords: list[str]) -> str`
- `call_claude(article: ArticleInput, keywords: list[str]) -> ClaudeResult`
- `parse_claude_json(raw_text: str) -> ClaudeResult`
- `validate_claude_result(data: dict) -> ClaudeResult`

`call_claude` owns retry behavior: three attempts with `1s`, `2s`, and
`4s` backoff. It must read the model name from `config.CLAUDE_MODEL`.
JSON parsing and validation must be testable without calling the real
API.

### `news_agent/logging_utils.py`

Failure logging helpers:

- `configure_logging() -> None`
- `log_global_failure(run_id: int | None, error: str) -> None`
- `log_feed_warning(feed_url: str, message: str) -> None`

`log_global_failure` appends one line to `FAILURE_LOG_PATH` with UTC
timestamp, run id if available, and error message.

### `news_agent/agent.py`

Main orchestration:

- `validate_runtime_config() -> None`
- `process_article(article: ArticleInput, run_stats: RunStats) -> None`
- `run_monitoring_once() -> int`

`run_monitoring_once` initializes storage, creates the run row, handles
top-level failures, updates run status, and returns the run id.

### Entrypoints

- `run_once.py`: calls `run_monitoring_once()`.
- `scheduler.py`: starts APScheduler with no overlapping runs.
- `app.py`: creates Flask app and renders `/`.

---

## 3. AI Coding Instructions

Follow these instructions when implementing this project with an AI
coding assistant.

- Treat `SPEC.md` as the source of truth for product behavior and this
  file as the source of truth for implementation sequence.
- Build one step at a time. Do not jump ahead to Flask, scheduler, or
  README work before the core run flow and storage behavior are working.
- After each step, run the listed manual verification commands or explain
  why they cannot be run.
- Keep dependencies minimal: `anthropic`, `feedparser`, `flask`,
  `apscheduler`, and `pytest` for tests.
- Use `python3` in documented commands. If a virtual environment exposes
  `python`, that alias is acceptable locally.
- Do not introduce an ORM, frontend framework, task queue, web scraper,
  YAML parser, or cloud-specific dependency.
- Keep business configuration in `config.py`; do not hardcode feeds,
  keywords, thresholds, database path, or failure log path inside modules.
- Keep modules small and direct. Prefer simple functions and dataclasses
  over large classes.
- Make Claude parsing and validation testable without a live API call.
- Use monkeypatching or fake functions in tests instead of real Claude
  calls or live RSS feeds.
- Write brief comments for main components and non-obvious Python idioms,
  but avoid comments that restate obvious code.
- Preserve idempotency: never call Claude for an article id already
  stored in SQLite.
- Preserve the RSS-only boundary: never fetch or scrape linked article
  pages.
- If an edge case is unclear, choose the behavior already specified in
  `SPEC.md`; do not expand scope.
- Do not commit runtime artifacts such as `news_agent.db`,
  `failures.log`, caches, or virtual environments.

---

## 4. Build Order With Manual Verification

### Step 1: Project Skeleton And Config

Create `requirements.txt`, `config.py`, package folder, and empty
entrypoint files.

Manual verification:

- Run `python3 -m py_compile config.py`.
- Confirm `config.py` contains no secrets.
- Confirm generated files are listed in `.gitignore`.

Commands:

```bash
python3 -m py_compile config.py
```

### Step 2: SQLite Schema And DB Helpers

Implement `news_agent/db.py`, `news_agent/models.py`, and `init_db()`.

Manual verification:

- Run `init_db()` from a Python shell or temporary command.
- Confirm the SQLite file is created.
- Inspect tables and columns.

Commands:

```bash
python3 -c "from news_agent.db import init_db; init_db()"
sqlite3 news_agent.db ".schema"
```

### Step 3: Utility Functions And Dedup

Implement timestamp, URL normalization, article id hashing, and text
truncation helpers.

Manual verification:

- Same URL with different fragments creates the same normalized URL.
- Scheme and host are lowercased.
- Query strings are preserved.
- Missing URL with GUID still creates an id.
- Missing URL and GUID returns `None`.

Commands:

```bash
python3 -m pytest tests/test_utils.py
```

### Step 4: RSS Fetching And Parsing

Implement RSS fetch and parse behavior with `feedparser`.

Manual verification:

- One configured feed returns parsed entries.
- Entries have title fallback, source fallback, published date handling,
  content excerpt, and article id inputs.
- Parser does not fetch linked article pages.

Commands:

```bash
python3 -m pytest tests/test_rss.py
python3 -c "import config; from news_agent.rss import fetch_feed, parse_feed; f=fetch_feed(config.RSS_FEEDS[0]); print(len(parse_feed(config.RSS_FEEDS[0], f)))"
```

### Step 5: Claude JSON Parsing And Validation

Implement prompt builder, parser, validator, and mocked retry tests
before calling the real API.

Manual verification:

- Valid Claude JSON returns `ClaudeResult`.
- Malformed JSON fails validation.
- Missing fields fail validation.
- String score, float score, negative score, and score above `100` fail
  validation.
- Extra fields do not break parsing.

Commands:

```bash
python3 -m pytest tests/test_claude_client.py
```

### Step 6: Full One-Run Agent Flow

Implement `process_article`, `run_monitoring_once`, and `run_once.py`.

Manual verification:

- Missing API key records a failed run and writes `failures.log`.
- With a valid API key, `python3 run_once.py` stores new articles.
- Running `python3 run_once.py` twice does not duplicate rows.
- Low-relevance articles are stored but not marked `processed`.
- Article-level failures are stored as `failed` and do not crash the run.

Commands:

```bash
python3 run_once.py
sqlite3 news_agent.db "select id, status, relevance_score, error from articles limit 10;"
sqlite3 news_agent.db "select id, status, articles_seen, articles_new, articles_failed, error from runs order by id desc limit 5;"
```

### Step 7: Failure Handling

Finish global failure logging, feed failure handling, and
`partial_success` status.

Manual verification:

- Bad feed plus good feed results in `partial_success`.
- Claude failure after retries creates a failed article.
- Global failure appends a line to `failures.log`.
- Feed failure does not write to `failures.log` unless the whole run
  fails.

Commands:

```bash
python3 run_once.py
tail -n 20 failures.log
sqlite3 news_agent.db "select status, error from runs order by id desc limit 3;"
```

### Step 8: Scheduler

Implement `scheduler.py` with APScheduler interval trigger and no
overlapping runs. Use job settings equivalent to `max_instances=1` and
`coalesce=True`.

Manual verification:

- Scheduler starts and logs scheduled runs.
- If a run is still executing, the next scheduled run is skipped or
  coalesced.
- Stopping the process does not corrupt the database.

Commands:

```bash
python3 scheduler.py
```

### Step 9: Flask Web Page

Implement `app.py` and a simple HTML view at `/`.

Manual verification:

- Empty database renders cleanly.
- No previous runs renders cleanly.
- Processed articles appear ordered by score, then recency.
- Low-relevance and failed articles do not appear.
- Latest run status appears in the header.

Commands:

```bash
python3 app.py
curl http://127.0.0.1:5000/
```

### Step 10: README And Final Pass

Write README with setup, commands, architecture, scheduler mapping, and
alert mapping.

Manual verification:

- A new reader can install dependencies, configure the API key, run one
  monitoring job, start the scheduler, and view the web page.
- README states what is intentionally not implemented.

Commands:

```bash
python3 -m pytest
python3 -m py_compile config.py run_once.py scheduler.py app.py news_agent/*.py
```

---

## 5. Test Plan

Use `pytest` for focused unit tests. Do not require live RSS or Claude
for unit tests.

### Unit Tests

- `test_utils.py`
  - URL normalization strips fragments.
  - Scheme and host are lowercased.
  - Query strings are preserved.
  - Article ids are stable.
  - Missing URL and GUID returns `None`.

- `test_db.py`
  - `init_db` creates both tables.
  - Run rows can move from `running` to final statuses.
  - Article insert and `article_exists` support idempotency.
  - Processed article query excludes low relevance and failed rows.

- `test_rss.py`
  - RSS entries become `ArticleInput`.
  - Missing title becomes `"(untitled)"`.
  - Missing source uses feed URL.
  - Missing URL with GUID is accepted.
  - Missing URL and GUID is skipped before Claude.

- `test_claude_client.py`
  - Valid JSON parses.
  - Malformed JSON raises a validation error.
  - Missing fields fail.
  - Invalid score types and ranges fail.
  - Extra fields are ignored.
  - Retry wrapper retries expected exceptions.

### Integration Tests

Keep integration tests lightweight:

- Use a temporary SQLite database.
- Monkeypatch RSS parsing to return fixed `ArticleInput` objects.
- Monkeypatch Claude calls to return deterministic `ClaudeResult`
  objects.
- Verify full run statuses: `success`, `partial_success`, and `failed`.
- Verify a second run skips existing articles.

### Manual Tests

Manual tests cover real dependencies:

- One real RSS fetch.
- One real Claude call with a valid API key.
- One scheduled run with APScheduler.
- One Flask page render in a browser.

---

## 6. Commands To Run

### Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY="your_key_here"
```

### Development Checks

```bash
python3 -m py_compile config.py run_once.py scheduler.py app.py news_agent/*.py
python3 -m pytest
```

### Run One Monitoring Job

```bash
python3 run_once.py
```

### Inspect SQLite Data

```bash
sqlite3 news_agent.db ".tables"
sqlite3 news_agent.db "select id, status, articles_seen, articles_new, articles_failed from runs order by id desc limit 5;"
sqlite3 news_agent.db "select title, status, relevance_score from articles order by processed_at desc limit 10;"
```

### Start Scheduler

```bash
python3 scheduler.py
```

### Start Web App

```bash
python3 app.py
```

Then open:

```text
http://127.0.0.1:5000/
```

---

## 7. Known Tradeoffs For The One-Week MVP

- Failed articles are remembered and not retried automatically. This
  keeps idempotency simple but may miss articles affected by transient
  Claude failures.
- URL normalization is intentionally minimal. Tracking parameters are
  preserved, so some near-duplicate URLs may be treated as distinct.
- RSS entry text is used as-is. The MVP does not scrape full article
  pages, so summaries depend on feed quality.
- SQLite is used directly with helper functions instead of an ORM. This
  keeps the code small and transparent for learning.
- Flask uses a simple server-rendered page. There is no filtering,
  search, pagination, or client-side interactivity.
- `failures.log` is the local alert mechanism. Real Slack/email alerts
  are documented but not implemented.
- Scheduler behavior is local-process based. Production scheduling is
  documented but not deployed.

---

## 8. Out Of Scope For The MVP

- Authentication, user accounts, or multi-user support.
- Configuration UI.
- React, frontend build tools, or a frontend API.
- Arbitrary web scraping or full article extraction.
- Background worker queues such as Celery or RQ.
- External databases.
- Cloud deployment.
- Real Slack/email alert sending.
- Automatic reprocessing of failed articles.
- Admin controls for retry, delete, edit, or re-score.
- Advanced dedup across syndicated copies with different URLs.
- Long-term monitoring dashboards, charts, or analytics.
