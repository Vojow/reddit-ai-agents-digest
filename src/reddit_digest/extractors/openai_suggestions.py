"""OpenAI-backed suggestion generation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
from typing import Any
from typing import Protocol

from openai import OpenAI

from reddit_digest.config import RuntimeConfig
from reddit_digest.models.insight import Insight
from reddit_digest.models.post import Post
from reddit_digest.models.suggestion import Suggestion


class ResponsesClient(Protocol):
    def create(self, **kwargs: Any) -> Any:
        ...


class OpenAIClient(Protocol):
    responses: ResponsesClient


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


def build_openai_client(runtime: RuntimeConfig) -> OpenAIClient:
    return OpenAI(api_key=runtime.openai_api_key)


def generate_suggestions(
    client: OpenAIClient,
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
    response = client.responses.create(
        model=model,
        input=prompt,
    )
    parsed = json.loads(response.output_text)
    suggestions = tuple(Suggestion.from_raw(item) for item in parsed.get("suggestions", []))

    path = processed_root / "suggestions" / f"{run_date}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([item.to_dict() for item in suggestions], indent=2, sort_keys=True))
    return SuggestionResult(path=path, suggestions=suggestions)


def generate_topic_rewrites(
    client: OpenAIClient,
    *,
    model: str,
    topics: tuple[dict[str, object], ...],
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
        f"Input payload:\n{json.dumps({'topics': topics}, indent=2, sort_keys=True)}"
    )
    response = client.responses.create(
        model=model,
        input=prompt,
    )
    parsed = json.loads(response.output_text)
    rewrites = tuple(TopicRewrite.from_raw(item) for item in parsed.get("topic_rewrites", []))

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
