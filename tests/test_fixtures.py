from __future__ import annotations

from typing import Any


def assert_common_post_fields(post: dict[str, Any]) -> None:
    assert post["id"]
    assert post["subreddit"]
    assert post["title"]
    assert isinstance(post["score"], int)
    assert isinstance(post["num_comments"], int)
    assert post["permalink"].startswith("/r/")


def assert_common_comment_fields(comment: dict[str, Any]) -> None:
    assert comment["id"]
    assert comment["post_id"]
    assert comment["subreddit"]
    assert comment["body"]
    assert isinstance(comment["score"], int)
    assert comment["permalink"].startswith("/r/")


def test_sample_post_fixture_schema(sample_posts_payload: list[dict[str, Any]]) -> None:
    assert len(sample_posts_payload) >= 2
    for post in sample_posts_payload:
        assert_common_post_fields(post)


def test_sample_comment_fixture_schema(sample_comments_payload: list[dict[str, Any]]) -> None:
    assert len(sample_comments_payload) >= 2
    for comment in sample_comments_payload:
        assert_common_comment_fields(comment)


def test_comment_fixture_references_sample_posts(
    sample_posts_payload: list[dict[str, Any]],
    sample_comments_payload: list[dict[str, Any]],
) -> None:
    post_ids = {post["id"] for post in sample_posts_payload}
    assert {comment["post_id"] for comment in sample_comments_payload} <= post_ids
