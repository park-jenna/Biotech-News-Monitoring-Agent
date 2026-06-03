# SPEC: Scheduled Biotech News Monitoring Agent

> This spec is written in the SDD style used for AI-assisted
> implementation. It is structured so an AI tool can implement the MVP
> with minimal ambiguity: explicit goal, non-goals, runtime commands,
> concrete data contracts, edge cases, and acceptance criteria.

---

## 1. Goal And Demo Definition

Build a local MVP of an autonomous agent that monitors biotech and FDA
news from RSS feeds on a schedule, uses Claude to summarize and score
new articles for relevance, stores results in SQLite, and shows relevant
articles on a simple Flask web page.

For the local demo, a human may start the long-running scheduler process,
but each monitoring run after startup must be triggered by APScheduler,
not by a human clicking a button or manually running the job.

The agent must demonstrate these capabilities:
1. Scheduled execution after process startup.
2. RSS data integration.
3. SQLite memory so already-seen articles are not reprocessed.
4. Claude-based summarization and relevance scoring.
5. Failure handling that records problems and continues when possible.
6. A read-only web view for the latest relevant articles and run status.

---

## 2. Non-Goals

- User accounts or authentication.
- Multiple users.
- A configuration UI. Feeds and settings live in `config.py`.
- Web scraping of arbitrary article pages.
- Fetching full article text outside the RSS entry payload.
- Cloud deployment. A local run is acceptable for the demo.
- Real Slack or email alert integration. Production alert mapping is
  documented in the README only.
- A heavy frontend. The web page is a single read-only Flask view with
  simple HTML/CSS, no React, and no build step.

If a feature is not listed in the goal or acceptance criteria, do not
build it for the MVP.

---

## 3. Runtime Commands And Environment Variables

The implementation must expose these local commands:

- `python run_once.py`: initialize storage if needed and execute one
  monitoring run immediately.
- `python scheduler.py`: start APScheduler and execute monitoring runs
  on the configured interval.
- `python app.py`: start the Flask web app.

The Anthropic API key must be read from:

```text
ANTHROPIC_API_KEY
```

The API key must never be hardcoded or committed.

If `ANTHROPIC_API_KEY` is missing when a run needs Claude, the run must
fail clearly, record the failure in `runs`, and write the global failure
to `failures.log`.

All timestamps stored by the application must be UTC ISO-8601 strings.

---

## 4. Configuration

Use `config.py` as the only configuration file. Do not add YAML support
for the MVP.

`config.py` must define:

- `RSS_FEEDS`: list of RSS feed URLs.
- `RELEVANCE_KEYWORDS`: topics the agent cares about, for example
  `AL amyloidosis`, `CAR-T`, `BCMA`, `FDA approval`, `clinical trial`.
- `SCHEDULE_INTERVAL_HOURS`: how often the scheduled agent runs.
- `RELEVANCE_THRESHOLD`: minimum score from `0` to `100` for an article
  to be shown as relevant.
- `DATABASE_PATH`: path to the SQLite database file.
- `FAILURE_LOG_PATH`: path to `failures.log`.

Domain logic such as feeds, keywords, and thresholds must live in
`config.py`, not be hardcoded in processing logic.

---

## 5. Data Model

Use SQLite with a single local database file.

### Table: `articles`

- `id` TEXT PRIMARY KEY
- `title` TEXT
- `url` TEXT
- `source` TEXT
- `published_at` TEXT
- `content_excerpt` TEXT
- `summary` TEXT
- `relevance_score` INTEGER
- `status` TEXT
- `error` TEXT
- `created_at` TEXT
- `processed_at` TEXT

Allowed `articles.status` values:

- `"processed"`: Claude returned valid output and
  `relevance_score >= RELEVANCE_THRESHOLD`.
- `"low_relevance"`: Claude returned valid output but
  `relevance_score < RELEVANCE_THRESHOLD`; `summary` must be null.
- `"failed"`: article-level processing failed; `error` must explain why.

The `articles` table is the memory. Before processing an article, check
whether its `id` already exists. If it exists, skip the article and do
not call Claude again.

### Table: `runs`

