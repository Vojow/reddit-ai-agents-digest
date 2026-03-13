"""Pipeline orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from pathlib import Path
import logging

from openai import APIStatusError
from openai import RateLimitError

from reddit_digest.collectors.reddit_comments import CommentCollector
from reddit_digest.collectors.reddit_comments import PublicRedditCommentSource
from reddit_digest.collectors.reddit_posts import PostCollector
from reddit_digest.collectors.reddit_posts import PublicRedditPostSource
from reddit_digest.config import load_config
from reddit_digest.extractors.openai_suggestions import build_openai_client
from reddit_digest.extractors.openai_suggestions import generate_suggestions
from reddit_digest.extractors.openai_suggestions import generate_topic_rewrites
from reddit_digest.extractors.service import extract_insights
from reddit_digest.outputs.google_sheets import GoogleSheetsExporter
from reddit_digest.outputs.digest import build_digest_artifact
from reddit_digest.outputs.markdown import render_markdown_digest
from reddit_digest.outputs.markdown import select_digest_topics
from reddit_digest.ranking.novelty import apply_novelty
from reddit_digest.ranking.threads import select_threads
from reddit_digest.utils.retries import retry_call
from reddit_digest.utils.state import RunState
from reddit_digest.utils.state import write_run_state


LOGGER = logging.getLogger(__name__)


@dataclass
class PipelineRunner:
    base_path: Path

    def run(self, *, run_date: str, skip_sheets: bool = False) -> RunState:
        config = load_config(
            self.base_path,
            require_reddit=True,
            require_sheets=not skip_sheets,
        )
        run_at = datetime.fromisoformat(f"{run_date}T12:00:00+00:00").astimezone(UTC)

        post_source = PublicRedditPostSource(config.runtime)
        comment_source = PublicRedditCommentSource(config.runtime)

        post_result = retry_call(
            lambda: PostCollector(post_source, self.base_path / "data" / "raw", self.base_path / "data" / "processed").collect(
                config.subreddits,
                run_at=run_at,
            ),
            operation="collect_posts",
            logger=LOGGER,
        )
        comment_result = retry_call(
            lambda: CommentCollector(
                comment_source,
                self.base_path / "data" / "raw",
                self.base_path / "data" / "processed",
            ).collect(
                post_result.posts,
                max_comments_per_post=config.subreddits.fetch.max_comments_per_post,
                run_at=run_at,
            ),
            operation="collect_comments",
            logger=LOGGER,
        )
        extracted = extract_insights(
            post_result.posts,
            comment_result.comments,
            processed_root=self.base_path / "data" / "processed",
            run_date=run_date,
        )
        novelty = apply_novelty(self.base_path / "data" / "processed", run_date=run_date, insights=extracted.insights)
        thread_selection = select_threads(
            post_result.posts,
            scoring=config.scoring,
            enabled_subreddits=config.subreddits.enabled_subreddits,
            run_at=run_at,
            lookback_hours=config.subreddits.fetch.lookback_hours,
        )
        digest_topics = select_digest_topics(
            insights=novelty.insights,
            scoring=config.scoring,
            thread_selection=thread_selection,
        )

        suggestions = ()
        topic_rewrites: dict[str, tuple[str, str]] = {}
        markdown_warnings: list[str] = []
        if config.runtime.openai_api_key:
            openai_client = build_openai_client(config.runtime)
            skip_topic_rewrites = False
            try:
                suggestion_result = retry_call(
                    lambda: generate_suggestions(
                        openai_client,
                        model=config.runtime.openai_model,
                        posts=post_result.posts,
                        insights=novelty.insights,
                        processed_root=self.base_path / "data" / "processed",
                        run_date=run_date,
                    ),
                    operation="generate_openai_suggestions",
                    logger=LOGGER,
                )
            except Exception as exc:
                LOGGER.warning("Skipping OpenAI suggestions for %s after failure", run_date, exc_info=True)
                quota_warning = _build_openai_warning(exc, skipped_steps="Watch Next suggestions and LLM topic rewrites")
                if quota_warning is not None:
                    markdown_warnings.append(quota_warning)
                    skip_topic_rewrites = True
                else:
                    raise
            else:
                suggestions = tuple(f"{item.title}: {item.rationale}" for item in suggestion_result.suggestions)

            if digest_topics and not skip_topic_rewrites:
                try:
                    rewrite_result = retry_call(
                        lambda: generate_topic_rewrites(
                            openai_client,
                            model=config.runtime.openai_model,
                            topics=tuple(
                                {
                                    "topic_key": topic.topic_key,
                                    "title": topic.title,
                                    "executive_summary": topic.executive_summary,
                                    "relevance_for_user": topic.relevance_for_user,
                                    "source_title": topic.source_title,
                                    "source_subreddit": topic.source_subreddit,
                                    "source_url": topic.source_url,
                                    "impact_score": topic.impact_score,
                                    "support_count": topic.support_count,
                                }
                                for topic in digest_topics
                            ),
                            processed_root=self.base_path / "data" / "processed",
                            run_date=run_date,
                        ),
                        operation="rewrite_openai_topics",
                        logger=LOGGER,
                    )
                except Exception as exc:
                    LOGGER.warning("Skipping LLM markdown variant for %s after topic rewrite failure", run_date, exc_info=True)
                    quota_warning = _build_openai_warning(exc, skipped_steps="LLM topic rewrites")
                    if quota_warning is not None:
                        markdown_warnings.append(quota_warning)
                else:
                    topic_rewrites = {
                        item.topic_key: (item.executive_summary, item.relevance_for_user)
                        for item in rewrite_result.rewrites
                    }
        digest = build_digest_artifact(
            run_date=run_date,
            insights=novelty.insights,
            scoring=config.scoring,
            thread_selection=thread_selection,
            watch_next=suggestions,
            topics=digest_topics,
        )
        markdown = render_markdown_digest(
            run_date=run_date,
            insights=novelty.insights,
            scoring=config.scoring,
            thread_selection=thread_selection,
            reports_root=self.base_path / "reports",
            watch_next=suggestions,
            warnings=tuple(dict.fromkeys(markdown_warnings)),
            digest=digest,
        )
        if topic_rewrites:
            render_markdown_digest(
                run_date=run_date,
                insights=novelty.insights,
                scoring=config.scoring,
                thread_selection=thread_selection,
                reports_root=self.base_path / "reports",
                digest=digest,
                topic_rewrites=topic_rewrites,
                variant_suffix="llm",
            )

        sheets_exported = False
        if not skip_sheets:
            retry_call(
                lambda: GoogleSheetsExporter.from_runtime(config.runtime).export(
                    run_date=run_date,
                    posts=post_result.posts,
                    insights=novelty.insights,
                    digest=digest,
                    scoring=config.scoring,
                    lookback_hours=config.subreddits.fetch.lookback_hours,
                    run_at=run_at,
                ),
                operation="export_google_sheets",
                logger=LOGGER,
            )
            sheets_exported = True

        state = RunState(
            run_date=run_date,
            completed_at=datetime.now(tz=UTC).isoformat(),
            raw_posts_path=str(post_result.raw_path.relative_to(self.base_path)),
            raw_comments_path=str(comment_result.raw_path.relative_to(self.base_path)),
            insights_path=str(novelty.path.relative_to(self.base_path)),
            report_path=str(markdown.daily_path.relative_to(self.base_path)),
            sheets_exported=sheets_exported,
        )
        write_run_state(self.base_path / "data" / "state", state)
        LOGGER.info("Pipeline completed for %s", run_date)
        return state


def _build_openai_warning(exc: Exception, *, skipped_steps: str) -> str | None:
    if _is_openai_quota_error(exc):
        return (
            f"OPENAI QUOTA EXHAUSTED: {skipped_steps} were skipped. "
            "The deterministic markdown below was generated successfully without OpenAI enhancements."
        )
    if isinstance(exc, RateLimitError):
        return (
            f"OPENAI RATE LIMITED: {skipped_steps} were skipped. "
            "The deterministic markdown below was generated successfully without OpenAI enhancements."
        )
    return None


def _is_openai_quota_error(exc: Exception) -> bool:
    if isinstance(exc, APIStatusError):
        body = getattr(exc, "body", None)
        if isinstance(body, dict):
            error = body.get("error")
            if isinstance(error, dict):
                code = error.get("code")
                if code == "insufficient_quota":
                    return True
    message = str(exc).lower()
    return "insufficient quota" in message or "insufficient_quota" in message
