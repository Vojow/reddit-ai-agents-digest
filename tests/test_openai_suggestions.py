from __future__ import annotations

from pathlib import Path
import json

from reddit_digest.extractors.openai_suggestions import generate_suggestions
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
