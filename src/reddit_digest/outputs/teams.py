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
            "facts": _build_topic_facts(topics),
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
            "facts": _build_watch_next_facts(watch_next),
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
def _build_topic_facts(topics: tuple[TeamsTopicSummary, ...]) -> list[dict[str, str]]:
    if not topics:
        return [{"name": "Topics", "value": "No picked topics today."}]
    return [
        {
            "name": f"{index}. {topic.title}",
            "value": f"r/{topic.subreddit} · impact {topic.impact_score:.2f} · {topic.source_url}",
        }
        for index, topic in enumerate(topics[:3], start=1)
    ]


def _build_watch_next_facts(watch_next: tuple[str, ...]) -> list[dict[str, str]]:
    if not watch_next:
        return [{"name": "Items", "value": "No watch-next items."}]
    return [{"name": f"{index}.", "value": item} for index, item in enumerate(watch_next, start=1)]
