from __future__ import annotations

from pathlib import Path
import json

import pytest

from reddit_digest.extractors.openai_suggestions import OpenAIResponseError
from reddit_digest.extractors.openai_suggestions import generate_executive_summary_rewrite
from reddit_digest.extractors.openai_suggestions import generate_suggestions
from reddit_digest.extractors.openai_suggestions import generate_topic_rewrites
from reddit_digest.models.insight import Insight
from reddit_digest.models.post import Post


class FakeClient:
    def __init__(self, output_text: str) -> None:
        self.output_text = output_text

    def create_text(self, *, operation: str, model: str, input: str) -> str:
        return self.output_text


def _suggestions_client() -> FakeClient:
    return FakeClient(
        json.dumps(
            {
                "suggestions": [
                    {
                        "category": "content",
                        "title": "Prompt-state snapshots",
                        "rationale": "Multiple threads connect reliable agent work with explicit context capture.",
                    },
                    {
                        "category": "source",
                        "title": "r/OpenHands",
                        "rationale": "The current findings suggest growing interest in broader coding-agent workflows.",
                    },
                ]
            }
        )
    )


def _rewrite_client(*, items: list[dict[str, object]]) -> FakeClient:
    return FakeClient(json.dumps({"topic_rewrites": items}))


def _executive_summary_client(*, summary: str) -> FakeClient:
    return FakeClient(json.dumps({"executive_summary": summary}))


def _sample_topics() -> tuple[dict[str, object], ...]:
    return (
        {
            "topic_key": "topic_1",
            "title": "Codex",
            "executive_summary": "Codex appears across the day's threads.",
            "relevance_for_user": "Useful for your AI-assisted development feed.",
            "source_title": "Codex agent keeps a local context file for every task",
            "source_subreddit": "Codex",
            "source_url": "https://reddit.com/r/Codex/comments/post_001",
            "impact_score": 8.7,
            "support_count": 3,
        },
        {
            "topic_key": "topic_2",
            "title": "Claude Code",
            "executive_summary": "Claude Code threads focus on real repo editing workflows.",
            "relevance_for_user": "Relevant to AI-enhanced development and testing.",
            "source_title": "Claude Code repo automation",
            "source_subreddit": "ClaudeCode",
            "source_url": "https://reddit.com/r/ClaudeCode/comments/post_002",
            "impact_score": 7.8,
            "support_count": 2,
        },
    )


def _sample_rewrites(*, include_second: bool = True) -> list[dict[str, object]]:
    items: list[dict[str, object]] = [
        {
            "topic_key": "topic_1",
            "executive_summary": "Codex threads converge on repeatable local context handling for coding agents.",
            "relevance_for_user": "This is relevant because you want a feed that highlights workflows you can reuse quickly.",
        }
    ]
    if include_second:
        items.append(
            {
                "topic_key": "topic_2",
                "executive_summary": "Claude Code discussion emphasizes practical repo editing loops instead of generic hype.",
                "relevance_for_user": "This matters because it helps separate immediately usable patterns from noise.",
            }
        )
    return items


def test_generate_suggestions_persists_structured_output(
    sample_posts_payload: list[dict[str, object]],
    tmp_path: Path,
) -> None:
    posts = tuple(Post.from_raw(item) for item in sample_posts_payload)
    insights = (
        Insight.from_raw(
            {
                "category": "tools",
                "title": "Codex",
                "summary": "Codex is being used as an agentic coding tool in real workflows.",
                "tags": ["ai-agents", "tooling"],
                "evidence": "Codex shows up across the findings.",
                "source_kind": "post",
                "source_id": "post_001",
                "source_post_id": "post_001",
                "source_permalink": "https://reddit.com/r/Codex/comments/post_001",
                "subreddit": "Codex",
                "why_it_matters": "It appears in practical coding discussions.",
                "novelty": "new",
            }
        ),
    )

    result = generate_suggestions(
        _suggestions_client(),
        model="gpt-5-mini",
        posts=posts,
        insights=insights,
        processed_root=tmp_path,
        run_date="2026-03-12",
    )

    assert [item.category for item in result.suggestions] == ["content", "source"]
    assert result.path.exists()
    assert json.loads(result.path.read_text())[0]["title"] == "Prompt-state snapshots"


def test_generate_suggestions_rejects_invalid_json(
    sample_posts_payload: list[dict[str, object]],
    tmp_path: Path,
) -> None:
    posts = tuple(Post.from_raw(item) for item in sample_posts_payload)
    insights: tuple[Insight, ...] = ()

    with pytest.raises(OpenAIResponseError, match="valid JSON"):
        generate_suggestions(
            FakeClient("{not-json"),
            model="gpt-5-mini",
            posts=posts,
            insights=insights,
            processed_root=tmp_path,
            run_date="2026-03-12",
        )


