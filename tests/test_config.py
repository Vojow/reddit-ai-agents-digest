from __future__ import annotations

from pathlib import Path

import pytest

from reddit_digest.config import ConfigError, load_config, load_runtime_config, load_scoring_config, load_subreddit_config


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def test_load_config_from_repo_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("INCLUDE_SECONDARY_SUBREDDITS", raising=False)
    config = load_config(Path.cwd())

    assert config.subreddits.primary == ("Codex", "ClaudeCode", "Vibecoding")
    assert config.subreddits.enabled_subreddits == ("Codex", "ClaudeCode", "Vibecoding")
    assert config.scoring.weights["relevance"] == pytest.approx(0.30)
    assert config.runtime.openai_model == "gpt-5-mini"


def test_env_overrides_runtime_and_fetch(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    write_text(
        tmp_path / "config" / "subreddits.yaml",
        """
primary:
  - Codex
secondary:
  - LocalLLaMA
mvp_enabled:
  include_secondary: false
fetch:
  lookback_hours: 24
  sort_modes: [new]
  min_post_score: 5
  min_comments: 3
  max_posts_per_subreddit: 25
  max_comments_per_post: 50
""".strip(),
    )
    write_text(
        tmp_path / "config" / "scoring.yaml",
        """
weights:
  relevance: 0.5
tags:
  - ai-agents
""".strip(),
    )

    monkeypatch.setenv("INCLUDE_SECONDARY_SUBREDDITS", "true")
    monkeypatch.setenv("LOOKBACK_HOURS", "12")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-5")

    config = load_config(tmp_path)

    assert config.subreddits.include_secondary is True
    assert config.subreddits.enabled_subreddits == ("Codex", "LocalLLaMA")
    assert config.subreddits.fetch.lookback_hours == 12
    assert config.runtime.openai_model == "gpt-5"


def test_invalid_yaml_fails_with_clear_message(tmp_path: Path) -> None:
    bad_config = tmp_path / "subreddits.yaml"
    bad_config.write_text("primary: [Codex\n")

    with pytest.raises(ConfigError, match="Invalid YAML"):
        load_subreddit_config(bad_config)


def test_missing_required_env_fails_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("REDDIT_USER_AGENT", raising=False)

    with pytest.raises(ConfigError, match="REDDIT_USER_AGENT"):
        load_runtime_config(require_reddit=True)


def test_require_sheets_only_needs_spreadsheet_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GOOGLE_SERVICE_ACCOUNT_JSON", raising=False)
    monkeypatch.setenv("GOOGLE_SHEETS_SPREADSHEET_ID", "sheet-123")

    runtime = load_runtime_config(require_sheets=True)

    assert runtime.google_sheets_spreadsheet_id == "sheet-123"


def test_runtime_config_reads_wif_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GCP_WORKLOAD_IDENTITY_PROVIDER", "projects/123/locations/global/workloadIdentityPools/pool/providers/provider")
    monkeypatch.setenv("GCP_SERVICE_ACCOUNT_EMAIL", "digest-bot@example.iam.gserviceaccount.com")

    runtime = load_runtime_config()

    assert runtime.gcp_workload_identity_provider == "projects/123/locations/global/workloadIdentityPools/pool/providers/provider"
    assert runtime.gcp_service_account_email == "digest-bot@example.iam.gserviceaccount.com"


def test_invalid_scoring_config_fails(tmp_path: Path) -> None:
    scoring_path = tmp_path / "scoring.yaml"
    scoring_path.write_text("weights: []\ntags:\n  - ai-agents\n")

    with pytest.raises(ConfigError, match="weights"):
        load_scoring_config(scoring_path)


def test_negative_threshold_override_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MIN_POST_SCORE", "-1")

    with pytest.raises(ConfigError, match="MIN_POST_SCORE"):
        load_subreddit_config(Path.cwd() / "config" / "subreddits.yaml")
