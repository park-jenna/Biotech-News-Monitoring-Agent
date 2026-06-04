# Unit tests for news_agent/rss.py (implemented in Step 4).

import feedparser

from news_agent.models import ArticleInput
from news_agent.rss import (
    extract_content_excerpt,
    parse_feed,
    parse_published_at,
)
from news_agent.utils import make_article_id


def _parse_rss(xml: str) -> feedparser.FeedParserDict:
    return feedparser.parse(xml)


def test_parse_feed_returns_article_input_objects():
    parsed = _parse_rss(
        """
        <rss version="2.0">
          <channel>
            <title>Biotech Feed</title>
            <item>
              <title>CAR-T trial update</title>
              <link>https://example.com/car-t-trial</link>
              <guid>guid-1</guid>
              <pubDate>Mon, 01 Jun 2026 12:00:00 GMT</pubDate>
              <description>Trial results look promising.</description>
            </item>
          </channel>
        </rss>
        """
    )

    articles = parse_feed("https://example.com/feed.xml", parsed)

    assert len(articles) == 1
    assert isinstance(articles[0], ArticleInput)
    assert articles[0].title == "CAR-T trial update"
    assert articles[0].url == "https://example.com/car-t-trial"
    assert articles[0].guid == "guid-1"
    assert articles[0].source == "Biotech Feed"
    assert articles[0].published_at is not None
    assert articles[0].content_excerpt == "Trial results look promising."
    assert articles[0].id == make_article_id(
        "https://example.com/car-t-trial", "guid-1"
    )


def test_missing_title_becomes_untitled():
    parsed = _parse_rss(
        """
        <rss version="2.0">
          <channel>
            <title>Feed</title>
            <item>
              <link>https://example.com/no-title</link>
            </item>
          </channel>
        </rss>
        """
    )

    articles = parse_feed("https://example.com/feed.xml", parsed)
    assert len(articles) == 1
    assert articles[0].title == "(untitled)"


def test_missing_feed_title_uses_feed_url_as_source():
    parsed = _parse_rss(
        """
        <rss version="2.0">
          <channel>
            <item>
              <title>Article</title>
              <link>https://example.com/article</link>
            </item>
          </channel>
        </rss>
        """
    )

    feed_url = "https://example.com/feed.xml"
    articles = parse_feed(feed_url, parsed)
    assert len(articles) == 1
    assert articles[0].source == feed_url


def test_missing_url_with_guid_is_accepted():
    parsed = _parse_rss(
        """
        <rss version="2.0">
          <channel>
            <title>Feed</title>
            <item>
              <title>GUID only</title>
              <guid>unique-guid-42</guid>
              <description>Content via guid.</description>
            </item>
          </channel>
        </rss>
        """
    )

    articles = parse_feed("https://example.com/feed.xml", parsed)
    assert len(articles) == 1
    assert articles[0].url is None
    assert articles[0].guid == "unique-guid-42"
    assert articles[0].id == make_article_id(None, "unique-guid-42")


def test_missing_url_and_guid_is_skipped():
    parsed = _parse_rss(
        """
        <rss version="2.0">
          <channel>
            <title>Feed</title>
            <item>
              <title>No identity</title>
              <description>Should be skipped.</description>
            </item>
            <item>
              <title>Has link</title>
              <link>https://example.com/kept</link>
            </item>
          </channel>
        </rss>
        """
    )

    articles = parse_feed("https://example.com/feed.xml", parsed)
    assert len(articles) == 1
    assert articles[0].title == "Has link"


def test_extract_content_excerpt_prefers_content_over_summary():
    entry = feedparser.FeedParserDict(
        {
            "content": [{"value": "Full content body."}],
            "summary": "Short summary.",
        }
    )
    assert extract_content_excerpt(entry) == "Full content body."


def test_extract_content_excerpt_falls_back_to_summary():
    entry = feedparser.FeedParserDict({"summary": "Summary text."})
    assert extract_content_excerpt(entry) == "Summary text."


def test_extract_content_excerpt_returns_empty_when_missing():
    entry = feedparser.FeedParserDict({})
    assert extract_content_excerpt(entry) == ""


def test_parse_published_at_returns_utc_iso_string():
    entry = feedparser.FeedParserDict(
        {"published_parsed": (2026, 6, 1, 12, 0, 0, 0, 0, 0)}
    )
    assert parse_published_at(entry) == "2026-06-01T12:00:00+00:00"


def test_parse_published_at_returns_none_when_missing():
    entry = feedparser.FeedParserDict({})
    assert parse_published_at(entry) is None
