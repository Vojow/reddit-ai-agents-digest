from __future__ import annotations

import re

from reddit_digest.extractors.common import comment_source
from reddit_digest.extractors.common import InsightPattern
from reddit_digest.extractors.common import match_patterns
from reddit_digest.extractors.common import post_source
from reddit_digest.extractors.common import TextSource
from reddit_digest.models.comment import Comment
from reddit_digest.models.post import Post


def test_extractor_common_builds_sources_and_matches_patterns() -> None:
    post = Post.from_raw(
        {
            "id": "post-1",
            "subreddit": "Codex",
            "title": "Codex system prompt workflow",
            "author": "tester",
            "score": 12,
            "num_comments": 3,
            "created_utc": 1_741_780_800,
            "url": "https://reddit.com/r/Codex/comments/post-1",
            "permalink": "/r/Codex/comments/post-1",
            "selftext": "system prompt workflow guide",
        }
    )
    comment = Comment.from_raw(
        {
            "id": "comment-1",
            "post_id": post.id,
            "parent_id": f"t3_{post.id}",
            "subreddit": post.subreddit,
            "author": "commenter",
            "body": "Codex workflow is deterministic",
            "score": 5,
            "created_utc": 1_741_780_900,
            "permalink": f"/r/{post.subreddit}/comments/{post.id}/comment-1",
        }
    )

    post_text = post_source(post)
    comment_text = comment_source(comment)

    assert "Codex system prompt workflow" in post_text.text
    assert comment_text.permalink.startswith("https://reddit.com/r/Codex/comments/")

    patterns = (
        InsightPattern(
            title="System prompting",
            category="tools",
            summary="summary",
            why_it_matters="why",
            tags=("tooling",),
            regex=re.compile(r"system prompt"),
        ),
    )

    matched = match_patterns(post_text, patterns)
    assert [item.title for item in matched] == ["System prompting"]
    assert match_patterns(
        TextSource(
            source_kind="post",
            source_id="p2",
            source_post_id="p2",
            subreddit="Codex",
            permalink="https://reddit.com/r/Codex/comments/p2",
            text="plain unrelated text",
        ),
        patterns,
    ) == []