- `id` INTEGER PRIMARY KEY AUTOINCREMENT
- `started_at` TEXT
- `finished_at` TEXT
- `articles_seen` INTEGER
- `articles_new` INTEGER
- `articles_failed` INTEGER
- `status` TEXT
- `error` TEXT

Allowed `runs.status` values:

- `"running"`: run row has been created and processing has started.
- `"success"`: run completed with no feed-level, article-level, or
  global failures.
- `"partial_success"`: run completed, but one or more feeds or articles
  failed.
- `"failed"`: a global failure prevented the run from completing, for
  example a database error or missing required API key.

---

## 6. Article Identity And Dedup Policy

Article identity must be deterministic and stable across runs.

Dedup rules:

1. If an RSS entry has a URL, normalize the URL and use a SHA-256 hash of
   the normalized URL as `articles.id`.
2. If no URL exists but the entry has a GUID/id, use a SHA-256 hash of
   the GUID/id as `articles.id`.
3. If neither URL nor GUID/id exists, skip the entry and log a
   feed-level warning. Do not call Claude.

Minimum URL normalization for the MVP:

- Strip leading and trailing whitespace.
- Remove URL fragments.
- Preserve query strings.
- Lowercase the scheme and host.

If the same article appears in multiple feeds, the first seen copy is
processed and stored. Later copies are skipped because their `id`
already exists.

Failed articles are remembered and are not retried automatically in the
MVP. This prevents a bad article or bad model response from being retried
forever.

---

## 7. RSS Input Contract

The agent must use RSS entry fields only. It must not fetch or scrape
the linked article page.

For each RSS entry, extract:

- `title`: entry title if present, otherwise `"(untitled)"`.
- `url`: entry link if present.
- `guid`: entry id/guid if present.
- `source`: feed title if available, otherwise the feed URL.
- `published_at`: parsed feed timestamp if available, otherwise null.
- `content_excerpt`: text from RSS content/summary fields, truncated to
  a reasonable length for storage and Claude input.

If an entry has no useful content beyond title and URL, still process it
with the available title and metadata.

---

## 8. Agent Run Flow

One monitoring run must follow this flow:

1. Insert a `runs` row with `started_at`, `status = "running"`, and zero
   counts.
2. Validate required runtime configuration, including
   `ANTHROPIC_API_KEY`.
3. For each feed in `RSS_FEEDS`:
   - Fetch and parse the feed.
   - If the feed is unreachable or malformed, log the feed failure,
     count it as a partial failure, and continue to the next feed.
   - For each entry, compute its article id using the dedup policy.
   - Increment `articles_seen` for entries with enough identity data to
     consider.
   - If the id already exists in `articles`, skip it.
   - If the id is new, call Claude with the article title, source,
     published date, content excerpt, and relevance keywords.
   - Validate Claude's JSON response.
   - Store the article as `"processed"`, `"low_relevance"`, or
     `"failed"`.
4. Update the `runs` row with `finished_at`, counts, final status, and
   error text if applicable.

The run is idempotent: running it twice in a row with unchanged feeds
must create no duplicate articles and must not call Claude for articles
already present in SQLite.

---

## 9. Claude Integration And Response Validation

Use the official `anthropic` Python SDK. No other AI provider is allowed.

The implementation must make one Claude call per new article.

The prompt must instruct Claude to return only JSON with exactly these
fields:

```json
{
  "summary": "2 to 3 sentence summary",
  "relevance_score": 92
}
```

Validation rules:

- The response must parse as JSON.
- The JSON must include `summary` and `relevance_score`.
- `summary` must be a non-empty string.
- `relevance_score` must be an integer from `0` to `100`.
- Extra fields may be ignored, but missing or invalid required fields
  make the article fail.

Claude API failures must be retried up to three times with backoff
delays of `1s`, `2s`, and `4s`. If all attempts fail, store the article
with `status = "failed"` and an `error` message, then continue the run.

Malformed or invalid Claude output is an article-level failure. Store the
article as `"failed"`, record the error, and continue the run.

---

## 10. Failure Handling And Logging

The agent must not fail silently.

Failure categories:

- Feed failure: log the feed URL and error, continue with other feeds,
  and finish the run as `"partial_success"` if anything else completes.
