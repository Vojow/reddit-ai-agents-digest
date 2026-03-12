"""Shared extraction helpers."""

from __future__ import annotations

from dataclasses import dataclass
import re

from reddit_digest.models.comment import Comment
from reddit_digest.models.insight import Insight
from reddit_digest.models.post import Post


@dataclass(frozen=True)
class TextSource:
    source_kind: str
    source_id: str
    source_post_id: str
    subreddit: str
    permalink: str
    text: str


@dataclass(frozen=True)
class InsightPattern:
    title: str
    category: str
    summary: str
    why_it_matters: str
    tags: tuple[str, ...]
    regex: re.Pattern[str]


def post_source(post: Post) -> TextSource:
    text = "\n".join(part for part in [post.title, post.selftext or ""] if part)
    return TextSource(
        source_kind="post",
        source_id=post.id,
        source_post_id=post.id,
        subreddit=post.subreddit,
        permalink=post.url,
        text=text,
    )


def comment_source(comment: Comment) -> TextSource:
    return TextSource(
        source_kind="comment",
        source_id=comment.id,
        source_post_id=comment.post_id,
        subreddit=comment.subreddit,
        permalink=f"https://reddit.com{comment.permalink}",
        text=comment.body,
    )


def match_patterns(source: TextSource, patterns: tuple[InsightPattern, ...]) -> list[Insight]:
    lowered_text = source.text.lower()
    insights: list[Insight] = []
    for pattern in patterns:
        if not pattern.regex.search(lowered_text):
            continue
        insights.append(
            Insight(
                category=pattern.category,
                title=pattern.title,
                summary=pattern.summary,
                tags=pattern.tags,
                evidence=source.text.strip(),
                source_kind=source.source_kind,
                source_id=source.source_id,
                source_permalink=source.permalink,
                source_post_id=source.source_post_id,
                subreddit=source.subreddit,
                why_it_matters=pattern.why_it_matters,
            )
        )
    return insights
