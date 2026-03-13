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
    subreddit: str
    impact_score: float


def publish_digest_to_teams(
    webhook_url: str,
    *,
    run_date: str,
    warnings: tuple[str, ...],
    topics: tuple[TeamsTopicSummary, ...],
    emerging_themes: tuple[str, ...],
    watch_next: tuple[str, ...],
    openai_usage: OpenAIUsageSummary,
    deterministic_report_path: str,
    preferred_report_path: str,
    llm_report_path: str | None,
    session: SessionLike | None = None,
) -> None:
    http_session = session or requests.Session()
    payload = build_teams_payload(
        run_date=run_date,
        warnings=warnings,
        topics=topics,
        emerging_themes=emerging_themes,
        watch_next=watch_next,
        openai_usage=openai_usage,
        deterministic_report_path=deterministic_report_path,
        preferred_report_path=preferred_report_path,
        llm_report_path=llm_report_path,
    )
    response = http_session.post(webhook_url, json=payload, timeout=20)
    response.raise_for_status()


def build_teams_payload(
    *,
    run_date: str,
    warnings: tuple[str, ...],
    topics: tuple[TeamsTopicSummary, ...],
    emerging_themes: tuple[str, ...],
    watch_next: tuple[str, ...],
    openai_usage: OpenAIUsageSummary,
    deterministic_report_path: str,
    preferred_report_path: str,
    llm_report_path: str | None,
) -> dict[str, Any]:
    sections: list[dict[str, Any]] = [
        {
            "activityTitle": "Report",
            "facts": [
                {"name": "Run date", "value": run_date},
                {"name": "Preferred report", "value": preferred_report_path},
                {"name": "Source of record", "value": deterministic_report_path},
                *(
                    [{"name": "LLM report", "value": llm_report_path}]
                    if llm_report_path is not None
                    else []
                ),
            ],
        },
        {
            "activityTitle": "Top Topics",
            "facts": [
                {
                    "name": f"{index}. {topic.title}",
                    "value": f"r/{topic.subreddit} · impact {topic.impact_score:.2f}",
                }
                for index, topic in enumerate(topics[:3], start=1)
            ]
            or [{"name": "Topics", "value": "No picked topics today."}],
        },
        {
            "activityTitle": "Emerging Themes",
            "facts": [
                {"name": "Themes", "value": ", ".join(emerging_themes)}
            ]
            if emerging_themes
            else [{"name": "Themes", "value": "No emerging themes today."}],
        },
        {
            "activityTitle": "Watch Next",
            "facts": [
                {"name": "Items", "value": " | ".join(watch_next)}
            ]
            if watch_next
            else [{"name": "Items", "value": "No watch-next items."}],
        },
        {
            "activityTitle": "OpenAI Usage",
            "facts": [
                {"name": "Calls", "value": str(openai_usage.total_calls)},
                {"name": "Input tokens", "value": str(openai_usage.input_tokens)},
                {"name": "Output tokens", "value": str(openai_usage.output_tokens)},
                {"name": "Total tokens", "value": str(openai_usage.total_tokens)},
            ],
        },
    ]
    if warnings:
        sections.insert(
            1,
            {
                "activityTitle": "Warnings",
                "text": "<br>".join(warnings),
            },
        )

    return {
        "@type": "MessageCard",
        "@context": "https://schema.org/extensions",
        "summary": f"Daily Reddit Digest — {run_date}",
        "themeColor": "D83B01" if warnings else "0078D4",
        "title": f"Daily Reddit Digest — {run_date}",
        "sections": sections,
    }
