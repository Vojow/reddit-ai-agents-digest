from __future__ import annotations

from datetime import UTC
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from reddit_digest.config import AppConfig
from reddit_digest.config import FetchConfig
from reddit_digest.config import load_scoring_config
from reddit_digest.config import RuntimeConfig
from reddit_digest.config import SubredditConfig
from reddit_digest.models.insight import Insight
from reddit_digest.models.openai_usage import OpenAIUsageSummary
from reddit_digest.models.post import Post
from reddit_digest.outputs.digest import DigestArtifact
from reddit_digest.outputs.digest import DigestThread
from reddit_digest.outputs.digest import EmergingTheme
from reddit_digest.outputs.digest import RankedTopic
from reddit_digest.outputs.markdown import MarkdownDigestResult
from reddit_digest.outputs.teams import TeamsDigestPayload
from reddit_digest.pipeline_stages import AnalysisArtifacts
from reddit_digest.pipeline_stages import AnalysisStageServices
from reddit_digest.pipeline_stages import CollectionStageServices
from reddit_digest.pipeline_stages import CollectionArtifacts
from reddit_digest.pipeline_stages import DeliveryStageServices
from reddit_digest.pipeline_stages import DeliveryArtifacts
from reddit_digest.pipeline_stages import OpenAIArtifacts
from reddit_digest.pipeline_stages import OpenAIStageServices
from reddit_digest.pipeline_stages import PipelineRunContext
from reddit_digest.pipeline_stages import PipelineServices
from reddit_digest.pipeline_stages import RenderStageServices
from reddit_digest.pipeline_stages import RenderArtifacts
from reddit_digest.pipeline_stages import StateStageServices
from reddit_digest.pipeline_stages import run_analysis_stage
from reddit_digest.pipeline_stages import run_collection_stage
from reddit_digest.pipeline_stages import run_delivery_stage
from reddit_digest.pipeline_stages import run_openai_stage
from reddit_digest.pipeline_stages import run_render_stage
from reddit_digest.pipeline_stages import run_state_stage
from reddit_digest.ranking.impact import ScoreBreakdown
from reddit_digest.ranking.threads import RankedPost
from reddit_digest.ranking.threads import SubredditThreadRanking
from reddit_digest.ranking.threads import ThreadSelection
from reddit_digest.utils.state import write_run_state


def test_collection_stage_returns_explicit_collection_artifacts(tmp_path: Path) -> None:
    calls: dict[str, object] = {}
    posts = (_build_post("post_001", subreddit="Codex"),)
    comments = (SimpleNamespace(id="comment_001"),)
    raw_posts_path = tmp_path / "data" / "raw" / "posts" / "2026-03-12.json"
    raw_comments_path = tmp_path / "data" / "raw" / "comments" / "2026-03-12.json"

    class FakePostCollector:
        def __init__(self, source: object, raw_root: Path, processed_root: Path) -> None:
            calls["post_source"] = source
            calls["post_raw_root"] = raw_root
            calls["post_processed_root"] = processed_root

        def collect(self, subreddits: SubredditConfig, *, run_at: datetime) -> SimpleNamespace:
            calls["post_subreddits"] = subreddits.enabled_subreddits
            calls["post_run_at"] = run_at
            return SimpleNamespace(posts=posts, raw_path=raw_posts_path)

    class FakeCommentCollector:
        def __init__(self, source: object, raw_root: Path, processed_root: Path) -> None:
            calls["comment_source"] = source
            calls["comment_raw_root"] = raw_root
            calls["comment_processed_root"] = processed_root

        def collect(self, collected_posts: tuple[Post, ...], *, max_comments_per_post: int, run_at: datetime) -> SimpleNamespace:
            calls["comment_posts"] = collected_posts
            calls["comment_limit"] = max_comments_per_post
            calls["comment_run_at"] = run_at
            return SimpleNamespace(comments=comments, raw_path=raw_comments_path)

    services = _build_services(
        post_source_factory=lambda runtime: {"post_runtime": runtime.reddit_user_agent},
        comment_source_factory=lambda runtime: {"comment_runtime": runtime.reddit_user_agent},
        post_collector_factory=FakePostCollector,
        comment_collector_factory=FakeCommentCollector,
    )

    context = _build_context(tmp_path)
    result = run_collection_stage(context, services)

    assert result == CollectionArtifacts(
        posts=posts,
        comments=comments,
        raw_posts_path=raw_posts_path,
        raw_comments_path=raw_comments_path,
    )
    assert calls["post_subreddits"] == ("Codex", "ClaudeCode")
    assert calls["comment_posts"] == posts
    assert calls["comment_limit"] == 5


