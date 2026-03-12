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
