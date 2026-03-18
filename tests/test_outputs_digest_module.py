from __future__ import annotations

from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.reddit_digest.models.insight import Insight
from src.reddit_digest.outputs.digest import _derive_specific_tool_topic_label
from src.reddit_digest.outputs.digest import DigestArtifact
from src.reddit_digest.outputs.digest import DigestThread
from src.reddit_digest.outputs.digest import EmergingTheme
from src.reddit_digest.outputs.digest import RankedTopic
from src.reddit_digest.outputs.digest import select_watch_next_items


def _insight(*, title: str, novelty: str | None) -> Insight:
    return Insight.from_raw(
        {
            "category": "tools",
            "title": title,
            "summary": "Codex is being used in practical workflows.",
            "tags": ["ai-agents", "tooling"],
            "evidence": "Codex workflow evidence",
            "source_kind": "post",
            "source_id": title.lower().replace(" ", "-"),
            "source_post_id": title.lower().replace(" ", "-"),
            "source_permalink": "https://reddit.com/r/Codex/comments/post-1",
            "subreddit": "Codex",
            "why_it_matters": "Useful for agent workflow evaluation.",
            "novelty": novelty,
        }
    )


def test_output_digest_module_derives_specific_titles() -> None:
    assert _derive_specific_tool_topic_label(
        "Codex",
        "Bad news: Codex limits were tightened again",
    ) == "Codex plan and quota changes"


def test_output_digest_module_tracks_top_thread_and_watch_next() -> None:
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
        watch_next=(),
    )

    assert digest.top_thread == digest.notable_threads[0]
    assert select_watch_next_items(
        watch_next=(),
        insights=(
            _insight(title="First", novelty="new"),
            _insight(title="Second", novelty="ongoing"),
        ),
    ) == ("First",)
