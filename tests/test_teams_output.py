from __future__ import annotations

from reddit_digest.models.openai_usage import OpenAIOperationUsage
from reddit_digest.models.openai_usage import OpenAIUsageSummary
from reddit_digest.outputs.teams import TeamsTopicSummary
from reddit_digest.outputs.teams import build_teams_payload
from reddit_digest.outputs.teams import publish_digest_to_teams


class FakeResponse:
    def raise_for_status(self) -> None:
        return None


class FakeSession:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object], int]] = []

    def post(self, url: str, *, json: dict[str, object], timeout: int) -> FakeResponse:
        self.calls.append((url, json, timeout))
        return FakeResponse()


def test_build_teams_payload_includes_warnings_paths_and_usage() -> None:
    payload = build_teams_payload(
        run_date="2026-03-12",
        warnings=("OPENAI QUOTA EXHAUSTED",),
        topics=(
            TeamsTopicSummary(
                title="Agent Memory Patterns",
                source_url="https://reddit.com/r/Codex/comments/post_001",
                subreddit="Codex",
                impact_score=8.75,
            ),
            TeamsTopicSummary(
                title="Eval Harnesses",
                source_url="https://reddit.com/r/ClaudeCode/comments/post_002",
                subreddit="ClaudeCode",
                impact_score=7.5,
            ),
        ),
        emerging_themes=("ai-agents", "testing"),
        watch_next=("Prompt-state snapshots", "Plan drift monitors"),
        openai_usage=OpenAIUsageSummary(
            total_calls=2,
            input_tokens=120,
            output_tokens=40,
            total_tokens=160,
            operations=(
                OpenAIOperationUsage(
                    operation="generate_openai_suggestions",
                    calls=1,
                    input_tokens=70,
                    output_tokens=20,
                    total_tokens=90,
                ),
            ),
        ),
        deterministic_report_path="reports/daily/2026-03-12.md",
        preferred_report_path="reports/daily/2026-03-12.llm.md",
        llm_report_path="reports/daily/2026-03-12.llm.md",
    )

    assert payload["title"] == "Daily Reddit Digest — 2026-03-12"
    assert payload["themeColor"] == "D83B01"
    report_section = payload["sections"][0]
    assert report_section["facts"][1]["value"] == "reports/daily/2026-03-12.llm.md"
    warnings_section = payload["sections"][1]
    assert warnings_section["activityTitle"] == "Warnings"
    topics_section = payload["sections"][2]
    assert topics_section["activityTitle"] == "Top Topics"
    assert topics_section["facts"][0]["name"] == "1. Agent Memory Patterns"
    assert "https://reddit.com/r/Codex/comments/post_001" in topics_section["facts"][0]["value"]
    watch_next_section = payload["sections"][4]
    assert watch_next_section["activityTitle"] == "Watch Next"
    assert watch_next_section["facts"][0]["name"] == "1."
    assert watch_next_section["facts"][0]["value"] == "Prompt-state snapshots"
    assert watch_next_section["facts"][1]["name"] == "2."
    assert watch_next_section["facts"][1]["value"] == "Plan drift monitors"
    usage_section = payload["sections"][-1]
    assert usage_section["facts"][3]["value"] == "160"


def test_publish_digest_to_teams_posts_expected_payload() -> None:
    session = FakeSession()

    publish_digest_to_teams(
        "https://contoso.example/webhook",
        run_date="2026-03-12",
        warnings=(),
        topics=(
            TeamsTopicSummary(
                title="Agent Memory Patterns",
                source_url="https://reddit.com/r/Codex/comments/post_001",
                subreddit="Codex",
                impact_score=8.75,
            ),
        ),
        emerging_themes=("ai-agents",),
        watch_next=("Prompt-state snapshots",),
        openai_usage=OpenAIUsageSummary.empty(),
        deterministic_report_path="reports/daily/2026-03-12.md",
        preferred_report_path="reports/daily/2026-03-12.md",
        llm_report_path=None,
        session=session,
    )

    assert session.calls[0][0] == "https://contoso.example/webhook"
    assert session.calls[0][2] == 20
    assert session.calls[0][1]["sections"][0]["facts"][2]["value"] == "reports/daily/2026-03-12.md"
    assert session.calls[0][1]["sections"][1]["facts"][0]["name"] == "1. Agent Memory Patterns"
    assert "https://reddit.com/r/Codex/comments/post_001" in session.calls[0][1]["sections"][1]["facts"][0]["value"]
