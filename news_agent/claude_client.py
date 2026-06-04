# Claude API integration: prompt builder, JSON parser, validator, retry wrapper.

import json
import time

import anthropic

import config
from news_agent.models import ArticleInput, ClaudeResult

_RETRY_DELAYS_SECONDS = (1, 2, 4)


class ClaudeValidationError(ValueError):
    """Raised when Claude output is not valid JSON or fails field validation."""


def build_prompt(article: ArticleInput, keywords: list[str]) -> str:
    keyword_text = ", ".join(keywords)
    published_at = article.published_at or "unknown"
    excerpt = article.content_excerpt or "(no excerpt available)"

    return (
        "You are analyzing a biotech news article for relevance.\n"
        "Return only JSON with exactly these fields:\n"
        '{\n  "summary": "2 to 3 sentence summary",\n'
        '  "relevance_score": 92\n}\n\n'
        "Do not include markdown, code fences, or extra fields.\n"
        f"Relevance keywords: {keyword_text}\n\n"
        f"Title: {article.title}\n"
        f"Source: {article.source}\n"
        f"Published at: {published_at}\n"
        f"Content excerpt:\n{excerpt}\n"
    )


def validate_claude_result(data: dict) -> ClaudeResult:
    if "summary" not in data:
        raise ClaudeValidationError("Missing required field: summary")
    if "relevance_score" not in data:
        raise ClaudeValidationError("Missing required field: relevance_score")

    summary = data["summary"]
    if not isinstance(summary, str) or not summary.strip():
        raise ClaudeValidationError("summary must be a non-empty string")

    score = data["relevance_score"]
    if type(score) is not int or isinstance(score, bool):
        raise ClaudeValidationError("relevance_score must be an integer")
    if score < 0 or score > 100:
        raise ClaudeValidationError("relevance_score must be between 0 and 100")

    return ClaudeResult(summary=summary.strip(), relevance_score=score)


def _extract_json_text(raw_text: str) -> str:
    text = raw_text.strip()
    if not text.startswith("```"):
        return text

    lines = text.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def parse_claude_json(raw_text: str) -> ClaudeResult:
    try:
        data = json.loads(_extract_json_text(raw_text))
    except json.JSONDecodeError as exc:
        raise ClaudeValidationError(f"Invalid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise ClaudeValidationError("Claude response must be a JSON object")

    return validate_claude_result(data)


def _request_claude(prompt: str) -> str:
    client = anthropic.Anthropic()
    message = client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def call_claude(article: ArticleInput, keywords: list[str]) -> ClaudeResult:
    prompt = build_prompt(article, keywords)
    last_error: Exception | None = None

    for attempt in range(len(_RETRY_DELAYS_SECONDS)):
        try:
            raw_text = _request_claude(prompt)
            return parse_claude_json(raw_text)
        except ClaudeValidationError:
            raise
        except Exception as exc:
            last_error = exc
            if attempt < len(_RETRY_DELAYS_SECONDS) - 1:
                time.sleep(_RETRY_DELAYS_SECONDS[attempt])

    assert last_error is not None
    raise last_error