def test_analysis_stage_returns_thread_selection_topics_and_paths(tmp_path: Path) -> None:
    post = _build_post("post_001", subreddit="Codex")
    insight = _build_insight("post_001")
    insights_path = tmp_path / "data" / "processed" / "insights" / "2026-03-12.json"
    thread_selection = _build_thread_selection(post)
    captured: dict[str, object] = {}

    services = _build_services(
        extract_insights=lambda posts, comments, **kwargs: captured.update(
            {"extract": (posts, comments, kwargs)}
        )
        or SimpleNamespace(insights=(insight,)),
        apply_novelty=lambda processed_root, **kwargs: captured.update(
            {"novelty": (processed_root, kwargs)}
        )
        or SimpleNamespace(insights=(insight,), path=insights_path),
        select_threads=lambda posts, **kwargs: captured.update(
            {"threads": (posts, kwargs)}
        )
        or thread_selection,
        select_digest_topics=lambda **kwargs: captured.update({"topics": kwargs})
        or (
            RankedTopic(
                topic_key="topic_1",
                title="Topic One",
                executive_summary="Summary",
                relevance_for_user="Relevance",
                source_title=post.title,
                source_url=post.url,
                source_subreddit=post.subreddit,
                impact_score=1.4,
                support_count=1,
            ),
        ),
    )

    result = run_analysis_stage(
        _build_context(tmp_path),
        CollectionArtifacts(
            posts=(post,),
            comments=(SimpleNamespace(id="comment_001"),),
            raw_posts_path=tmp_path / "data" / "raw" / "posts" / "2026-03-12.json",
            raw_comments_path=tmp_path / "data" / "raw" / "comments" / "2026-03-12.json",
        ),
        services,
    )

    assert result.insights == (insight,)
    assert result.insights_path == insights_path
    assert result.thread_selection == thread_selection
    assert result.digest_topics[0].topic_key == "topic_1"
    assert captured["threads"][1]["enabled_subreddits"] == ("Codex", "ClaudeCode")


def test_openai_stage_returns_warning_and_skips_rewrites_on_quota_error(tmp_path: Path) -> None:
    usage = OpenAIUsageSummary.empty()

    class FakeLogger:
        def __init__(self) -> None:
            self.messages: list[str] = []

        def warning(self, message: str, *args, **_kwargs) -> None:
            self.messages.append(message % args)

    class FakeOpenAIClient:
        def usage_summary(self) -> OpenAIUsageSummary:
            return usage

    services = _build_services(
        logger=FakeLogger(),
        build_openai_client=lambda _runtime: FakeOpenAIClient(),
        generate_suggestions=lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("insufficient_quota")),
        generate_topic_rewrites=lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("should not run")),
        generate_executive_summary_rewrite=lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("should not run")),
        build_suggestion_warning=lambda exc: f"warning:{exc}",
        build_rewrite_warning=lambda exc: f"rewrite:{exc}",
    )

    result = run_openai_stage(
        _build_context(tmp_path, openai_api_key="test-key"),
        CollectionArtifacts(
            posts=(_build_post("post_001", subreddit="Codex"),),
            comments=(),
            raw_posts_path=tmp_path / "data" / "raw" / "posts" / "2026-03-12.json",
            raw_comments_path=tmp_path / "data" / "raw" / "comments" / "2026-03-12.json",
        ),
        AnalysisArtifacts(
            insights=(_build_insight("post_001"),),
            insights_path=tmp_path / "data" / "processed" / "insights" / "2026-03-12.json",
            thread_selection=_build_thread_selection(_build_post("post_001", subreddit="Codex")),
            digest_topics=(
                RankedTopic(
                    topic_key="topic_1",
                    title="Topic One",
                    executive_summary="Summary",
                    relevance_for_user="Relevance",
                    source_title="Codex thread",
                    source_url="https://reddit.com/r/Codex/comments/post_001",
                    source_subreddit="Codex",
                    impact_score=1.4,
                    support_count=1,
                ),
            ),
        ),
        services,
    )

    assert result == OpenAIArtifacts(
        watch_next=(),
        topic_rewrites={},
        executive_summary_rewrite=None,
        warnings=("warning:insufficient_quota",),
        usage=usage,
    )


