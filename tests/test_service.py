from __future__ import annotations

from reddit_digest.extractors.service import _extract
from reddit_digest.models.comment import Comment
from reddit_digest.models.post import Post


def test_extract_dedupes_and_sorts_insights() -> None:
    post = Post.from_raw(
        {
            "id": "post-1",
            "subreddit": "Codex",
            "title": "Codex workflow",
            "author": "tester",
            "score": 12,
            "num_comments": 3,
            "created_utc": 1_741_780_800,
            "url": "https://reddit.com/r/Codex/comments/post-1",
            "permalink": "/r/Codex/comments/post-1",
            "selftext": "system prompt workflow guide",
        }
    )
    comments = (
        Comment.from_raw(
            {
                "id": "comment-a",
                "post_id": post.id,
                "parent_id": f"t3_{post.id}",
                "subreddit": post.subreddit,
                "author": "commenter",
                "body": "Codex workflow is deterministic and codex is useful.",
                "score": 1,
                "created_utc": 1_741_780_900,
                "permalink": f"/r/{post.subreddit}/comments/{post.id}/comment-a",
            }
        ),
    )

    extracted = _extract((post,), comments)

    assert extracted == sorted(extracted, key=lambda insight: (insight.category, insight.title, insight.source_id))
    assert len({(item.category, item.title, item.source_id) for item in extracted}) == len(extracted)
