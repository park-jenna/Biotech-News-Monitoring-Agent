# Unit tests for news_agent/utils.py (implemented in Step 3).

from news_agent.utils import (
    make_article_id,
    normalize_url,
    truncate_text,
    utc_now_iso,
)


def test_normalize_url_strips_fragments():
    assert (
        normalize_url("https://Example.com/article?x=1#section")
        == "https://example.com/article?x=1"
    )


def test_normalize_url_lowercases_scheme_and_host():
    assert (
        normalize_url("HTTPS://WWW.Example.COM/path")
        == "https://www.example.com/path"
    )


def test_normalize_url_preserves_query_string():
    assert (
        normalize_url("https://example.com/search?q=CAR-T&page=2")
        == "https://example.com/search?q=CAR-T&page=2"
    )


def test_normalize_url_strips_whitespace():
    assert (
        normalize_url("  https://Example.com/article#frag  ")
        == "https://example.com/article"
    )


def test_same_url_with_different_fragments_normalizes_identically():
    url_a = normalize_url("https://example.com/news/1#top")
    url_b = normalize_url("https://example.com/news/1#comments")
    assert url_a == url_b


def test_make_article_id_from_url_is_stable():
    url = "https://example.com/article?ref=rss#section"
    first = make_article_id(url, None)
    second = make_article_id(url, None)
    assert first == second
    assert len(first) == 64


def test_make_article_id_from_url_ignores_fragment():
    id_with_fragment = make_article_id("https://example.com/article#a", None)
    id_without_fragment = make_article_id("https://example.com/article", None)
    assert id_with_fragment == id_without_fragment


def test_make_article_id_from_guid_when_url_missing():
    article_id = make_article_id(None, "feed-guid-12345")
    assert article_id is not None
    assert len(article_id) == 64
    assert article_id == make_article_id(None, "feed-guid-12345")


def test_make_article_id_prefers_url_over_guid():
    url_id = make_article_id("https://example.com/a", "some-guid")
    guid_only_id = make_article_id(None, "some-guid")
    assert url_id != guid_only_id


def test_make_article_id_returns_none_when_url_and_guid_missing():
    assert make_article_id(None, None) is None
    assert make_article_id("", "") is None
    assert make_article_id("   ", "   ") is None


def test_truncate_text_returns_original_when_short_enough():
    text = "short excerpt"
    assert truncate_text(text) == text


def test_truncate_text_truncates_long_text():
    text = "a" * 5000
    result = truncate_text(text, max_chars=4000)
    assert len(result) == 4000
    assert result == "a" * 4000


def test_utc_now_iso_returns_utc_string():
    timestamp = utc_now_iso()
    assert timestamp.endswith("+00:00") or timestamp.endswith("Z")
    assert "T" in timestamp