def test_openai_stage_reraises_non_quota_executive_summary_failures(tmp_path: Path) -> None:
    class FakeLogger:
        def warning(self, *_args, **_kwargs) -> None:
            return None

    class FakeOpenAIClient:
        def usage_summary(self) -> OpenAIUsageSummary:
            return OpenAIUsageSummary.empty()

    services = _build_services(
        logger=FakeLogger(),
        build_openai_client=lambda _runtime: FakeOpenAIClient(),
        generate_suggestions=lambda *_args, **_kwargs: SimpleNamespace(suggestions=()),
        generate_topic_rewrites=lambda *_args, **_kwargs: SimpleNamespace(
            rewrites=(SimpleNamespace(topic_key="topic_1", executive_summary="summary", relevance_for_user="relevance"),)
        ),
        generate_executive_summary_rewrite=lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("bad schema")),
        build_suggestion_warning=lambda exc: f"warning:{exc}",
        build_rewrite_warning=lambda _exc: None,
    )

    with pytest.raises(RuntimeError, match="bad schema"):
        run_openai_stage(
            _build_context(tmp_path, openai_api_key="test-key"),
            CollectionArtifacts(
                posts=(_build_post("post_001", subreddit="Codex"),),
                comments=(),
                raw_posts_path=tmp_path / "data" / "raw" / "posts" / "2026-03-12.json",
                raw_comments_path=tmp_path / "data" / "raw" / "comments" / "2026-03-12.json",
            ),
            AnalysisArtifacts(
                insights=(_build_insight("post_001"),),
                insights_path=tmp_path / "data" / "processed" / "insights" / "2026-03-12.json",
                thread_selection=_build_thread_selection(_build_post("post_001", subreddit="Codex")),
                digest_topics=(
                    RankedTopic(
                        topic_key="topic_1",
                        title="Topic One",
                        executive_summary="Summary",
                        relevance_for_user="Relevance",
                        source_title="Codex thread",
                        source_url="https://reddit.com/r/Codex/comments/post_001",
                        source_subreddit="Codex",
                        impact_score=1.4,
                        support_count=1,
                    ),
                ),
            ),
            services,
        )


def test_render_stage_returns_digest_and_optional_llm_variant(tmp_path: Path) -> None:
    digest = DigestArtifact(
        run_date="2026-03-12",
        total_posts=1,
        total_insights=1,
        represented_subreddits=("Codex",),
        top_topic_title="Topic One",
        top_tool="",
        top_approach="",
        top_guide="",
        top_testing_insight="",
        topics=(),
        notable_threads=(DigestThread(title="Codex thread", url="https://example.com", subreddit="Codex", impact_score=1.2),),
        emerging_themes=(EmergingTheme(label="agents", evidence="evidence", support_count=1, total_impact=1.2, evidence_titles=("Topic One",)),),
        watch_next=("Track tomorrow",),
    )
    calls: list[dict[str, object]] = []

    def fake_renderer(**kwargs) -> MarkdownDigestResult:
        calls.append(kwargs)
        suffix = kwargs.get("variant_suffix", "")
        name = "2026-03-12.llm.md" if suffix == "llm" else "2026-03-12.md"
        latest = "latest.llm.md" if suffix == "llm" else "latest.md"
        return MarkdownDigestResult(
            daily_path=tmp_path / "reports" / "daily" / name,
            latest_path=tmp_path / "reports" / latest,
            content=name,
        )

    services = _build_services(
        build_digest_artifact=lambda **_kwargs: digest,
        render_markdown_digest=fake_renderer,
    )

    result = run_render_stage(
        _build_context(tmp_path),
        AnalysisArtifacts(
            insights=(_build_insight("post_001"),),
            insights_path=tmp_path / "data" / "processed" / "insights" / "2026-03-12.json",
            thread_selection=_build_thread_selection(_build_post("post_001", subreddit="Codex")),
            digest_topics=(),
        ),
        OpenAIArtifacts(
            watch_next=("Track tomorrow",),
            topic_rewrites={"topic_1": ("summary", "relevance")},
            executive_summary_rewrite="Three workflow-specific topics stand out across Codex today.",
            warnings=("warning",),
            usage=OpenAIUsageSummary.empty(),
        ),
        services,
    )

    assert result.digest == digest
    assert result.markdown.daily_path.name == "2026-03-12.md"
    assert result.llm_markdown is not None
    assert result.llm_markdown.daily_path.name == "2026-03-12.llm.md"
    assert calls[0]["warnings"] == ("warning",)
    assert calls[0]["digest"] == digest
    assert calls[1]["executive_summary_rewrite"] == "Three workflow-specific topics stand out across Codex today."
    assert calls[1]["variant_suffix"] == "llm"


