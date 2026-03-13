"""Pipeline orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import logging

from openai import APIStatusError
from openai import RateLimitError

from reddit_digest.collectors.reddit_comments import CommentCollector
from reddit_digest.collectors.reddit_comments import PublicRedditCommentSource
from reddit_digest.collectors.reddit_posts import PostCollector
from reddit_digest.collectors.reddit_posts import PublicRedditPostSource
from reddit_digest.config import load_config
from reddit_digest.extractors.openai_suggestions import generate_executive_summary_rewrite
from reddit_digest.extractors.openai_suggestions import generate_suggestions
from reddit_digest.extractors.openai_suggestions import generate_topic_rewrites
from reddit_digest.extractors.service import extract_insights
from reddit_digest.models.openai_usage import OpenAIUsageSummary
from reddit_digest.openai_client import build_openai_client
from reddit_digest.outputs.digest import build_digest_artifact
from reddit_digest.outputs.digest import select_digest_topics
from reddit_digest.outputs.google_sheets import GoogleSheetsExporter
from reddit_digest.outputs.markdown import render_markdown_digest
from reddit_digest.outputs.teams import publish_digest_to_teams
from reddit_digest.pipeline_stages import AnalysisStageServices
from reddit_digest.pipeline_stages import CollectionStageServices
from reddit_digest.pipeline_stages import DeliveryStageServices
from reddit_digest.pipeline_stages import OpenAIStageServices
from reddit_digest.pipeline_stages import PipelineRunContext
from reddit_digest.pipeline_stages import PipelineServices
from reddit_digest.pipeline_stages import RenderStageServices
from reddit_digest.pipeline_stages import StateStageServices
from reddit_digest.pipeline_stages import run_analysis_stage
from reddit_digest.pipeline_stages import run_collection_stage
from reddit_digest.pipeline_stages import run_delivery_stage
from reddit_digest.pipeline_stages import run_openai_stage
from reddit_digest.pipeline_stages import run_render_stage
from reddit_digest.pipeline_stages import run_state_stage
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
        context = PipelineRunContext.build(
            base_path=self.base_path,
            config=config,
            run_date=run_date,
            skip_sheets=skip_sheets,
        )
        services = _compose_services()

        collection = run_collection_stage(context, services)
        analysis = run_analysis_stage(context, collection, services)
        openai = run_openai_stage(context, collection, analysis, services)
        rendered = run_render_stage(context, analysis, openai, services)
        delivery = run_delivery_stage(context, collection, analysis, openai, rendered, services)
        state = run_state_stage(context, collection, analysis, rendered, delivery, openai, services)

        _log_openai_usage_summary(openai.usage)
        LOGGER.info("Pipeline completed for %s", run_date)
        return state


def _compose_services() -> PipelineServices:
    return PipelineServices(
        collection=CollectionStageServices(
            logger=LOGGER,
            retry_call=retry_call,
            post_source_factory=PublicRedditPostSource,
            comment_source_factory=PublicRedditCommentSource,
            post_collector_factory=PostCollector,
            comment_collector_factory=CommentCollector,
        ),
        analysis=AnalysisStageServices(
            extract_insights=extract_insights,
            apply_novelty=apply_novelty,
            select_threads=select_threads,
            select_digest_topics=select_digest_topics,
        ),
        openai=OpenAIStageServices(
            logger=LOGGER,
            retry_call=retry_call,
            build_openai_client=build_openai_client,
            generate_suggestions=generate_suggestions,
            generate_topic_rewrites=generate_topic_rewrites,
            generate_executive_summary_rewrite=generate_executive_summary_rewrite,
            build_suggestion_warning=lambda exc: _build_openai_warning(
                exc,
                skipped_steps="Watch Next suggestions, LLM topic rewrites, and LLM executive summary rewrites",
            ),
            build_rewrite_warning=lambda exc: _build_openai_warning(
                exc,
                skipped_steps="LLM topic rewrites and LLM executive summary rewrites",
            ),
        ),
        render=RenderStageServices(
            build_digest_artifact=build_digest_artifact,
            render_markdown_digest=render_markdown_digest,
        ),
        delivery=DeliveryStageServices(
            logger=LOGGER,
            retry_call=retry_call,
            sheets_exporter_factory=GoogleSheetsExporter.from_runtime,
            publish_digest_to_teams=publish_digest_to_teams,
        ),
        state=StateStageServices(
            write_run_state=write_run_state,
        ),
    )


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


def _log_openai_usage_summary(usage: OpenAIUsageSummary) -> None:
    LOGGER.info(
        "OpenAI usage totals: calls=%s input_tokens=%s output_tokens=%s total_tokens=%s",
        usage.total_calls,
        usage.input_tokens,
        usage.output_tokens,
        usage.total_tokens,
    )
    for operation in usage.operations:
        LOGGER.info(
            "OpenAI usage for %s: calls=%s input_tokens=%s output_tokens=%s total_tokens=%s",
            operation.operation,
            operation.calls,
            operation.input_tokens,
            operation.output_tokens,
            operation.total_tokens,
        )
