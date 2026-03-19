"""Explicit pipeline stage functions and their typed service contracts."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from pathlib import Path
import logging
from typing import Protocol
from typing import TypeVar

from reddit_digest.collectors.reddit_comments import PublicRedditCommentSource
from reddit_digest.collectors.reddit_posts import PublicRedditPostSource
from reddit_digest.config import AppConfig
from reddit_digest.config import RuntimeConfig
from reddit_digest.config import ScoringConfig
from reddit_digest.config import SubredditConfig
from reddit_digest.extractors.openai_suggestions import ExecutiveSummaryRewriteRequest
from reddit_digest.extractors.openai_suggestions import TopicRewriteRequest
from reddit_digest.models.insight import Insight
from reddit_digest.models.openai_usage import OpenAIUsageSummary
from reddit_digest.models.post import Post
from reddit_digest.outputs.digest import DigestArtifact
from reddit_digest.outputs.digest import RankedTopic
from reddit_digest.outputs.markdown import MarkdownDigestResult
from reddit_digest.outputs.teams import extract_executive_summary
from reddit_digest.outputs.teams import TeamsDigestPayload
from reddit_digest.outputs.teams import TeamsTopicSummary
from reddit_digest.ranking.threads import ThreadSelection
from reddit_digest.utils.state import RunState


T = TypeVar("T")


class RetryCall(Protocol):
    def __call__(self, func: Callable[[], T], *, operation: str, logger: logging.Logger) -> T: ...


class PostCollectionResultLike(Protocol):
    posts: tuple[Post, ...]
    raw_path: Path


class CommentCollectionResultLike(Protocol):
    comments: tuple[object, ...]
    raw_path: Path


class PostCollectorLike(Protocol):
    def collect(self, subreddits: SubredditConfig, *, run_at: datetime) -> PostCollectionResultLike: ...


class CommentCollectorLike(Protocol):
    def collect(
        self,
        posts: tuple[Post, ...],
        *,
        max_comments_per_post: int,
        run_at: datetime,
    ) -> CommentCollectionResultLike: ...


class ExtractInsightsResultLike(Protocol):
    insights: tuple[Insight, ...]


class NoveltyResultLike(Protocol):
    insights: tuple[Insight, ...]
    path: Path


class SuggestionLike(Protocol):
    title: str
    rationale: str


class SuggestionResultLike(Protocol):
    suggestions: tuple[SuggestionLike, ...]


class TopicRewriteLike(Protocol):
    topic_key: str
    executive_summary: str
    relevance_for_user: str


class TopicRewriteResultLike(Protocol):
    rewrites: tuple[TopicRewriteLike, ...]


class ExecutiveSummaryRewriteResultLike(Protocol):
    executive_summary: str


class OpenAIClientLike(Protocol):
    def usage_summary(self) -> OpenAIUsageSummary: ...


class SheetsExporterLike(Protocol):
    def export(
        self,
        *,
        run_date: str,
        posts: tuple[Post, ...],
        insights: tuple[Insight, ...],
        digest: DigestArtifact,
        scoring: ScoringConfig,
        lookback_hours: int,
        run_at: datetime | None = None,
    ) -> object: ...


PostSourceFactory = Callable[[RuntimeConfig], PublicRedditPostSource]
CommentSourceFactory = Callable[[RuntimeConfig], PublicRedditCommentSource]
PostCollectorFactory = Callable[[PublicRedditPostSource, Path, Path], PostCollectorLike]
CommentCollectorFactory = Callable[[PublicRedditCommentSource, Path, Path], CommentCollectorLike]
ExtractInsightsFunc = Callable[[tuple[Post, ...], tuple[object, ...]], ExtractInsightsResultLike]
ApplyNoveltyFunc = Callable[[Path], NoveltyResultLike]
SelectThreadsFunc = Callable[..., ThreadSelection]
SelectDigestTopicsFunc = Callable[..., tuple[RankedTopic, ...]]
BuildOpenAIClientFunc = Callable[[RuntimeConfig], OpenAIClientLike]
GenerateSuggestionsFunc = Callable[..., SuggestionResultLike]
GenerateTopicRewritesFunc = Callable[..., TopicRewriteResultLike]
GenerateExecutiveSummaryRewriteFunc = Callable[..., ExecutiveSummaryRewriteResultLike]
WarningBuilder = Callable[[Exception], str | None]
BuildDigestArtifactFunc = Callable[..., DigestArtifact]
RenderMarkdownDigestFunc = Callable[..., MarkdownDigestResult]
SheetsExporterFactory = Callable[[RuntimeConfig], SheetsExporterLike]
PublishTeamsDigestFunc = Callable[[str, TeamsDigestPayload], object]
WriteRunStateFunc = Callable[[Path, RunState], None]


@dataclass(frozen=True)
class PipelineRunContext:
    base_path: Path
    config: AppConfig
    run_date: str
    run_at: datetime
    skip_sheets: bool
    skip_openai: bool

    @classmethod
    def build(
        cls,
        *,
        base_path: Path,
        config: AppConfig,
        run_date: str,
        skip_sheets: bool,
        skip_openai: bool,
    ) -> "PipelineRunContext":
        run_at = datetime.fromisoformat(f"{run_date}T12:00:00+00:00").astimezone(UTC)
        return cls(
            base_path=base_path,
            config=config,
            run_date=run_date,
            run_at=run_at,
            skip_sheets=skip_sheets,
            skip_openai=skip_openai,
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
class CollectionStageServices:
    logger: logging.Logger
    retry_call: RetryCall
    post_source_factory: PostSourceFactory
    comment_source_factory: CommentSourceFactory
    post_collector_factory: PostCollectorFactory
    comment_collector_factory: CommentCollectorFactory


@dataclass(frozen=True)
class AnalysisStageServices:
    extract_insights: ExtractInsightsFunc
    apply_novelty: ApplyNoveltyFunc
    select_threads: SelectThreadsFunc
    select_digest_topics: SelectDigestTopicsFunc


@dataclass(frozen=True)
class OpenAIStageServices:
    logger: logging.Logger
    retry_call: RetryCall
    build_openai_client: BuildOpenAIClientFunc
    generate_suggestions: GenerateSuggestionsFunc
    generate_topic_rewrites: GenerateTopicRewritesFunc
    generate_executive_summary_rewrite: GenerateExecutiveSummaryRewriteFunc
    build_suggestion_warning: WarningBuilder
    build_rewrite_warning: WarningBuilder


@dataclass(frozen=True)
class RenderStageServices:
    build_digest_artifact: BuildDigestArtifactFunc
    render_markdown_digest: RenderMarkdownDigestFunc


@dataclass(frozen=True)
class DeliveryStageServices:
    logger: logging.Logger
    retry_call: RetryCall
    sheets_exporter_factory: SheetsExporterFactory
    publish_digest_to_teams: PublishTeamsDigestFunc


@dataclass(frozen=True)
class StateStageServices:
    write_run_state: WriteRunStateFunc


@dataclass(frozen=True)
class PipelineServices:
    collection: CollectionStageServices
    analysis: AnalysisStageServices
    openai: OpenAIStageServices
    render: RenderStageServices
    delivery: DeliveryStageServices
    state: StateStageServices


def run_collection_stage(context: PipelineRunContext, services: PipelineServices) -> CollectionArtifacts:
    stage = services.collection
    raw_root = context.base_path / "data" / "raw"
    processed_root = context.base_path / "data" / "processed"
    post_source = stage.post_source_factory(context.config.runtime)
    comment_source = stage.comment_source_factory(context.config.runtime)

    post_result = stage.retry_call(
        lambda: stage.post_collector_factory(post_source, raw_root, processed_root).collect(
            context.config.subreddits,
            run_at=context.run_at,
        ),
        operation="collect_posts",
        logger=stage.logger,
    )
    comment_result = stage.retry_call(
        lambda: stage.comment_collector_factory(comment_source, raw_root, processed_root).collect(
            post_result.posts,
            max_comments_per_post=context.config.subreddits.fetch.max_comments_per_post,
            run_at=context.run_at,
        ),
        operation="collect_comments",
        logger=stage.logger,
    )
    return CollectionArtifacts(
        posts=post_result.posts,
        comments=comment_result.comments,
        raw_posts_path=post_result.raw_path,
        raw_comments_path=comment_result.raw_path,
    )


def run_analysis_stage(
    context: PipelineRunContext,
    collection: CollectionArtifacts,
    services: PipelineServices,
) -> AnalysisArtifacts:
    stage = services.analysis
    processed_root = context.base_path / "data" / "processed"
    extracted = stage.extract_insights(
        collection.posts,
        collection.comments,
        processed_root=processed_root,
        run_date=context.run_date,
    )
    novelty = stage.apply_novelty(processed_root, run_date=context.run_date, insights=extracted.insights)
    thread_selection = stage.select_threads(
        collection.posts,
        scoring=context.config.scoring,
        enabled_subreddits=context.config.subreddits.enabled_subreddits,
        run_at=context.run_at,
        lookback_hours=context.config.subreddits.fetch.lookback_hours,
    )
    digest_topics = stage.select_digest_topics(
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


def run_openai_stage(
    context: PipelineRunContext,
    collection: CollectionArtifacts,
    analysis: AnalysisArtifacts,
    services: PipelineServices,
) -> OpenAIArtifacts:
    stage = services.openai
    if context.skip_openai or not context.config.runtime.openai_api_key:
        return OpenAIArtifacts(
            watch_next=(),
            topic_rewrites={},
            executive_summary_rewrite=None,
            warnings=(),
            usage=OpenAIUsageSummary.empty(),
        )

    openai_client = stage.build_openai_client(context.config.runtime)
    processed_root = context.base_path / "data" / "processed"
    watch_next: tuple[str, ...] = ()
    topic_rewrites: dict[str, tuple[str, str]] = {}
    executive_summary_rewrite: str | None = None
    markdown_warnings: list[str] = []
    skip_topic_rewrites = False

    try:
        suggestion_result = stage.retry_call(
            lambda: stage.generate_suggestions(
                openai_client,
                model=context.config.runtime.openai_model,
                posts=collection.posts,
                insights=analysis.insights,
                processed_root=processed_root,
                run_date=context.run_date,
            ),
            operation="generate_openai_suggestions",
            logger=stage.logger,
        )
    except Exception as exc:
        stage.logger.warning("Skipping OpenAI suggestions for %s after failure", context.run_date, exc_info=True)
        quota_warning = stage.build_suggestion_warning(exc)
        if quota_warning is not None:
            markdown_warnings.append(quota_warning)
            skip_topic_rewrites = True
        else:
            raise
    else:
        watch_next = tuple(f"{item.title}: {item.rationale}" for item in suggestion_result.suggestions)

    if analysis.digest_topics and not skip_topic_rewrites:
        rewrite_requests = _build_topic_rewrite_requests(analysis.digest_topics)
        try:
            rewrite_result = stage.retry_call(
                lambda: stage.generate_topic_rewrites(
                    openai_client,
                    model=context.config.runtime.openai_model,
                    requests=rewrite_requests,
                    processed_root=processed_root,
                    run_date=context.run_date,
                ),
                operation="rewrite_openai_topics",
                logger=stage.logger,
            )
        except Exception as exc:
            stage.logger.warning(
                "Skipping LLM markdown variant for %s after topic rewrite failure",
                context.run_date,
                exc_info=True,
            )
            quota_warning = stage.build_rewrite_warning(exc)
            if quota_warning is not None:
                markdown_warnings.append(quota_warning)
        else:
            topic_rewrites = {
                item.topic_key: (item.executive_summary, item.relevance_for_user)
                for item in rewrite_result.rewrites
            }
            try:
                summary_request = _build_executive_summary_rewrite_request(
                    run_date=context.run_date,
                    analysis=analysis,
                    topic_requests=rewrite_requests,
                )
                executive_summary_result = stage.retry_call(
                    lambda: stage.generate_executive_summary_rewrite(
                        openai_client,
                        model=context.config.runtime.openai_model,
                        request=summary_request,
                        processed_root=processed_root,
                        run_date=context.run_date,
                    ),
                    operation="rewrite_openai_executive_summary",
                    logger=stage.logger,
                )
            except Exception as exc:
                stage.logger.warning(
                    "Skipping LLM executive summary rewrite for %s after failure",
                    context.run_date,
                    exc_info=True,
                )
                quota_warning = stage.build_rewrite_warning(exc)
                if quota_warning is not None:
                    markdown_warnings.append(quota_warning)
                else:
                    raise
            else:
                executive_summary_rewrite = executive_summary_result.executive_summary

    return OpenAIArtifacts(
        watch_next=watch_next,
        topic_rewrites=topic_rewrites,
        executive_summary_rewrite=executive_summary_rewrite,
        warnings=tuple(dict.fromkeys(markdown_warnings)),
        usage=openai_client.usage_summary(),
    )


def run_render_stage(
    context: PipelineRunContext,
    analysis: AnalysisArtifacts,
    openai: OpenAIArtifacts,
    services: PipelineServices,
) -> RenderArtifacts:
    stage = services.render
    digest = stage.build_digest_artifact(
        run_date=context.run_date,
        insights=analysis.insights,
        scoring=context.config.scoring,
        thread_selection=analysis.thread_selection,
        watch_next=openai.watch_next,
        topics=analysis.digest_topics,
    )
    markdown = stage.render_markdown_digest(
        digest=digest,
        reports_root=context.base_path / "reports",
        warnings=openai.warnings,
    )
    llm_markdown = None
    if openai.topic_rewrites or openai.executive_summary_rewrite:
        llm_markdown = stage.render_markdown_digest(
            digest=digest,
            reports_root=context.base_path / "reports",
            topic_rewrites=openai.topic_rewrites,
            executive_summary_rewrite=openai.executive_summary_rewrite,
            variant_suffix="llm",
        )
    return RenderArtifacts(digest=digest, markdown=markdown, llm_markdown=llm_markdown)


def run_delivery_stage(
    context: PipelineRunContext,
    collection: CollectionArtifacts,
    analysis: AnalysisArtifacts,
    openai: OpenAIArtifacts,
    rendered: RenderArtifacts,
    services: PipelineServices,
) -> DeliveryArtifacts:
    stage = services.delivery
    sheets_exported = False
    if not context.skip_sheets:
        stage.retry_call(
            lambda: stage.sheets_exporter_factory(context.config.runtime).export(
                run_date=context.run_date,
                posts=collection.posts,
                insights=analysis.insights,
                digest=rendered.digest,
                scoring=context.config.scoring,
                lookback_hours=context.config.subreddits.fetch.lookback_hours,
                run_at=context.run_at,
            ),
            operation="export_google_sheets",
            logger=stage.logger,
        )
        sheets_exported = True

    teams_published = False
    teams_error = None
    if context.config.runtime.teams_webhook_url:
        preferred_markdown = rendered.llm_markdown or rendered.markdown
        teams_payload = TeamsDigestPayload(
            run_date=context.run_date,
            warnings=openai.warnings,
            topics=tuple(
                TeamsTopicSummary(
                    title=topic.title,
                    source_url=topic.source_url,
                    subreddit=topic.source_subreddit,
                    impact_score=topic.impact_score,
                )
                for topic in rendered.digest.topics
            ),
            emerging_themes=tuple(theme.label for theme in rendered.digest.emerging_themes),
            watch_next=rendered.digest.watch_next,
            openai_usage=openai.usage,
            selected_report_variant="LLM-enhanced" if rendered.llm_markdown is not None else "Deterministic",
            preferred_executive_summary=(
                extract_executive_summary(preferred_markdown.content)
                if rendered.llm_markdown is not None
                else None
            ),
        )
        try:
            stage.retry_call(
                lambda: stage.publish_digest_to_teams(
                    context.config.runtime.teams_webhook_url,
                    teams_payload,
                ),
                operation="publish_teams_digest",
                logger=stage.logger,
            )
        except Exception as exc:
            teams_error = str(exc)
            stage.logger.warning("Skipping Teams webhook publish for %s after failure", context.run_date, exc_info=True)
        else:
            teams_published = True

    return DeliveryArtifacts(
        sheets_exported=sheets_exported,
        teams_published=teams_published,
        teams_error=teams_error,
    )


def run_state_stage(
    context: PipelineRunContext,
    collection: CollectionArtifacts,
    analysis: AnalysisArtifacts,
    rendered: RenderArtifacts,
    delivery: DeliveryArtifacts,
    openai: OpenAIArtifacts,
    services: PipelineServices,
) -> RunState:
    stage = services.state
    state = RunState(
        run_date=context.run_date,
        completed_at=datetime.now(tz=UTC).isoformat(),
        raw_posts_path=str(collection.raw_posts_path.relative_to(context.base_path)),
        raw_comments_path=str(collection.raw_comments_path.relative_to(context.base_path)),
        insights_path=str(analysis.insights_path.relative_to(context.base_path)),
        report_path=str(rendered.markdown.daily_path.relative_to(context.base_path)),
        sheets_exported=delivery.sheets_exported,
        teams_published=delivery.teams_published,
        teams_error=delivery.teams_error,
        openai_usage=openai.usage,
    )
    stage.write_run_state(context.base_path / "data" / "state", state)
    return state


def _build_topic_rewrite_requests(topics: tuple[RankedTopic, ...]) -> tuple[TopicRewriteRequest, ...]:
    return tuple(
        TopicRewriteRequest(
            topic_key=topic.topic_key,
            title=topic.title,
            executive_summary=topic.executive_summary,
            relevance_for_user=topic.relevance_for_user,
            source_title=topic.source_title,
            source_subreddit=topic.source_subreddit,
            source_url=topic.source_url,
            impact_score=topic.impact_score,
            support_count=topic.support_count,
        )
        for topic in topics
    )


def _build_executive_summary_rewrite_request(
    *,
    run_date: str,
    analysis: AnalysisArtifacts,
    topic_requests: tuple[TopicRewriteRequest, ...],
) -> ExecutiveSummaryRewriteRequest:
    represented_subreddits = tuple(dict.fromkeys(item.post.subreddit for item in analysis.thread_selection.ranked_posts))
    return ExecutiveSummaryRewriteRequest(
        run_date=run_date,
        total_posts=len(analysis.thread_selection.ranked_posts),
        represented_subreddits=represented_subreddits,
        top_topic_title=analysis.digest_topics[0].title if analysis.digest_topics else None,
        topics=topic_requests,
    )
