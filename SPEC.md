# SPEC: Scheduled Biotech News Monitoring Agent

## Goal

An agent that runs on a schedule, pulls biotech and FDA news from RSS
feeds, uses Claude to summarize and score each article for relevance,
stores the results, and shows them on a simple web page. It runs on its
own instead of me checking news by hand.

## Tech stack

- Language: Python
- AI: Anthropic Claude API (official `anthropic` SDK)
- Storage: SQLite (single local file)
- Scheduler: APScheduler for the demo
- Web: Flask, simple page

RSS chosen over a news API or scraping: no API key, stable to parse.

## Configuration (config file, not hardcoded)

- `RSS_FEEDS`, `RELEVANCE_KEYWORDS`, `SCHEDULE_INTERVAL`,
  `RELEVANCE_THRESHOLD`

## Data model (SQLite)

Table `articles`:
- `id` TEXT PRIMARY KEY (hash of url, for dedup)
- `title`, `url`, `source`, `published_at`
- `summary` (null if low relevance or failed)
- `relevance_score` (0 to 100)
- `status` ("processed", "low_relevance", "failed")
- `processed_at`

Table `runs`:
- `id`, `started_at`, `finished_at`, `articles_seen`, `articles_new`,
  `status`, `error`

The `articles` table is the memory. Skip any id that already exists.

## Concrete input / output example (the contract)

### Input: one parsed RSS article
```
title:     "FDA Grants Breakthrough Therapy Designation to XYZ-100 for AL Amyloidosis"
url:       "https://example-biotech-news.com/articles/xyz-100-btd"
source:    "FierceBiotech"
published: "2026-06-04T09:30:00Z"
content:   "Biotech company XYZ today announced the FDA has granted
            Breakthrough Therapy Designation to its lead candidate
            XYZ-100, a BCMA-targeted CAR-T therapy... [full text]"
```

### Claude output (JSON, exactly these fields)
```json
{
  "summary": "The FDA granted Breakthrough Therapy Designation to XYZ-100, a BCMA-targeted CAR-T therapy for relapsed AL amyloidosis. It is intended to speed development based on early clinical data.",
  "relevance_score": 92
}
```

### Stored row in `articles`
```
id:              "a3f9..."  (sha256 of url, truncated)
title:           "FDA Grants Breakthrough Therapy Designation to XYZ-100..."
url:             "https://example-biotech-news.com/articles/xyz-100-btd"
source:          "FierceBiotech"
published_at:    "2026-06-04T09:30:00Z"
summary:         "The FDA granted Breakthrough Therapy Designation..."
relevance_score: 92
status:          "processed"
processed_at:    "2026-06-04T12:00:03Z"
```

### Low-relevance example
Input: an unrelated consumer-tech funding article.
Expected: Claude returns a low score (e.g. 8). Stored with
`status = "low_relevance"` and `summary = null`, so its id is remembered
and not reprocessed, but it does not appear on the web page.

## Run flow (one scheduled run)

1. Record a run start.
2. For each feed: fetch, parse, compute id, skip if already seen.
3. New article: call Claude, expect the JSON above.
4. Score at or above threshold -> store as "processed". Below ->
   "low_relevance", null summary.
5. Record run finish with counts.

Must be idempotent: running twice creates no duplicates.

## Claude integration

- One call per new article.
- Prompt must return only the JSON above (summary + relevance_score).
- Parse safely. Malformed JSON -> treat article as "failed", record id
  so it is not retried forever.

## Failure handling

- Feed down: continue with other feeds.
- Claude call fails: retry 3 times with backoff (1s, 2s, 4s), then mark
  "failed".
- Whole run fails: record `runs.status = "failed"` with the error.

## Scheduler

- Runs automatically on `SCHEDULE_INTERVAL`, no manual trigger.

## Web page (Flask)

- One page showing "processed" articles, ordered by score then recency:
  title (linked), source, score, summary.
- Header shows last run time and status.
- Clean empty state.
