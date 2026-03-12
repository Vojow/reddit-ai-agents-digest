"""Pipeline orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from pathlib import Path
import logging

from reddit_digest.collectors.reddit_comments import CommentCollector
from reddit_digest.collectors.reddit_comments import PublicRedditCommentSource
from reddit_digest.collectors.reddit_posts import PostCollector
from reddit_digest.collectors.reddit_posts import PublicRedditPostSource
from reddit_digest.config import load_config
from reddit_digest.outputs.google_sheets import GoogleSheetsExporter
from reddit_digest.outputs.markdown import render_markdown_digest
from reddit_digest.extractors.service import extract_insights
from reddit_digest.extractors.openai_suggestions import build_openai_client
from reddit_digest.extractors.openai_suggestions import generate_suggestions
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
        suggestions = ()
        if config.runtime.openai_api_key:
            suggestion_result = retry_call(
                lambda: generate_suggestions(
                    build_openai_client(config.runtime),
                    model=config.runtime.openai_model,
                    posts=post_result.posts,
                    insights=novelty.insights,
                    processed_root=self.base_path / "data" / "processed",
                    run_date=run_date,
                ),
                operation="generate_openai_suggestions",
                logger=LOGGER,
            )
            suggestions = tuple(f"{item.title}: {item.rationale}" for item in suggestion_result.suggestions)
        thread_selection = select_threads(
            post_result.posts,
            scoring=config.scoring,
            enabled_subreddits=config.subreddits.enabled_subreddits,
            run_at=run_at,
            lookback_hours=config.subreddits.fetch.lookback_hours,
        )
        markdown = render_markdown_digest(
            run_date=run_date,
            insights=novelty.insights,
            scoring=config.scoring,
            thread_selection=thread_selection,
            reports_root=self.base_path / "reports",
            watch_next=suggestions,
        )

        sheets_exported = False
        if not skip_sheets:
            retry_call(
                lambda: GoogleSheetsExporter.from_runtime(config.runtime).export(
                    run_date=run_date,
                    posts=post_result.posts,
                    insights=novelty.insights,
                    markdown_content=markdown.content,
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
