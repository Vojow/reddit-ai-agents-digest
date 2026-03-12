from __future__ import annotations

from typing import Any

import pytest

from reddit_digest.models.base import ModelError
from reddit_digest.models.comment import Comment
from reddit_digest.models.digest import DigestItem
from reddit_digest.models.post import Post


def test_post_from_raw_normalizes_fixture(sample_posts_payload: list[dict[str, Any]]) -> None:
    post = Post.from_raw(sample_posts_payload[0])

    assert post.id == "post_001"
    assert post.subreddit == "Codex"
    assert post.num_comments == 18
    assert post.to_dict()["title"] == "Codex agent keeps a local context file for every task"


def test_comment_from_raw_normalizes_fixture(sample_comments_payload: list[dict[str, Any]]) -> None:
    comment = Comment.from_raw(sample_comments_payload[0])

    assert comment.post_id == "post_001"
    assert comment.parent_id == "t3_post_001"
    assert "deterministic" in comment.body


def test_deleted_comment_is_rejected(sample_comments_payload: list[dict[str, Any]]) -> None:
    deleted_comment = dict(sample_comments_payload[0])
    deleted_comment["body"] = "[deleted]"

    with pytest.raises(ModelError, match="comment text"):
        Comment.from_raw(deleted_comment)


def test_digest_item_from_raw_validates_required_fields() -> None:
    payload = {
        "category": "tools",
        "title": "Codex",
        "subreddit": "Codex",
        "permalink": "https://reddit.com/r/Codex/comments/post_001",
        "why_it_matters": "Helps automate repo changes with clear task context.",
        "impact_score": 8.7,
        "tags": ["ai-agents", "tooling"],
        "source_post_ids": ["post_001"],
        "evidence": "Mentioned repeatedly in the thread and comments.",
    }

    item = DigestItem.from_raw(payload)

    assert item.category == "tools"
    assert item.tags == ("ai-agents", "tooling")
    assert item.source_post_ids == ("post_001",)


def test_post_requires_relative_permalink(sample_posts_payload: list[dict[str, Any]]) -> None:
    invalid_post = dict(sample_posts_payload[0])
    invalid_post["permalink"] = "https://reddit.com/r/Codex/comments/post_001"

    with pytest.raises(ModelError, match="permalink"):
        Post.from_raw(invalid_post)


def test_negative_scores_are_preserved(sample_posts_payload: list[dict[str, Any]]) -> None:
    post_payload = dict(sample_posts_payload[0])
    post_payload["score"] = -3

    comment_payload = {
        "id": "comment_negative_score",
        "post_id": "post_001",
        "parent_id": "t3_post_001",
        "subreddit": "Codex",
        "author": "skeptic",
        "body": "This still has useful schema even when the score is negative.",
        "score": -1,
        "created_utc": 1773316500,
        "permalink": "/r/Codex/comments/post_001/comment_negative_score/",
    }

    assert Post.from_raw(post_payload).score == -3
    assert Comment.from_raw(comment_payload).score == -1
