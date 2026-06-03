# SPEC: Scheduled Biotech News Monitoring Agent

> This spec is written in the SDD style used for AI-assisted
> implementation. It is structured so an AI tool can implement it with
> minimal ambiguity: explicit goal, non-goals, constraints, concrete
> input/output examples, edge cases, and acceptance criteria.

---

## 1. Goal

Build an autonomous agent that runs on a schedule, pulls biotech and FDA
news from RSS feeds, uses Claude to summarize and score each article for
relevance, stores the results, and shows them on a simple web page. The
agent remembers what it has already processed so it never repeats work,
and it recovers from or reports failures without a human watching.

The agent must demonstrate, concretely, four capabilities:
1. Runs on a schedule (no human trigger).
2. Handles edge cases without crashing.
3. Does not need babysitting (idempotent, self-recovering, alerts on
   failure).
4. Has the tooling and integrations built around it (data integration,
   memory, scheduler, web view, failure handling).

---

## 2. Non-goals (explicitly out of scope)

- User accounts or authentication.
- Multiple users.
- A configuration UI. Feeds and settings live in a config file.
- Web scraping of arbitrary pages. RSS only.
- Cloud deployment. A local run is acceptable for the demo, with
  production mapping documented in the README.
- A heavy frontend. The web page is a single read-only view, no React,
  no build step.

If a feature is not listed in the Goal, do not build it.

---

## 3. Constraints

- Language: Python.
- AI: Anthropic Claude API via the official `anthropic` SDK. No other AI
  provider.
- Storage: SQLite, a single local file. No external database.
- Scheduler: APScheduler for the demo. Document the cron / cloud
  scheduler mapping in the README.
- Web: Flask only, with simple templates or inline HTML. No frontend
  framework.
- Dependencies: keep minimal. Prefer the standard library where
  reasonable. Expected third-party packages: `anthropic`, `feedparser`,
  `flask`, `apscheduler`.
- The API key is read from an environment variable, never hardcoded.
- Domain logic (feeds, keywords, thresholds) lives in a config file, not
  in code, so the agent is portable to another topic without code
  changes.
- I am still building fluency in Python, so the implementation should
  include brief comments on each main component and explain any
  non-obvious Python idioms.

---

## 4. Configuration (config file, not hardcoded)

A `config.py` (or `config.yaml`) holding:
- `RSS_FEEDS`: list of RSS feed URLs.
- `RELEVANCE_KEYWORDS`: topics the agent cares about, e.g. AL
  amyloidosis, CAR-T, BCMA, FDA approval, clinical trial.
- `SCHEDULE_INTERVAL`: how often the agent runs, e.g. every 6 hours.
- `RELEVANCE_THRESHOLD`: minimum score (0 to 100) for an article to be
  shown as relevant.

---

## 5. Data model (SQLite)

Table `articles`:
- `id` TEXT PRIMARY KEY (a hash of the article URL, used for dedup).
- `title` TEXT
- `url` TEXT
- `source` TEXT (which feed it came from)
- `published_at` TEXT (from the feed if present)
- `summary` TEXT (Claude-generated, null if low relevance or failed)
- `relevance_score` INTEGER (0 to 100, Claude-generated)
- `status` TEXT ("processed", "low_relevance", or "failed")
- `processed_at` TEXT

Table `runs`:
- `id` INTEGER PRIMARY KEY AUTOINCREMENT
- `started_at` TEXT
- `finished_at` TEXT
- `articles_seen` INTEGER
- `articles_new` INTEGER
- `status` TEXT ("success" or "failed")
- `error` TEXT (null on success)

The `articles` table is the memory. Before processing an article, check
whether its id already exists. If it does, skip it.

---

## 6. Concrete input / output example

This is the contract the implementation must satisfy.

### Input: one RSS article (as parsed from a feed)
```
title:       "FDA Grants Breakthrough Therapy Designation to XYZ-100 for AL Amyloidosis"
url:         "https://example-biotech-news.com/articles/xyz-100-btd"
source:      "FierceBiotech"
published:   "2026-06-04T09:30:00Z"
content:     "Biotech company XYZ today announced the FDA has granted
              Breakthrough Therapy Designation to its lead candidate
              XYZ-100, a BCMA-targeted CAR-T therapy for relapsed AL
              amyloidosis... [full article text]"
```

### Claude call: expected structured output (JSON, exactly these fields)
```json
{
  "summary": "The FDA granted Breakthrough Therapy Designation to XYZ-100, a BCMA-targeted CAR-T therapy for relapsed AL amyloidosis. The designation is based on early clinical data and is intended to speed development.",
  "relevance_score": 92
}
```

