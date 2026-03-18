from __future__ import annotations

from pathlib import Path

import pytest

from reddit_digest.models.base import ModelError
from reddit_digest.models.digest import DigestItem
from reddit_digest.models.insight import Insight
from reddit_digest.outputs.digest import _canonicalize_theme_tag
from reddit_digest.outputs.digest import _clean_theme_title
from reddit_digest.outputs.digest import _derive_specific_tool_topic_label
from reddit_digest.outputs.digest import _normalize_theme_title
from reddit_digest.outputs.digest import _resolve_topic_relevance
from reddit_digest.outputs.digest import _resolve_topic_summary
from reddit_digest.outputs.digest import DigestArtifact
from reddit_digest.outputs.digest import DigestThread
from reddit_digest.outputs.digest import EmergingTheme
from reddit_digest.outputs.digest import RankedTopic
from reddit_digest.outputs.digest import select_watch_next_items
from reddit_digest.outputs.markdown import _build_output_paths


def test_digest_helpers_cover_generic_topic_paths() -> None:
    insight = Insight.from_raw(
        {
            "category": "tools",
            "title": "Codex",
            "summary": "Codex is being used in practical workflows.",
            "tags": ["ai-agents", "tooling"],
            "evidence": "Codex workflow evidence",
            "source_kind": "post",
            "source_id": "post-1",
            "source_post_id": "post-1",
            "source_permalink": "https://reddit.com/r/Codex/comments/post-1",
            "subreddit": "Codex",
            "why_it_matters": "Useful for agent workflow evaluation.",
            "novelty": "new",
        }
    )

    assert _canonicalize_theme_tag("coding-agents") == "ai-agents"
    assert _normalize_theme_title("  Codex   Limits ") == "codex limits"
    assert _clean_theme_title("  Codex   Limits ") == "Codex Limits"
    assert _derive_specific_tool_topic_label("Codex", "Bad news: Codex limits are tighter") == "Codex plan and quota changes"

    quota_title = "Codex plan and quota changes"
    assert _resolve_topic_summary(insight, topic_title=quota_title).startswith("Threads focus on usage limits")
    assert _resolve_topic_relevance(insight, topic_title=quota_title).startswith("Useful for planning tool usage")
    assert select_watch_next_items(watch_next=("Use explicit list",), insights=(insight,)) == ("Use explicit list",)


def test_digest_artifact_top_thread_and_markdown_paths() -> None:
    topic = RankedTopic(
        topic_key="topic_1",
        title="Codex plan and quota changes",
        executive_summary="summary",
        relevance_for_user="relevance",
        source_title="Original thread",
        source_url="https://reddit.com/t1",
        source_subreddit="Codex",
        impact_score=8.8,
        support_count=2,
    )
    digest = DigestArtifact(
        run_date="2026-03-13",
        total_posts=4,
        total_insights=3,
        represented_subreddits=("Codex", "ClaudeCode"),
        top_topic_title=topic.title,
        top_tool="Codex",
        top_approach="Context snapshots",
        top_guide="Prompt recovery checklist",
        top_testing_insight="Deterministic prompting",
        topics=(topic,),
        notable_threads=(
            DigestThread(title="Thread 1", url="https://reddit.com/t1", subreddit="Codex", impact_score=8.2),
        ),
        emerging_themes=(
            EmergingTheme(
                label="Ai Agents",
                evidence="Codex workflow, Claude Code workflow",
                support_count=2,
                total_impact=16.0,
                evidence_titles=("Codex workflow", "Claude Code workflow"),
            ),
        ),
        watch_next=("Watch one",),
    )

    daily_path, latest_path = _build_output_paths(
        reports_root=Path("/tmp/reports"),
        run_date="2026-03-13",
        variant_suffix="llm",
    )

    assert digest.top_thread == digest.notable_threads[0]
    assert daily_path == Path("/tmp/reports/daily/2026-03-13.llm.md")
    assert latest_path == Path("/tmp/reports/latest.llm.md")


def test_digest_item_normalizes_evidence_and_validates_impact_score() -> None:
    item = DigestItem.from_raw(
        {
            "category": "tools",
            "title": "Codex",
            "subreddit": "Codex",
            "permalink": "https://reddit.com/r/Codex/comments/post-1",
            "why_it_matters": "Useful for testing.",
            "impact_score": 1,
            "tags": ["ai-agents"],
            "source_post_ids": ["post-1"],
            "evidence": "  concrete evidence  ",
        }
    )

    assert item.evidence == "concrete evidence"

    with pytest.raises(ModelError, match="must be greater than or equal to 0"):
        DigestItem.from_raw(
            {
                "category": "tools",
                "title": "Codex",
                "subreddit": "Codex",
                "permalink": "https://reddit.com/r/Codex/comments/post-1",
                "why_it_matters": "Useful for testing.",
                "impact_score": -0.1,
                "tags": ["ai-agents"],
                "source_post_ids": ["post-1"],
            }
        )
