# Utility helpers: timestamps, URL normalization, article id hashing, text truncation.

import hashlib
from datetime import datetime, timezone
from urllib.parse import urlparse, urlunparse


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_url(url: str) -> str:
    stripped = url.strip()
    parsed = urlparse(stripped)
    return urlunparse(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path,
            parsed.params,
            parsed.query,
            "",
        )
    )


def make_article_id(url: str | None, guid: str | None) -> str | None:
    if url and url.strip():
        return hashlib.sha256(normalize_url(url).encode("utf-8")).hexdigest()
    if guid and guid.strip():
        return hashlib.sha256(guid.strip().encode("utf-8")).hexdigest()
    return None


def truncate_text(text: str, max_chars: int = 4000) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars]