def test_delivery_stage_handles_optional_exports_and_teams_publish(tmp_path: Path) -> None:
    exported: dict[str, object] = {}
    published: dict[str, object] = {}

    class FakeExporter:
        def export(self, **kwargs) -> None:
            exported.update(kwargs)

    services = _build_services(
        sheets_exporter_factory=lambda _runtime: FakeExporter(),
        publish_digest_to_teams=lambda url, payload: published.update({"url": url, "payload": payload}),
    )

    post = _build_post("post_001", subreddit="Codex")
    result = run_delivery_stage(
        _build_context(tmp_path, teams_webhook_url="https://contoso.example/webhook", skip_sheets=False),
        CollectionArtifacts(
            posts=(post,),
            comments=(),
            raw_posts_path=tmp_path / "data" / "raw" / "posts" / "2026-03-12.json",
            raw_comments_path=tmp_path / "data" / "raw" / "comments" / "2026-03-12.json",
        ),
        AnalysisArtifacts(
            insights=(_build_insight("post_001"),),
            insights_path=tmp_path / "data" / "processed" / "insights" / "2026-03-12.json",
            thread_selection=_build_thread_selection(post),
            digest_topics=(
                RankedTopic(
                    topic_key="topic_1",
                    title="Topic One",
                    executive_summary="Summary",
                    relevance_for_user="Relevance",
                    source_title=post.title,
                    source_url=post.url,
                    source_subreddit=post.subreddit,
                    impact_score=1.4,
                    support_count=1,
                ),
            ),
        ),
        OpenAIArtifacts(
            watch_next=("Track tomorrow",),
            topic_rewrites={},
            executive_summary_rewrite=None,
            warnings=("warning",),
            usage=OpenAIUsageSummary.empty(),
        ),
        RenderArtifacts(
            digest=DigestArtifact(
                run_date="2026-03-12",
                total_posts=1,
                total_insights=1,
                represented_subreddits=("Codex",),
                top_topic_title="Topic One",
                top_tool="",
                top_approach="",
                top_guide="",
                top_testing_insight="",
                topics=(
                    RankedTopic(
                        topic_key="topic_1",
                        title="Topic One",
                        executive_summary="Summary",
                        relevance_for_user="Relevance",
                        source_title=post.title,
                        source_url=post.url,
                        source_subreddit=post.subreddit,
                        impact_score=1.4,
                        support_count=1,
                    ),
                ),
                notable_threads=(DigestThread(title=post.title, url=post.url, subreddit=post.subreddit, impact_score=1.4),),
                emerging_themes=(),
                watch_next=("Track tomorrow",),
            ),
            markdown=MarkdownDigestResult(
                daily_path=tmp_path / "reports" / "daily" / "2026-03-12.md",
                latest_path=tmp_path / "reports" / "latest.md",
                content="deterministic",
            ),
            llm_markdown=MarkdownDigestResult(
                daily_path=tmp_path / "reports" / "daily" / "2026-03-12.llm.md",
                latest_path=tmp_path / "reports" / "latest.llm.md",
                content="llm",
            ),
        ),
        services,
    )

    assert result == DeliveryArtifacts(sheets_exported=True, teams_published=True, teams_error=None)
    assert exported["posts"] == (post,)
    assert published["url"] == "https://contoso.example/webhook"
    assert isinstance(published["payload"], TeamsDigestPayload)
    assert published["payload"].selected_report_variant == "LLM-enhanced"
    assert published["payload"].preferred_executive_summary is None