### Stored row in `articles`
```
id:               "a3f9..." (sha256 of the url, truncated)
title:            "FDA Grants Breakthrough Therapy Designation to XYZ-100 for AL Amyloidosis"
url:              "https://example-biotech-news.com/articles/xyz-100-btd"
source:           "FierceBiotech"
published_at:     "2026-06-04T09:30:00Z"
summary:          "The FDA granted Breakthrough Therapy Designation to XYZ-100..."
relevance_score:  92
status:           "processed"
processed_at:     "2026-06-04T12:00:03Z"
```

### Web page row (rendered)
```
[92]  FDA Grants Breakthrough Therapy Designation to XYZ-100 for AL Amyloidosis
      FierceBiotech
      The FDA granted Breakthrough Therapy Designation to XYZ-100, a
      BCMA-targeted CAR-T therapy for relapsed AL amyloidosis...
```

### Low-relevance example (score below threshold)
Input: an article about an unrelated consumer-tech funding round.
Expected: Claude returns a low `relevance_score` (e.g. 8). The row is
stored with `status = "low_relevance"` and `summary = null`, so its id
is remembered and never reprocessed, but it does not appear on the web
page.

---

## 7. Agent run flow (one scheduled run)

1. Insert a `runs` row with `started_at` and status "running".
2. For each feed in `RSS_FEEDS`:
   a. Fetch and parse the feed.
   b. For each article, compute its id (hash of url).
   c. If the id already exists in `articles`, skip it.
   d. If new, call Claude with the title and content; expect JSON with
      `summary` and `relevance_score`.
   e. If `relevance_score >= RELEVANCE_THRESHOLD`, store with
      `status = "processed"`. Otherwise store with
      `status = "low_relevance"` and a null summary.
3. Update the `runs` row with `finished_at`, counts, and final status.

The agent must be idempotent: running it twice in a row creates no
duplicates and reprocesses nothing.

---

## 8. Claude integration

- Official `anthropic` Python SDK.
- One Claude call per new article.
- The prompt instructs Claude to return only JSON with exactly two
  fields: `summary` (2 to 3 sentences) and `relevance_score` (integer 0
  to 100), scored against `RELEVANCE_KEYWORDS`.
- Parse the JSON safely. If parsing fails, treat the article as failed:
  store `status = "failed"`, log it, but record the id so it is not
  retried forever.

---

## 9. Edge cases (must handle, do not skip)

- A feed URL is unreachable or errors: log it, continue with other
  feeds, do not crash the run.
- A feed returns zero new articles: a valid run, not an error.
- The Claude API call fails (network, rate limit): retry up to 3 times
  with backoff (1s, 2s, 4s). If it still fails, mark the article
  "failed" and move on.
- Claude returns malformed JSON: handle as a failed article, do not
  crash.
- The same article appears in two feeds: dedup by id, process once.
- A whole run fails (e.g. database error): record `runs.status =
  "failed"` with the error, and send a failure alert (section 10).

---

## 10. Failure alerting (no babysitting)

If an entire run fails, the agent must surface it, not fail silently.
For the demo: a clearly logged error plus a written line to
`failures.log`. The README documents how this maps to a Slack or email
alert in production. The principle: no human is watching, so failure
must be visible after the fact.

---

## 11. Web page (Flask)

A single page at `/` that:
- Reads articles with `status = "processed"`, ordered by relevance score
  then recency.
- Shows each: title (linked to url), source, relevance score, summary.
- Shows a header with the last run time and status from `runs`.
- Handles the empty state cleanly.

Simple, clean styling. No build step.

---

## 12. Acceptance criteria (definition of done)

- The agent runs on a schedule with no manual trigger.
- Running it twice produces no duplicates and reprocesses nothing
  (idempotent).
- A failing feed or a failing Claude call does not crash the run.
- A failed run is recorded in `runs` and surfaced via `failures.log`,
  not silent.
- Low-relevance articles are remembered but not shown.
- The web page shows summarized, scored, relevant articles and the last
  run status, and handles the empty state.
- The README explains what it does, how to run it, the architecture, and
  the production mapping.
- The stored output matches the contract in section 6.

---

## 13. Build order (one step at a time, verify before moving on)

1. Config file, SQLite schema, and the dedup check.
2. RSS fetching and parsing for one feed; print raw articles.
3. Claude integration: summarize and score one article, structured JSON.
4. Full run flow: fetch, dedup, process, store, record the run.
5. Edge case handling and retries.
6. The scheduler.
7. The Flask web page.
8. README and production notes.

Do not move on from a step until it works and is understood.
