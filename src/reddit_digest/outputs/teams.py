"""Microsoft Teams webhook publisher."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from typing import Protocol

import requests

from reddit_digest.models.openai_usage import OpenAIUsageSummary


class ResponseLike(Protocol):
    def raise_for_status(self) -> None:
        ...


class SessionLike(Protocol):
    def post(self, url: str, *, json: dict[str, Any], timeout: int) -> ResponseLike:
        ...


@dataclass(frozen=True)
class TeamsTopicSummary:
    title: str
    source_url: str
    subreddit: str
    impact_score: float


@dataclass(frozen=True)
class TeamsDigestPayload:
    run_date: str
    warnings: tuple[str, ...]
    topics: tuple[TeamsTopicSummary, ...]
    emerging_themes: tuple[str, ...]
    watch_next: tuple[str, ...]
    openai_usage: OpenAIUsageSummary
    selected_report_variant: str
    preferred_executive_summary: str | None


def publish_digest_to_teams(
    webhook_url: str,
    payload: TeamsDigestPayload,
    *,
    session: SessionLike | None = None,
) -> None:
    http_session = session or requests.Session()
    response = http_session.post(webhook_url, json=build_teams_payload(payload), timeout=20)
    response.raise_for_status()


def build_teams_payload(payload: TeamsDigestPayload) -> dict[str, Any]:
    sections: list[dict[str, Any]] = [
        {
            "activityTitle": "Report",
            "facts": [
                {"name": "Run date", "value": payload.run_date},
                {"name": "Selected report", "value": payload.selected_report_variant},
                *(
                    [{"name": "Executive summary", "value": payload.preferred_executive_summary}]
                    if payload.preferred_executive_summary is not None
                    else []
                ),
            ],
        },
        {
            "activityTitle": "Top Topics",
            "facts": _build_topic_facts(payload.topics),
        },
        {
            "activityTitle": "Emerging Themes",
            "facts": [
                {"name": "Themes", "value": ", ".join(payload.emerging_themes)}
            ]
            if payload.emerging_themes
            else [{"name": "Themes", "value": "No emerging themes today."}],
        },
        {
            "activityTitle": "Watch Next",
            "facts": _build_watch_next_facts(payload.watch_next),
        },
        {
            "activityTitle": "OpenAI Usage",
            "facts": [
                {"name": "Calls", "value": str(payload.openai_usage.total_calls)},
                {"name": "Input tokens", "value": str(payload.openai_usage.input_tokens)},
                {"name": "Output tokens", "value": str(payload.openai_usage.output_tokens)},
                {"name": "Total tokens", "value": str(payload.openai_usage.total_tokens)},
            ],
        },
    ]
    if payload.warnings:
        sections.insert(
            1,
            {
                "activityTitle": "Warnings",
                "text": "<br>".join(payload.warnings),
            },
        )

    return {
        "@type": "MessageCard",
        "@context": "https://schema.org/extensions",
        "summary": f"Daily Reddit Digest — {payload.run_date}",
        "themeColor": "D83B01" if payload.warnings else "0078D4",
        "title": f"Daily Reddit Digest — {payload.run_date}",
        "sections": sections,
    }


def _build_topic_facts(topics: tuple[TeamsTopicSummary, ...]) -> list[dict[str, str]]:
    if not topics:
        return [{"name": "Topics", "value": "No picked topics today."}]
    return [
        {
            "name": f"{index}. {topic.title}",
            "value": f"r/{topic.subreddit} · impact {topic.impact_score:.2f} · {topic.source_url}",
        }
        for index, topic in enumerate(topics, start=1)
    ]


def _build_watch_next_facts(watch_next: tuple[str, ...]) -> list[dict[str, str]]:
    if not watch_next:
        return [{"name": "Items", "value": "No watch-next items."}]
    return [{"name": f"{index}.", "value": item} for index, item in enumerate(watch_next, start=1)]


def extract_executive_summary(content: str) -> str | None:
    lines = iter(content.splitlines())
    for line in lines:
        if line.strip() == "## Executive Summary":
            for candidate in lines:
                stripped = candidate.strip()
                if not stripped:
                    continue
                if stripped.startswith("## "):
                    return None
                if stripped.startswith("- "):
                    return stripped[2:].strip() or None
            return None
    return None
