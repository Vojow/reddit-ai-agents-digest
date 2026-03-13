from __future__ import annotations

from pathlib import Path
import json

from reddit_digest.extractors.openai_suggestions import generate_suggestions
from reddit_digest.extractors.openai_suggestions import generate_topic_rewrites
from reddit_digest.models.insight import Insight
from reddit_digest.models.post import Post


class FakeResponses:
    def create(self, **kwargs):
        class Response:
            output_text = json.dumps(
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

        return Response()


class FakeClient:
    responses = FakeResponses()


class FakeRewriteResponses:
    def create(self, **kwargs):
        class Response:
            output_text = json.dumps(
                {
                    "topic_rewrites": [
                        {
                            "topic_key": "topic_1",
                            "executive_summary": "Codex threads converge on repeatable local context handling for coding agents.",
                            "relevance_for_user": "This is relevant because you want a feed that highlights workflows you can reuse quickly.",
                        },
                        {
                            "topic_key": "topic_2",
                            "executive_summary": "Claude Code discussion emphasizes practical repo editing loops instead of generic hype.",
                            "relevance_for_user": "This matters because it helps separate immediately usable patterns from noise.",
                        },
                    ]
                }
            )

        return Response()


class FakeRewriteClient:
    responses = FakeRewriteResponses()


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
        FakeClient(),
        model="gpt-5-mini",
        posts=posts,
        insights=insights,
        processed_root=tmp_path,
        run_date="2026-03-12",
    )

    assert [item.category for item in result.suggestions] == ["content", "source"]
    assert result.path.exists()
    assert json.loads(result.path.read_text())[0]["title"] == "Prompt-state snapshots"


def test_generate_topic_rewrites_persists_structured_output(tmp_path: Path) -> None:
    result = generate_topic_rewrites(
        FakeRewriteClient(),
        model="gpt-5-mini",
        topics=(
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
        ),
        processed_root=tmp_path,
        run_date="2026-03-12",
    )

    assert [item.topic_key for item in result.rewrites] == ["topic_1", "topic_2"]
    assert result.path.exists()
    persisted = json.loads(result.path.read_text())
    assert persisted[0]["executive_summary"].startswith("Codex threads converge")