- Article/Claude failure: store the article with `status = "failed"`,
  record `articles.error`, increment `runs.articles_failed`, and
  continue the run.
- Global run failure: mark the run as `"failed"` when possible and write
  to `failures.log`.

Global run failures include:

- Missing `ANTHROPIC_API_KEY`.
- SQLite/database errors that prevent normal run recording or article
  storage.
- Unexpected top-level exceptions that stop the run.

For the demo, global run failure alerting means:

- Write a clear error to application logs.
- Append one line to `FAILURE_LOG_PATH`.

Each `failures.log` line must include at least:

- UTC timestamp.
- Run id if one exists.
- Error message.

The README must document how this local failure log maps to Slack or
email alerting in production.

---

## 11. Scheduler Behavior

Use APScheduler for the local scheduled demo.

Scheduler requirements:

- The scheduler interval comes from `config.py`.
- The scheduler must trigger monitoring runs without a human manually
  starting each run.
- Scheduled runs must not overlap. If a run is still in progress when
  the next interval fires, the next run must be skipped or coalesced.
- The README must document how the APScheduler setup maps to cron or a
  cloud scheduler in production.

---

## 12. Flask Web Page

Expose one read-only page at `/`.

The page must:

- Read articles with `status = "processed"`.
- Order articles by `relevance_score` descending, then `published_at`
  descending when available.
- Show each article's title linked to `url`, source, relevance score,
  summary, and published date when available.
- Show a header with the latest run time and latest run status.
- Render cleanly when there are no articles.
- Render cleanly before any run exists.

Simple, clean styling is enough. Do not add a frontend framework or
build step.

---

## 13. Acceptance Criteria

- `python run_once.py` initializes storage if needed and executes one
  monitoring run.
- `python scheduler.py` starts scheduled monitoring using APScheduler.
- `python app.py` starts a Flask app with a working `/` page.
- The agent runs scheduled jobs after process startup without a manual
  trigger for each run.
- Running the agent twice with unchanged feeds creates no duplicate
  articles and does not call Claude for already-seen articles.
- A failing feed does not crash the run; other feeds continue.
- If one feed fails and another feed succeeds, the run finishes as
  `"partial_success"`.
- A failing Claude call is retried up to three times, then the article is
  stored as `"failed"` and the run continues.
- Claude malformed JSON, missing fields, wrong field types, or a
  relevance score outside `0..100` stores the article as `"failed"` and
  records an error.
- Low-relevance articles are remembered with `status = "low_relevance"`
  and are not shown on the web page.
- Relevant articles are stored with `status = "processed"` and appear on
  the web page.
- Same-URL articles from multiple feeds create one article row.
- Entries with no URL and no GUID/id are skipped and logged without
  calling Claude.
- Missing `ANTHROPIC_API_KEY` records a failed run and appends a line to
  `failures.log`.
- Global run failures are recorded in `runs` when possible and surfaced
  via `failures.log`.
- `failures.log` entries include timestamp, run id if available, and
  error message.
- Scheduled runs do not overlap.
- The web page handles an empty database and no previous runs.
- The web page shows summarized, scored, relevant articles and latest
  run status.
- The README explains what the project does, how to run each command,
  the architecture, the config file, and the production mapping for
  scheduler and alerts.

---

## 14. Build Order

Build one step at a time and verify each step before moving on.

1. `config.py`, SQLite schema, timestamp helper, and dedup id helper.
2. Database initialization and article/run insert/update functions.
3. RSS fetching and parsing for one feed, using RSS entry fields only.
4. Claude integration for one article with strict JSON validation.
5. Full `run_once.py` flow: fetch, dedup, process, store, and record run.
6. Edge case handling: feed failures, Claude retries, malformed Claude
   output, missing identity fields, and missing API key.
7. `scheduler.py` with APScheduler and no overlapping runs.
8. `app.py` Flask page with empty-state handling.
9. README with usage, architecture, and production scheduler/alert
   mapping.

The implementation should include brief comments on each main component
and explain non-obvious Python idioms, because the project is intended
to support Python learning as well as demonstrate the agent.
