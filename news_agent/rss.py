# RSS fetching and parsing. Uses only RSS entry fields; never fetches linked pages.

from datetime import datetime, timezone

import feedparser

from news_agent.models import ArticleInput
from news_agent.logging_utils import log_feed_warning
from news_agent.utils import make_article_id, truncate_text


def fetch_feed(feed_url: str) -> feedparser.FeedParserDict:
    return feedparser.parse(feed_url)


def extract_content_excerpt(entry) -> str:
    content = entry.get("content")
    if content:
        for part in content:
            value = part.get("value")
            if value:
                return truncate_text(str(value).strip())

    for field in ("summary", "description"):
        value = entry.get(field)
        if value:
            return truncate_text(str(value).strip())

    return ""


def parse_published_at(entry) -> str | None:
    parsed_time = entry.get("published_parsed") or entry.get("updated_parsed")
    if not parsed_time:
        return None

    dt = datetime(*parsed_time[:6], tzinfo=timezone.utc)
    return dt.replace(microsecond=0).isoformat()


def _looks_like_url(value: str) -> bool:
    lowered = value.lower()
    return lowered.startswith("http://") or lowered.startswith("https://")


def _entry_url(entry) -> str | None:
    link = entry.get("link")
    if link is None:
        return None
    stripped = str(link).strip()
    if not stripped or not _looks_like_url(stripped):
        return None
    return stripped


def _entry_guid(entry) -> str | None:
    guid = entry.get("id") or entry.get("guid")
    if guid is None:
        return None
    stripped = str(guid).strip()
    return stripped or None


def _entry_title(entry) -> str:
    title = entry.get("title")
    if title is None:
        return "(untitled)"
    stripped = str(title).strip()
    return stripped or "(untitled)"


def _feed_source(parsed_feed, feed_url: str) -> str:
    feed_title = parsed_feed.get("feed", {}).get("title")
    if feed_title:
        stripped = str(feed_title).strip()
        if stripped:
            return stripped
    return feed_url


def parse_feed(feed_url: str, parsed_feed) -> list[ArticleInput]:
    source = _feed_source(parsed_feed, feed_url)
    articles: list[ArticleInput] = []

    for entry in parsed_feed.get("entries", []):
        url = _entry_url(entry)
        guid = _entry_guid(entry)
        article_id = make_article_id(url, guid)
        if article_id is None:
            log_feed_warning(
                feed_url,
                f"Skipping entry without URL or GUID: {_entry_title(entry)}",
            )
            continue

        articles.append(
            ArticleInput(
                id=article_id,
                title=_entry_title(entry),
                url=url,
                guid=guid,
                source=source,
                published_at=parse_published_at(entry),
                content_excerpt=extract_content_excerpt(entry),
            )
        )

    return articles
