# Dataclasses for internal data movement between modules.

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
