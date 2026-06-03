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

Decided on RSS over a news API or scraping, because RSS needs no API key
and is more stable to parse than scraping arbitrary pages.

## Configuration (in a config file, not hardcoded)

- `RSS_FEEDS`: list of feed URLs
- `RELEVANCE_KEYWORDS`: topics to care about (AL amyloidosis, CAR-T,
  BCMA, FDA approval, clinical trial)
- `SCHEDULE_INTERVAL`: how often it runs
- `RELEVANCE_THRESHOLD`: minimum score (0 to 100) to show an article

## Data model (SQLite)

Table `articles`:
- `id` TEXT PRIMARY KEY (hash of url, for dedup)
- `title`, `url`, `source`, `published_at`
- `summary` (Claude-generated)
- `relevance_score` (0 to 100)
- `processed_at`

Table `runs`:
- `id`, `started_at`, `finished_at`
- `articles_seen`, `articles_new`
- `status`, `error`

The `articles` table acts as memory. Before processing, check if the id
already exists; if so, skip it.

## Run flow (one scheduled run)

1. Record a run start.
2. For each feed: fetch and parse, compute each article id, skip if
   already seen.
3. For new articles: ask Claude for a summary and relevance score.
4. Save the ones above the threshold.
5. Record the run finish with counts.

## Claude integration

- One Claude call per new article.
- Ask it to return a summary and a relevance score.

## Failure handling

- If a feed is down, keep going with the others.
- If a Claude call fails, retry, then skip that article.
- If a whole run fails, record it.

## Scheduler

- Runs automatically on `SCHEDULE_INTERVAL`, no manual trigger.