def test_generate_suggestions_requires_suggestions_list(
    sample_posts_payload: list[dict[str, object]],
    tmp_path: Path,
) -> None:
    posts = tuple(Post.from_raw(item) for item in sample_posts_payload)
    insights: tuple[Insight, ...] = ()

    with pytest.raises(OpenAIResponseError, match="'suggestions' list"):
        generate_suggestions(
            FakeClient(json.dumps({"wrong_key": []})),
            model="gpt-5-mini",
            posts=posts,
            insights=insights,
            processed_root=tmp_path,
            run_date="2026-03-12",
        )


def test_generate_topic_rewrites_persists_structured_output(tmp_path: Path) -> None:
    result = generate_topic_rewrites(
        _rewrite_client(items=_sample_rewrites()),
        model="gpt-5-mini",
        topics=_sample_topics(),
        processed_root=tmp_path,
        run_date="2026-03-12",
    )

    assert [item.topic_key for item in result.rewrites] == ["topic_1", "topic_2"]
    assert result.path.exists()
    persisted = json.loads(result.path.read_text())
    assert persisted[0]["executive_summary"].startswith("Codex threads converge")


def test_generate_topic_rewrites_requires_full_topic_coverage(tmp_path: Path) -> None:
    with pytest.raises(OpenAIResponseError, match="exactly cover the deterministic topic set"):
        generate_topic_rewrites(
            _rewrite_client(items=_sample_rewrites(include_second=False)),
            model="gpt-5-mini",
            topics=_sample_topics(),
            processed_root=tmp_path,
            run_date="2026-03-12",
        )


def test_generate_topic_rewrites_rejects_unknown_topic_keys(tmp_path: Path) -> None:
    with pytest.raises(OpenAIResponseError, match="unexpected: topic_3"):
        generate_topic_rewrites(
            _rewrite_client(
                items=[
                    *_sample_rewrites(include_second=False),
                    {
                        "topic_key": "topic_3",
                        "executive_summary": "Unexpected extra topic.",
                        "relevance_for_user": "This should be rejected.",
                    },
                ]
            ),
            model="gpt-5-mini",
            topics=_sample_topics(),
            processed_root=tmp_path,
            run_date="2026-03-12",
        )


def test_generate_topic_rewrites_rejects_duplicate_topic_keys(tmp_path: Path) -> None:
    with pytest.raises(OpenAIResponseError, match="duplicate topic_key"):
        generate_topic_rewrites(
            _rewrite_client(
                items=[
                    *_sample_rewrites(include_second=False),
                    {
                        "topic_key": "topic_1",
                        "executive_summary": "Duplicate rewrite.",
                        "relevance_for_user": "This should be rejected.",
                    },
                    {
                        "topic_key": "topic_2",
                        "executive_summary": "Claude Code discussion emphasizes practical repo editing loops instead of generic hype.",
                        "relevance_for_user": "This matters because it helps separate immediately usable patterns from noise.",
                    },
                ]
            ),
            model="gpt-5-mini",
            topics=_sample_topics(),
            processed_root=tmp_path,
            run_date="2026-03-12",
        )


def test_generate_topic_rewrites_requires_topic_rewrites_list(tmp_path: Path) -> None:
    with pytest.raises(OpenAIResponseError, match="'topic_rewrites' list"):
        generate_topic_rewrites(
            FakeClient(json.dumps({"rewrites": []})),
            model="gpt-5-mini",
            topics=_sample_topics(),
            processed_root=tmp_path,
            run_date="2026-03-12",
        )


def test_generate_executive_summary_rewrite_persists_structured_output(tmp_path: Path) -> None:
    result = generate_executive_summary_rewrite(
        _executive_summary_client(
            summary=(
                "Three topics stand out across Codex, ClaudeCode, and Vibecoding, led by headless-agent safety "
                "and tooling workflow discussions."
            )
        ),
        model="gpt-5-mini",
        summary_payload={
            "run_date": "2026-03-12",
            "total_posts": 12,
            "represented_subreddits": ("Codex", "ClaudeCode"),
            "top_topic_title": "Claude Code permission model for headless automation",
            "topics": _sample_topics(),
        },
        processed_root=tmp_path,
        run_date="2026-03-12",
    )

    assert result.executive_summary.startswith("Three topics stand out")
    assert result.path.exists()
    assert json.loads(result.path.read_text())["executive_summary"].startswith("Three topics stand out")


def test_generate_executive_summary_rewrite_requires_summary_string(tmp_path: Path) -> None:
    with pytest.raises(OpenAIResponseError, match="'executive_summary' string"):
        generate_executive_summary_rewrite(
            FakeClient(json.dumps({"summary": "wrong key"})),
            model="gpt-5-mini",
            summary_payload={"topics": _sample_topics()},
            processed_root=tmp_path,
            run_date="2026-03-12",
        )
