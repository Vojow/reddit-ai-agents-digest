"""Explicit pipeline stages with focused input/output contracts."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from pathlib import Path
import logging

from reddit_digest.collectors.reddit_comments import PublicRedditCommentSource
from reddit_digest.collectors.reddit_posts import PublicRedditPostSource
from reddit_digest.config import AppConfig
from reddit_digest.models.insight import Insight
from reddit_digest.models.openai_usage import OpenAIUsageSummary
from reddit_digest.models.post import Post
from reddit_digest.outputs.digest import build_digest_artifact
from reddit_digest.outputs.digest import DigestArtifact
from reddit_digest.outputs.digest import RankedTopic
from reddit_digest.outputs.markdown import MarkdownDigestResult
from reddit_digest.outputs.teams import TeamsTopicSummary
from reddit_digest.ranking.threads import ThreadSelection
from reddit_digest.utils.state import RunState


LoggerRetryCall = Callable[..., object]


@dataclass(frozen=True)
class PipelineRunContext:
    base_path: Path
    config: AppConfig
    run_date: str
    run_at: datetime
    skip_sheets: bool

    @classmethod
    def build(cls, *, base_path: Path, config: AppConfig, run_date: str, skip_sheets: bool) -> "PipelineRunContext":
        run_at = datetime.fromisoformat(f"{run_date}T12:00:00+00:00").astimezone(UTC)
        return cls(
            base_path=base_path,
            config=config,
            run_date=run_date,
            run_at=run_at,
            skip_sheets=skip_sheets,
        )


@dataclass(frozen=True)
class CollectionArtifacts:
    posts: tuple[Post, ...]
    comments: tuple[object, ...]
    raw_posts_path: Path
    raw_comments_path: Path


@dataclass(frozen=True)
class AnalysisArtifacts:
    insights: tuple[Insight, ...]
    insights_path: Path
    thread_selection: ThreadSelection
    digest_topics: tuple[RankedTopic, ...]


@dataclass(frozen=True)
class OpenAIArtifacts:
    watch_next: tuple[str, ...]
    topic_rewrites: dict[str, tuple[str, str]]
    executive_summary_rewrite: str | None
    warnings: tuple[str, ...]
    usage: OpenAIUsageSummary


@dataclass(frozen=True)
class RenderArtifacts:
    digest: DigestArtifact
    markdown: MarkdownDigestResult
    llm_markdown: MarkdownDigestResult | None


@dataclass(frozen=True)
class DeliveryArtifacts:
    sheets_exported: bool
    teams_published: bool
    teams_error: str | None


@dataclass(frozen=True)
class CollectionStage:
    base_path: Path
    logger: logging.Logger
    retry_call: Callable[..., object]
    post_source_factory: Callable[[object], PublicRedditPostSource]
    comment_source_factory: Callable[[object], PublicRedditCommentSource]
    post_collector_factory: Callable[[object, Path, Path], object]
    comment_collector_factory: Callable[[object, Path, Path], object]

    def run(self, context: PipelineRunContext) -> CollectionArtifacts:
        raw_root = self.base_path / "data" / "raw"
        processed_root = self.base_path / "data" / "processed"
        post_source = self.post_source_factory(context.config.runtime)
        comment_source = self.comment_source_factory(context.config.runtime)

        post_result = self.retry_call(
            lambda: self.post_collector_factory(post_source, raw_root, processed_root).collect(
                context.config.subreddits,
                run_at=context.run_at,
            ),
            operation="collect_posts",
            logger=self.logger,
        )
        comment_result = self.retry_call(
            lambda: self.comment_collector_factory(comment_source, raw_root, processed_root).collect(
                post_result.posts,
                max_comments_per_post=context.config.subreddits.fetch.max_comments_per_post,
                run_at=context.run_at,
            ),
            operation="collect_comments",
            logger=self.logger,
        )
        return CollectionArtifacts(
            posts=post_result.posts,
            comments=comment_result.comments,
            raw_posts_path=post_result.raw_path,
            raw_comments_path=comment_result.raw_path,
        )


@dataclass(frozen=True)
class AnalysisStage:
    base_path: Path
    extract_insights: Callable[..., object]
    apply_novelty: Callable[..., object]
    select_threads: Callable[..., ThreadSelection]
    select_digest_topics: Callable[..., tuple[RankedTopic, ...]]

    def run(self, context: PipelineRunContext, collection: CollectionArtifacts) -> AnalysisArtifacts:
        processed_root = self.base_path / "data" / "processed"
        extracted = self.extract_insights(
            collection.posts,
            collection.comments,
            processed_root=processed_root,
            run_date=context.run_date,
        )
        novelty = self.apply_novelty(processed_root, run_date=context.run_date, insights=extracted.insights)
        thread_selection = self.select_threads(
            collection.posts,
            scoring=context.config.scoring,
            enabled_subreddits=context.config.subreddits.enabled_subreddits,
            run_at=context.run_at,
            lookback_hours=context.config.subreddits.fetch.lookback_hours,
        )
        digest_topics = self.select_digest_topics(
            insights=novelty.insights,
            scoring=context.config.scoring,
            thread_selection=thread_selection,
        )
        return AnalysisArtifacts(
            insights=novelty.insights,
            insights_path=novelty.path,
            thread_selection=thread_selection,
            digest_topics=digest_topics,
        )


@dataclass(frozen=True)
class OpenAIStage:
    base_path: Path
    logger: logging.Logger
    retry_call: Callable[..., object]
    build_openai_client: Callable[[object], object]
    generate_suggestions: Callable[..., object]
    generate_topic_rewrites: Callable[..., object]
    generate_executive_summary_rewrite: Callable[..., object]
    build_suggestion_warning: Callable[[Exception], str | None]
    build_rewrite_warning: Callable[[Exception], str | None]

    def run(self, context: PipelineRunContext, collection: CollectionArtifacts, analysis: AnalysisArtifacts) -> OpenAIArtifacts:
        if not context.config.runtime.openai_api_key:
            return OpenAIArtifacts(
                watch_next=(),
                topic_rewrites={},
                executive_summary_rewrite=None,
                warnings=(),
                usage=OpenAIUsageSummary.empty(),
            )

        openai_client = self.build_openai_client(context.config.runtime)
        processed_root = self.base_path / "data" / "processed"
        watch_next: tuple[str, ...] = ()
        topic_rewrites: dict[str, tuple[str, str]] = {}
        executive_summary_rewrite: str | None = None
        markdown_warnings: list[str] = []
        skip_topic_rewrites = False

        try:
            suggestion_result = self.retry_call(
                lambda: self.generate_suggestions(
                    openai_client,
                    model=context.config.runtime.openai_model,
                    posts=collection.posts,
                    insights=analysis.insights,
                    processed_root=processed_root,
                    run_date=context.run_date,
                ),
                operation="generate_openai_suggestions",
                logger=self.logger,
            )
        except Exception as exc:
            self.logger.warning("Skipping OpenAI suggestions for %s after failure", context.run_date, exc_info=True)
            quota_warning = self.build_suggestion_warning(exc)
            if quota_warning is not None:
                markdown_warnings.append(quota_warning)
                skip_topic_rewrites = True
            else:
                raise
        else:
            watch_next = tuple(f"{item.title}: {item.rationale}" for item in suggestion_result.suggestions)

        if analysis.digest_topics and not skip_topic_rewrites:
            try:
                rewrite_result = self.retry_call(
                    lambda: self.generate_topic_rewrites(
                        openai_client,
                        model=context.config.runtime.openai_model,
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
                            for topic in analysis.digest_topics
                        ),
                        processed_root=processed_root,
                        run_date=context.run_date,
                    ),
                    operation="rewrite_openai_topics",
                    logger=self.logger,
                )
            except Exception as exc:
                self.logger.warning(
                    "Skipping LLM markdown variant for %s after topic rewrite failure",
                    context.run_date,
                    exc_info=True,
                )
                quota_warning = self.build_rewrite_warning(exc)
                if quota_warning is not None:
                    markdown_warnings.append(quota_warning)
            else:
                topic_rewrites = {
                    item.topic_key: (item.executive_summary, item.relevance_for_user)
                    for item in rewrite_result.rewrites
                }
                try:
                    executive_summary_result = self.retry_call(
                        lambda: self.generate_executive_summary_rewrite(
                            openai_client,
                            model=context.config.runtime.openai_model,
                            summary_payload={
                                "run_date": context.run_date,
                                "total_posts": len(analysis.thread_selection.ranked_posts),
                                "represented_subreddits": tuple(
                                    dict.fromkeys(item.post.subreddit for item in analysis.thread_selection.ranked_posts)
                                ),
                                "top_topic_title": analysis.digest_topics[0].title if analysis.digest_topics else None,
                                "topics": tuple(
                                    {
                                        "title": topic.title,
                                        "executive_summary": topic.executive_summary,
                                        "relevance_for_user": topic.relevance_for_user,
                                        "source_subreddit": topic.source_subreddit,
                                        "support_count": topic.support_count,
                                        "impact_score": topic.impact_score,
                                    }
                                    for topic in analysis.digest_topics
                                ),
                            },
                            processed_root=processed_root,
                            run_date=context.run_date,
                        ),
                        operation="rewrite_openai_executive_summary",
                        logger=self.logger,
                    )
                except Exception:
                    self.logger.warning(
                        "Skipping LLM executive summary rewrite for %s after failure",
                        context.run_date,
                        exc_info=True,
                    )
                else:
                    executive_summary_rewrite = executive_summary_result.executive_summary

        return OpenAIArtifacts(
            watch_next=watch_next,
            topic_rewrites=topic_rewrites,
            executive_summary_rewrite=executive_summary_rewrite,
            warnings=tuple(dict.fromkeys(markdown_warnings)),
            usage=openai_client.usage_summary(),
        )


@dataclass(frozen=True)
class RenderStage:
    base_path: Path
    build_digest_artifact: Callable[..., DigestArtifact]
    render_markdown_digest: Callable[..., MarkdownDigestResult]

    def run(
        self,
        context: PipelineRunContext,
        analysis: AnalysisArtifacts,
        openai: OpenAIArtifacts,
    ) -> RenderArtifacts:
        digest = self.build_digest_artifact(
            run_date=context.run_date,
            insights=analysis.insights,
            scoring=context.config.scoring,
            thread_selection=analysis.thread_selection,
            watch_next=openai.watch_next,
            topics=analysis.digest_topics,
        )
        markdown = self.render_markdown_digest(
            run_date=context.run_date,
            insights=analysis.insights,
            scoring=context.config.scoring,
            thread_selection=analysis.thread_selection,
            reports_root=self.base_path / "reports",
            warnings=openai.warnings,
            digest=digest,
        )
        llm_markdown = None
        if openai.topic_rewrites or openai.executive_summary_rewrite:
            llm_markdown = self.render_markdown_digest(
                run_date=context.run_date,
                insights=analysis.insights,
                scoring=context.config.scoring,
                thread_selection=analysis.thread_selection,
                reports_root=self.base_path / "reports",
                digest=digest,
                topic_rewrites=openai.topic_rewrites,
                executive_summary_rewrite=openai.executive_summary_rewrite,
                variant_suffix="llm",
            )
        return RenderArtifacts(digest=digest, markdown=markdown, llm_markdown=llm_markdown)


@dataclass(frozen=True)
class DeliveryStage:
    base_path: Path
    logger: logging.Logger
    retry_call: Callable[..., object]
    sheets_exporter_factory: Callable[[object], object]
    publish_digest_to_teams: Callable[..., object]

    def run(
        self,
        context: PipelineRunContext,
        collection: CollectionArtifacts,
        analysis: AnalysisArtifacts,
        openai: OpenAIArtifacts,
        rendered: RenderArtifacts,
    ) -> DeliveryArtifacts:
        sheets_exported = False
        if not context.skip_sheets:
            self.retry_call(
                lambda: self.sheets_exporter_factory(context.config.runtime).export(
                    run_date=context.run_date,
                    posts=collection.posts,
                    insights=analysis.insights,
                    digest=rendered.digest,
                    scoring=context.config.scoring,
                    lookback_hours=context.config.subreddits.fetch.lookback_hours,
                    run_at=context.run_at,
                ),
                operation="export_google_sheets",
                logger=self.logger,
            )
            sheets_exported = True

        teams_published = False
        teams_error = None
        if context.config.runtime.teams_webhook_url:
            try:
                self.retry_call(
                    lambda: self.publish_digest_to_teams(
                        context.config.runtime.teams_webhook_url,
                        run_date=context.run_date,
                        warnings=openai.warnings,
                        topics=tuple(
                            TeamsTopicSummary(
                                title=topic.title,
                                subreddit=topic.source_subreddit,
                                impact_score=topic.impact_score,
                            )
                            for topic in rendered.digest.topics[:3]
                        ),
                        emerging_themes=tuple(theme.label for theme in rendered.digest.emerging_themes),
                        watch_next=rendered.digest.watch_next,
                        openai_usage=openai.usage,
                        deterministic_report_path=str(rendered.markdown.daily_path.relative_to(self.base_path)),
                        preferred_report_path=str(
                            (
                                rendered.llm_markdown.daily_path
                                if rendered.llm_markdown is not None
                                else rendered.markdown.daily_path
                            ).relative_to(self.base_path)
                        ),
                        llm_report_path=(
                            str(rendered.llm_markdown.daily_path.relative_to(self.base_path))
                            if rendered.llm_markdown is not None
                            else None
                        ),
                    ),
                    operation="publish_teams_digest",
                    logger=self.logger,
                )
            except Exception as exc:
                teams_error = str(exc)
                self.logger.warning("Skipping Teams webhook publish for %s after failure", context.run_date, exc_info=True)
            else:
                teams_published = True

        return DeliveryArtifacts(
            sheets_exported=sheets_exported,
            teams_published=teams_published,
            teams_error=teams_error,
        )


@dataclass(frozen=True)
class StateStage:
    base_path: Path
    write_run_state: Callable[[Path, RunState], None]

    def run(
        self,
        context: PipelineRunContext,
        collection: CollectionArtifacts,
        analysis: AnalysisArtifacts,
        rendered: RenderArtifacts,
        delivery: DeliveryArtifacts,
        openai: OpenAIArtifacts,
    ) -> RunState:
        state = RunState(
            run_date=context.run_date,
            completed_at=datetime.now(tz=UTC).isoformat(),
            raw_posts_path=str(collection.raw_posts_path.relative_to(self.base_path)),
            raw_comments_path=str(collection.raw_comments_path.relative_to(self.base_path)),
            insights_path=str(analysis.insights_path.relative_to(self.base_path)),
            report_path=str(rendered.markdown.daily_path.relative_to(self.base_path)),
            sheets_exported=delivery.sheets_exported,
            teams_published=delivery.teams_published,
            teams_error=delivery.teams_error,
            openai_usage=openai.usage,
        )
        self.write_run_state(self.base_path / "data" / "state", state)
        return state