def test_state_stage_writes_run_state_from_stage_artifacts(tmp_path: Path) -> None:
    post = _build_post("post_001", subreddit="Codex")
    raw_posts_path = tmp_path / "data" / "raw" / "posts" / "2026-03-12.json"
    raw_comments_path = tmp_path / "data" / "raw" / "comments" / "2026-03-12.json"
    insights_path = tmp_path / "data" / "processed" / "insights" / "2026-03-12.json"
    markdown_path = tmp_path / "reports" / "daily" / "2026-03-12.md"
    for path in (raw_posts_path, raw_comments_path, insights_path, markdown_path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("[]")

    state = run_state_stage(
        _build_context(tmp_path),
        CollectionArtifacts(
            posts=(post,),
            comments=(),
            raw_posts_path=raw_posts_path,
            raw_comments_path=raw_comments_path,
        ),
        AnalysisArtifacts(
            insights=(_build_insight("post_001"),),
            insights_path=insights_path,
            thread_selection=_build_thread_selection(post),
            digest_topics=(),
        ),
        RenderArtifacts(
            digest=DigestArtifact(
                run_date="2026-03-12",
                total_posts=1,
                total_insights=1,
                represented_subreddits=("Codex",),
                top_topic_title="Topic One",
                top_tool="",
                top_approach="",
                top_guide="",
                top_testing_insight="",
                topics=(),
                notable_threads=(),
                emerging_themes=(),
                watch_next=(),
            ),
            markdown=MarkdownDigestResult(
                daily_path=markdown_path,
                latest_path=tmp_path / "reports" / "latest.md",
                content="deterministic",
            ),
            llm_markdown=None,
        ),
        DeliveryArtifacts(
            sheets_exported=False,
            teams_published=False,
            teams_error=None,
        ),
        OpenAIArtifacts(
            watch_next=(),
            topic_rewrites={},
            executive_summary_rewrite=None,
            warnings=(),
            usage=OpenAIUsageSummary.empty(),
        ),
        _build_services(write_run_state=write_run_state),
    )

    assert state.report_path == "reports/daily/2026-03-12.md"
    assert (tmp_path / "data" / "state" / "2026-03-12.json").exists()
    assert (tmp_path / "data" / "state" / "latest.json").exists()


def _build_services(**overrides: object) -> PipelineServices:
    defaults: dict[str, object] = {
        "logger": SimpleNamespace(warning=lambda *_args, **_kwargs: None),
        "retry_call": lambda func, **_kwargs: func(),
        "post_source_factory": lambda runtime: {"post_runtime": runtime.reddit_user_agent},
        "comment_source_factory": lambda runtime: {"comment_runtime": runtime.reddit_user_agent},
        "post_collector_factory": lambda *_args, **_kwargs: SimpleNamespace(
            collect=lambda *_args, **_kwargs: SimpleNamespace(
                posts=(),
                raw_path=Path("/tmp/raw-posts.json"),
            )
        ),
        "comment_collector_factory": lambda *_args, **_kwargs: SimpleNamespace(
            collect=lambda *_args, **_kwargs: SimpleNamespace(
                comments=(),
                raw_path=Path("/tmp/raw-comments.json"),
            )
        ),
        "extract_insights": lambda *_args, **_kwargs: SimpleNamespace(insights=()),
        "apply_novelty": lambda *_args, **_kwargs: SimpleNamespace(insights=(), path=Path("/tmp/insights.json")),
        "select_threads": lambda *_args, **_kwargs: _build_thread_selection(_build_post("default", subreddit="Codex")),
        "select_digest_topics": lambda **_kwargs: (),
        "build_openai_client": lambda _runtime: SimpleNamespace(usage_summary=OpenAIUsageSummary.empty),
        "generate_suggestions": lambda *_args, **_kwargs: SimpleNamespace(suggestions=()),
        "generate_topic_rewrites": lambda *_args, **_kwargs: SimpleNamespace(rewrites=()),
        "generate_executive_summary_rewrite": lambda *_args, **_kwargs: SimpleNamespace(executive_summary="summary"),
        "build_suggestion_warning": lambda _exc: None,
        "build_rewrite_warning": lambda _exc: None,
        "build_digest_artifact": lambda **_kwargs: DigestArtifact(
            run_date="2026-03-12",
            total_posts=0,
            total_insights=0,
            represented_subreddits=(),
            top_topic_title=None,
            top_tool="",
            top_approach="",
            top_guide="",
            top_testing_insight="",
            topics=(),
            notable_threads=(),
            emerging_themes=(),
            watch_next=(),
        ),
        "render_markdown_digest": lambda **_kwargs: MarkdownDigestResult(
            daily_path=Path("/tmp/reports/daily/2026-03-12.md"),
            latest_path=Path("/tmp/reports/latest.md"),
            content="digest",
        ),
        "sheets_exporter_factory": lambda _runtime: SimpleNamespace(export=lambda **_kwargs: None),
        "publish_digest_to_teams": lambda *_args, **_kwargs: None,
        "write_run_state": lambda *_args, **_kwargs: None,
    }
    defaults.update(overrides)
    return PipelineServices(
        collection=CollectionStageServices(
            logger=defaults["logger"],
            retry_call=defaults["retry_call"],
            post_source_factory=defaults["post_source_factory"],
            comment_source_factory=defaults["comment_source_factory"],
            post_collector_factory=defaults["post_collector_factory"],
            comment_collector_factory=defaults["comment_collector_factory"],
        ),
        analysis=AnalysisStageServices(
            extract_insights=defaults["extract_insights"],
            apply_novelty=defaults["apply_novelty"],
            select_threads=defaults["select_threads"],
            select_digest_topics=defaults["select_digest_topics"],
        ),
        openai=OpenAIStageServices(
            logger=defaults["logger"],
            retry_call=defaults["retry_call"],
            build_openai_client=defaults["build_openai_client"],
            generate_suggestions=defaults["generate_suggestions"],
            generate_topic_rewrites=defaults["generate_topic_rewrites"],
            generate_executive_summary_rewrite=defaults["generate_executive_summary_rewrite"],
            build_suggestion_warning=defaults["build_suggestion_warning"],
            build_rewrite_warning=defaults["build_rewrite_warning"],
        ),
        render=RenderStageServices(
            build_digest_artifact=defaults["build_digest_artifact"],
            render_markdown_digest=defaults["render_markdown_digest"],
        ),
        delivery=DeliveryStageServices(
            logger=defaults["logger"],
            retry_call=defaults["retry_call"],
            sheets_exporter_factory=defaults["sheets_exporter_factory"],
            publish_digest_to_teams=defaults["publish_digest_to_teams"],
        ),
        state=StateStageServices(
            write_run_state=defaults["write_run_state"],
        ),
    )


def _build_context(
    base_path: Path,
    *,
    openai_api_key: str | None = None,
    teams_webhook_url: str | None = None,
    skip_sheets: bool = True,
) -> PipelineRunContext:
    return PipelineRunContext.build(
        base_path=base_path,
        config=AppConfig(
            subreddits=SubredditConfig(
                primary=("Codex",),
                secondary=("ClaudeCode",),
                include_secondary=True,
                fetch=FetchConfig(
                    lookback_hours=24,
                    sort_modes=("new",),
                    min_post_score=0,
                    min_comments=0,
                    max_posts_per_subreddit=5,
                    max_comments_per_post=5,
                ),
            ),
            scoring=load_scoring_config(Path.cwd() / "config" / "scoring.yaml"),
            runtime=RuntimeConfig(
                reddit_client_id=None,
                reddit_client_secret=None,
                reddit_user_agent="digest-test",
                openai_api_key=openai_api_key,
                openai_model="gpt-5-mini",
                teams_webhook_url=teams_webhook_url,
                gcp_workload_identity_provider=None,
                gcp_service_account_email=None,
                google_service_account_json=None,
                google_sheets_spreadsheet_id=None,
            ),
        ),
        run_date="2026-03-12",
        skip_sheets=skip_sheets,
    )


def _build_post(post_id: str, *, subreddit: str) -> Post:
    return Post.from_raw(
        {
            "id": post_id,
            "subreddit": subreddit,
            "title": f"{subreddit} thread",
            "author": "tester",
            "score": 10,
            "num_comments": 4,
            "created_utc": int(datetime(2026, 3, 12, 10, 0, tzinfo=UTC).timestamp()),
            "url": f"https://reddit.com/r/{subreddit}/comments/{post_id}",
            "permalink": f"/r/{subreddit}/comments/{post_id}",
            "selftext": "Agent workflow notes",
        }
    )


def _build_insight(source_post_id: str) -> Insight:
    return Insight.from_raw(
        {
            "category": "approaches",
            "title": "Topic One",
            "summary": "Summary",
            "tags": ["workflow"],
            "evidence": "Evidence",
            "source_kind": "post",
            "source_id": source_post_id,
            "source_post_id": source_post_id,
            "source_permalink": f"https://reddit.com/comments/{source_post_id}",
            "subreddit": "Codex",
            "why_it_matters": "Relevance",
            "novelty": "new",
        }
    )


def _build_thread_selection(post: Post) -> ThreadSelection:
    ranked = RankedPost(
        post=post,
        breakdown=ScoreBreakdown(
            components={"relevance": 1.0},
            total=1.4,
        ),
    )
    ranking = SubredditThreadRanking(
        subreddit=post.subreddit,
        posts=(ranked,),
    )
    return ThreadSelection(
        ranked_posts=(ranked,),
        notable_threads=(ranked,),
        by_subreddit=(ranking,),
    )
