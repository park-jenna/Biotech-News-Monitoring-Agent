# Unit tests for news_agent/claude_client.py (implemented in Step 5).

import pytest

from news_agent.claude_client import (
    ClaudeValidationError,
    build_prompt,
    call_claude,
    parse_claude_json,
    validate_claude_result,
)
from news_agent.models import ArticleInput, ClaudeResult


def _sample_article() -> ArticleInput:
    return ArticleInput(
        id="article-1",
        title="FDA approves new CAR-T therapy",
        url="https://example.com/article",
        guid=None,
        source="Biotech Feed",
        published_at="2026-06-01T12:00:00+00:00",
        content_excerpt="A new therapy was approved for myeloma patients.",
    )


def test_valid_json_parses_to_claude_result():
    result = parse_claude_json(
        '{"summary": "Important FDA approval.", "relevance_score": 92}'
    )
    assert result == ClaudeResult(summary="Important FDA approval.", relevance_score=92)


def test_valid_json_with_extra_fields_is_accepted():
    result = parse_claude_json(
        '{"summary": "Relevant update.", "relevance_score": 75, "notes": "ignore me"}'
    )
    assert result.relevance_score == 75


def test_malformed_json_raises_validation_error():
    with pytest.raises(ClaudeValidationError, match="Invalid JSON"):
        parse_claude_json("{not valid json")


def test_missing_summary_raises_validation_error():
    with pytest.raises(ClaudeValidationError, match="summary"):
        validate_claude_result({"relevance_score": 50})


def test_missing_relevance_score_raises_validation_error():
    with pytest.raises(ClaudeValidationError, match="relevance_score"):
        validate_claude_result({"summary": "A summary."})


def test_empty_summary_raises_validation_error():
    with pytest.raises(ClaudeValidationError, match="summary"):
        validate_claude_result({"summary": "   ", "relevance_score": 50})


def test_string_score_raises_validation_error():
    with pytest.raises(ClaudeValidationError, match="integer"):
        validate_claude_result({"summary": "A summary.", "relevance_score": "92"})


def test_float_score_raises_validation_error():
    with pytest.raises(ClaudeValidationError, match="integer"):
        validate_claude_result({"summary": "A summary.", "relevance_score": 92.5})


def test_negative_score_raises_validation_error():
    with pytest.raises(ClaudeValidationError, match="between 0 and 100"):
        validate_claude_result({"summary": "A summary.", "relevance_score": -1})


def test_score_above_100_raises_validation_error():
    with pytest.raises(ClaudeValidationError, match="between 0 and 100"):
        validate_claude_result({"summary": "A summary.", "relevance_score": 101})


def test_parse_claude_json_strips_markdown_code_fence():
    raw = """```json
{"summary": "Fenced JSON works.", "relevance_score": 60}
```"""
    result = parse_claude_json(raw)
    assert result.summary == "Fenced JSON works."


def test_build_prompt_includes_article_fields_and_keywords():
    prompt = build_prompt(_sample_article(), ["CAR-T", "FDA approval"])
    assert "FDA approves new CAR-T therapy" in prompt
    assert "Biotech Feed" in prompt
    assert "2026-06-01T12:00:00+00:00" in prompt
    assert "myeloma patients" in prompt
    assert "CAR-T, FDA approval" in prompt
    assert '"relevance_score"' in prompt


def test_call_claude_retries_api_failures(monkeypatch):
    calls = {"count": 0}

    def fake_request(prompt: str) -> str:
        calls["count"] += 1
        if calls["count"] < 3:
            raise RuntimeError("temporary API failure")
        return '{"summary": "Recovered after retries.", "relevance_score": 88}'

    monkeypatch.setattr("news_agent.claude_client._request_claude", fake_request)
    monkeypatch.setattr("news_agent.claude_client.time.sleep", lambda _: None)

    result = call_claude(_sample_article(), ["CAR-T"])
    assert result.relevance_score == 88
    assert calls["count"] == 3


def test_call_claude_raises_after_three_api_failures(monkeypatch):
    def fake_request(prompt: str) -> str:
        raise RuntimeError("persistent API failure")

    monkeypatch.setattr("news_agent.claude_client._request_claude", fake_request)
    monkeypatch.setattr("news_agent.claude_client.time.sleep", lambda _: None)

    with pytest.raises(RuntimeError, match="persistent API failure"):
        call_claude(_sample_article(), ["CAR-T"])


def test_call_claude_does_not_retry_validation_errors(monkeypatch):
    calls = {"count": 0}

    def fake_request(prompt: str) -> str:
        calls["count"] += 1
        return '{"summary": "", "relevance_score": 50}'

    monkeypatch.setattr("news_agent.claude_client._request_claude", fake_request)
    monkeypatch.setattr("news_agent.claude_client.time.sleep", lambda _: None)

    with pytest.raises(ClaudeValidationError):
        call_claude(_sample_article(), ["CAR-T"])

    assert calls["count"] == 1
