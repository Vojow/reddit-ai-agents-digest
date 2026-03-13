"""OpenAI-backed suggestion generation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
from typing import Any

from reddit_digest.models.insight import Insight
from reddit_digest.models.post import Post
from reddit_digest.models.suggestion import Suggestion
from reddit_digest.openai_client import OpenAITextClient


class OpenAIResponseError(ValueError):
    """Raised when the OpenAI response does not satisfy the expected schema."""


@dataclass(frozen=True)
class SuggestionResult:
    path: Path
    suggestions: tuple[Suggestion, ...]


@dataclass(frozen=True)
class TopicRewrite:
    topic_key: str
    executive_summary: str
    relevance_for_user: str

    @classmethod
    def from_raw(cls, payload: dict[str, Any]) -> "TopicRewrite":
        topic_key = payload.get("topic_key")
        executive_summary = payload.get("executive_summary")
        relevance_for_user = payload.get("relevance_for_user")
        if not isinstance(topic_key, str) or not topic_key:
            raise ValueError("'topic_key' must be a non-empty string")
        if not isinstance(executive_summary, str) or not executive_summary:
            raise ValueError("'executive_summary' must be a non-empty string")
        if not isinstance(relevance_for_user, str) or not relevance_for_user:
            raise ValueError("'relevance_for_user' must be a non-empty string")
        return cls(
            topic_key=topic_key,
            executive_summary=executive_summary,
            relevance_for_user=relevance_for_user,
        )


@dataclass(frozen=True)
class TopicRewriteResult:
    path: Path
    rewrites: tuple[TopicRewrite, ...]


@dataclass(frozen=True)
class TopicRewriteRequest:
    topic_key: str
    title: str
    executive_summary: str
    relevance_for_user: str
    source_title: str
    source_subreddit: str
    source_url: str
    impact_score: float
    support_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "topic_key": self.topic_key,
            "title": self.title,
            "executive_summary": self.executive_summary,
            "relevance_for_user": self.relevance_for_user,
            "source_title": self.source_title,
            "source_subreddit": self.source_subreddit,
            "source_url": self.source_url,
            "impact_score": self.impact_score,
            "support_count": self.support_count,
        }


@dataclass(frozen=True)
class ExecutiveSummaryRewriteResult:
    path: Path
    executive_summary: str


@dataclass(frozen=True)
class ExecutiveSummaryRewriteRequest:
    run_date: str
    total_posts: int
    represented_subreddits: tuple[str, ...]
    top_topic_title: str | None
    topics: tuple[TopicRewriteRequest, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_date": self.run_date,
            "total_posts": self.total_posts,
            "represented_subreddits": list(self.represented_subreddits),
            "top_topic_title": self.top_topic_title,
            "topics": [topic.to_dict() for topic in self.topics],
        }


def generate_suggestions(
    client: OpenAITextClient,
    *,
    model: str,
    posts: tuple[Post, ...],
    insights: tuple[Insight, ...],
    processed_root: Path,
    run_date: str,
) -> SuggestionResult:
    payload = {
        "posts": [post.to_dict() for post in posts[:5]],
        "insights": [insight.to_dict() for insight in insights[:10]],
    }
    prompt = (
        "You are generating advisory suggestions for tomorrow's monitoring feed. "
        "Use only the supplied Reddit findings. Do not invent same-day threads or claim external facts. "
        "Return strict JSON with a top-level key 'suggestions' containing up to 5 items. "
        "Each item must have: category ('content' or 'source'), title, rationale. "
        "Use 'content' for follow-up topics to monitor tomorrow. "
        "Use 'source' for new subreddits or topics worth watching next. "
        f"Input payload:\n{json.dumps(payload, indent=2, sort_keys=True)}"
    )
    output_text = client.create_text(
        operation="generate_openai_suggestions",
        model=model,
        input=prompt,
    )
    items = _parse_response_items(output_text, list_key="suggestions")
    suggestions = tuple(Suggestion.from_raw(item) for item in items)

    path = processed_root / "suggestions" / f"{run_date}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([item.to_dict() for item in suggestions], indent=2, sort_keys=True))
    return SuggestionResult(path=path, suggestions=suggestions)


def generate_executive_summary_rewrite(
    client: OpenAITextClient,
    *,
    model: str,
    request: ExecutiveSummaryRewriteRequest,
    processed_root: Path,
    run_date: str,
) -> ExecutiveSummaryRewriteResult:
    prompt = (
        "You are rewriting the executive summary for an AI digest. "
        "Use only the supplied deterministic digest data. "
        "Do not add external facts or change the selected topics, represented subreddits, or counts. "
        "Return strict JSON with a top-level key 'executive_summary' containing a concise 2-3 sentence summary string. "
        f"Input payload:\n{json.dumps(request.to_dict(), indent=2, sort_keys=True)}"
    )
    output_text = client.create_text(
        operation="rewrite_openai_executive_summary",
        model=model,
        input=prompt,
    )
    executive_summary = _parse_required_string(output_text, key="executive_summary")

    path = processed_root / "executive_summary_rewrites" / f"{run_date}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"executive_summary": executive_summary}, indent=2, sort_keys=True))
    return ExecutiveSummaryRewriteResult(path=path, executive_summary=executive_summary)


def generate_topic_rewrites(
    client: OpenAITextClient,
    *,
    model: str,
    requests: tuple[TopicRewriteRequest, ...],
    processed_root: Path,
    run_date: str,
) -> TopicRewriteResult:
    prompt = (
        "You are rewriting prose for an AI digest. "
        "Do not change the chosen topics, titles, links, subreddit names, scores, or counts. "
        "Use only the supplied topic data. Do not add new claims or external facts. "
        "Return strict JSON with a top-level key 'topic_rewrites' containing one item per input topic. "
        "Each item must include: topic_key, executive_summary, relevance_for_user. "
        "Keep topic_key exactly as provided. "
        f"Input payload:\n{json.dumps({'topics': [request.to_dict() for request in requests]}, indent=2, sort_keys=True)}"
    )
    output_text = client.create_text(
        operation="rewrite_openai_topics",
        model=model,
        input=prompt,
    )
    items = _parse_response_items(output_text, list_key="topic_rewrites")
    rewrites = tuple(TopicRewrite.from_raw(item) for item in items)
    _validate_topic_rewrites(rewrites, requests=requests)

    path = processed_root / "topic_rewrites" / f"{run_date}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            [
                {
                    "topic_key": item.topic_key,
                    "executive_summary": item.executive_summary,
                    "relevance_for_user": item.relevance_for_user,
                }
                for item in rewrites
            ],
            indent=2,
            sort_keys=True,
        )
    )
    return TopicRewriteResult(path=path, rewrites=rewrites)


def _parse_response_items(output_text: str, *, list_key: str) -> list[dict[str, Any]]:
    try:
        parsed = json.loads(output_text)
    except json.JSONDecodeError as exc:
        raise OpenAIResponseError("OpenAI response must be valid JSON") from exc
    if not isinstance(parsed, dict):
        raise OpenAIResponseError("OpenAI response must be a JSON object")
    items = parsed.get(list_key)
    if not isinstance(items, list):
        raise OpenAIResponseError(f"OpenAI response must include a '{list_key}' list")
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise OpenAIResponseError(f"OpenAI response item {index} in '{list_key}' must be an object")
    return items


def _parse_required_string(output_text: str, *, key: str) -> str:
    try:
        parsed = json.loads(output_text)
    except json.JSONDecodeError as exc:
        raise OpenAIResponseError("OpenAI response must be valid JSON") from exc
    if not isinstance(parsed, dict):
        raise OpenAIResponseError("OpenAI response must be a JSON object")
    value = parsed.get(key)
    if not isinstance(value, str) or not value.strip():
        raise OpenAIResponseError(f"OpenAI response must include a non-empty '{key}' string")
    return value.strip()


def _validate_topic_rewrites(
    rewrites: tuple[TopicRewrite, ...],
    *,
    requests: tuple[TopicRewriteRequest, ...],
) -> None:
    expected_keys = [request.topic_key for request in requests]

    actual_keys = [item.topic_key for item in rewrites]
    duplicate_keys = sorted({key for key in actual_keys if actual_keys.count(key) > 1})
    if duplicate_keys:
        raise OpenAIResponseError(
            f"OpenAI topic rewrites contain duplicate topic_key values: {', '.join(duplicate_keys)}"
        )

    expected_key_set = set(expected_keys)
    actual_key_set = set(actual_keys)
    missing = sorted(expected_key_set - actual_key_set)
    extra = sorted(actual_key_set - expected_key_set)
    if missing or extra:
        details: list[str] = []
        if missing:
            details.append(f"missing: {', '.join(missing)}")
        if extra:
            details.append(f"unexpected: {', '.join(extra)}")
        raise OpenAIResponseError(
            "OpenAI topic rewrites must exactly cover the deterministic topic set ("
            + "; ".join(details)
            + ")"
        )
