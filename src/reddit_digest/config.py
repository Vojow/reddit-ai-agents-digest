"""Configuration loading and validation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
from typing import Any

import yaml


class ConfigError(ValueError):
    """Raised when project configuration is invalid."""


@dataclass(frozen=True)
class FetchConfig:
    lookback_hours: int
    sort_modes: tuple[str, ...]
    min_post_score: int
    min_comments: int
    max_posts_per_subreddit: int
    max_comments_per_post: int


@dataclass(frozen=True)
class SubredditConfig:
    primary: tuple[str, ...]
    secondary: tuple[str, ...]
    include_secondary: bool
    fetch: FetchConfig

    @property
    def enabled_subreddits(self) -> tuple[str, ...]:
        if self.include_secondary:
            return self.primary + self.secondary
        return self.primary


@dataclass(frozen=True)
class ScoringConfig:
    weights: dict[str, float]
    tags: tuple[str, ...]


@dataclass(frozen=True)
class RuntimeConfig:
    reddit_client_id: str | None
    reddit_client_secret: str | None
    reddit_user_agent: str | None
    openai_api_key: str | None
    openai_model: str
    gcp_workload_identity_provider: str | None
    gcp_service_account_email: str | None
    google_service_account_json: str | None
    google_sheets_spreadsheet_id: str | None


@dataclass(frozen=True)
class AppConfig:
    subreddits: SubredditConfig
    scoring: ScoringConfig
    runtime: RuntimeConfig


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        payload = yaml.safe_load(path.read_text())
    except FileNotFoundError as exc:
        raise ConfigError(f"Config file not found: {path}") from exc
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML in {path}: {exc}") from exc

    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise ConfigError(f"Expected a mapping at the top of {path}")
    return payload


def _require_list(payload: dict[str, Any], key: str, *, path: Path) -> list[str]:
    value = payload.get(key)
    if not isinstance(value, list) or not value:
        raise ConfigError(f"{path}: '{key}' must be a non-empty list")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise ConfigError(f"{path}: '{key}' entries must be non-empty strings")
    return value


def _optional_list(payload: dict[str, Any], key: str, *, path: Path) -> list[str]:
    value = payload.get(key, [])
    if not isinstance(value, list):
        raise ConfigError(f"{path}: '{key}' must be a list")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise ConfigError(f"{path}: '{key}' entries must be non-empty strings")
    return value


def _require_int(payload: dict[str, Any], key: str, *, path: Path) -> int:
    value = payload.get(key)
    if not isinstance(value, int):
        raise ConfigError(f"{path}: '{key}' must be an integer")
    return value


def _require_positive_int(payload: dict[str, Any], key: str, *, path: Path) -> int:
    value = _require_int(payload, key, path=path)
    if value <= 0:
        raise ConfigError(f"{path}: '{key}' must be greater than 0")
    return value


def _require_non_negative_int(payload: dict[str, Any], key: str, *, path: Path) -> int:
    value = _require_int(payload, key, path=path)
    if value < 0:
        raise ConfigError(f"{path}: '{key}' must be greater than or equal to 0")
    return value


def _require_float_map(payload: dict[str, Any], key: str, *, path: Path) -> dict[str, float]:
    value = payload.get(key)
    if not isinstance(value, dict) or not value:
        raise ConfigError(f"{path}: '{key}' must be a non-empty mapping")

    normalized: dict[str, float] = {}
    for name, weight in value.items():
        if not isinstance(name, str) or not name.strip():
            raise ConfigError(f"{path}: '{key}' keys must be non-empty strings")
        if not isinstance(weight, (int, float)):
            raise ConfigError(f"{path}: '{key}.{name}' must be numeric")
        normalized[name] = float(weight)
    return normalized


def _env_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default

    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ConfigError(f"Environment variable {name} must be a boolean value")


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigError(f"Environment variable {name} must be an integer") from exc
    if value <= 0:
        raise ConfigError(f"Environment variable {name} must be greater than 0")
    return value


def _env_non_negative_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigError(f"Environment variable {name} must be an integer") from exc
    if value < 0:
        raise ConfigError(f"Environment variable {name} must be greater than or equal to 0")
    return value


def _env_optional(name: str) -> str | None:
    value = os.getenv(name)
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _require_env(name: str) -> str:
    value = _env_optional(name)
    if value is None:
        raise ConfigError(f"Missing required environment variable: {name}")
    return value


def load_subreddit_config(path: Path) -> SubredditConfig:
    payload = _read_yaml(path)
    fetch = payload.get("fetch")
    flags = payload.get("mvp_enabled")

    if not isinstance(fetch, dict):
        raise ConfigError(f"{path}: 'fetch' must be a mapping")
    if not isinstance(flags, dict):
        raise ConfigError(f"{path}: 'mvp_enabled' must be a mapping")

    include_secondary = flags.get("include_secondary")
    if not isinstance(include_secondary, bool):
        raise ConfigError(f"{path}: 'mvp_enabled.include_secondary' must be a boolean")

    sort_modes = fetch.get("sort_modes")
    if not isinstance(sort_modes, list) or not sort_modes:
        raise ConfigError(f"{path}: 'fetch.sort_modes' must be a non-empty list")
    if any(not isinstance(item, str) or not item.strip() for item in sort_modes):
        raise ConfigError(f"{path}: 'fetch.sort_modes' entries must be non-empty strings")

    parsed_fetch = FetchConfig(
        lookback_hours=_env_int("LOOKBACK_HOURS", _require_positive_int(fetch, "lookback_hours", path=path)),
        sort_modes=tuple(sort_modes),
        min_post_score=_env_non_negative_int(
            "MIN_POST_SCORE",
            _require_non_negative_int(fetch, "min_post_score", path=path),
        ),
        min_comments=_env_non_negative_int(
            "MIN_COMMENTS",
            _require_non_negative_int(fetch, "min_comments", path=path),
        ),
        max_posts_per_subreddit=_env_int(
            "MAX_POSTS_PER_SUBREDDIT",
            _require_positive_int(fetch, "max_posts_per_subreddit", path=path),
        ),
        max_comments_per_post=_env_int(
            "MAX_COMMENTS_PER_POST",
            _require_positive_int(fetch, "max_comments_per_post", path=path),
        ),
    )

    return SubredditConfig(
        primary=tuple(_require_list(payload, "primary", path=path)),
        secondary=tuple(_optional_list(payload, "secondary", path=path)),
        include_secondary=_env_flag("INCLUDE_SECONDARY_SUBREDDITS", include_secondary),
        fetch=parsed_fetch,
    )


def load_scoring_config(path: Path) -> ScoringConfig:
    payload = _read_yaml(path)
    tags = payload.get("tags")
    if not isinstance(tags, list) or not tags:
        raise ConfigError(f"{path}: 'tags' must be a non-empty list")
    if any(not isinstance(item, str) or not item.strip() for item in tags):
        raise ConfigError(f"{path}: 'tags' entries must be non-empty strings")

    return ScoringConfig(
        weights=_require_float_map(payload, "weights", path=path),
        tags=tuple(tags),
    )


def load_runtime_config(*, require_reddit: bool = False, require_openai: bool = False, require_sheets: bool = False) -> RuntimeConfig:
    runtime = RuntimeConfig(
        reddit_client_id=_env_optional("REDDIT_CLIENT_ID"),
        reddit_client_secret=_env_optional("REDDIT_CLIENT_SECRET"),
        reddit_user_agent=_env_optional("REDDIT_USER_AGENT"),
        openai_api_key=_env_optional("OPENAI_API_KEY"),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-5-mini"),
        gcp_workload_identity_provider=_env_optional("GCP_WORKLOAD_IDENTITY_PROVIDER"),
        gcp_service_account_email=_env_optional("GCP_SERVICE_ACCOUNT_EMAIL"),
        google_service_account_json=_env_optional("GOOGLE_SERVICE_ACCOUNT_JSON"),
        google_sheets_spreadsheet_id=_env_optional("GOOGLE_SHEETS_SPREADSHEET_ID"),
    )

    if require_reddit:
        _require_env("REDDIT_USER_AGENT")
    if require_openai:
        _require_env("OPENAI_API_KEY")
    if require_sheets:
        _require_env("GOOGLE_SHEETS_SPREADSHEET_ID")

    return runtime


def load_config(
    base_path: Path | None = None,
    *,
    require_reddit: bool = False,
    require_openai: bool = False,
    require_sheets: bool = False,
) -> AppConfig:
    root = base_path or Path.cwd()
    config_dir = root / "config"
    return AppConfig(
        subreddits=load_subreddit_config(config_dir / "subreddits.yaml"),
        scoring=load_scoring_config(config_dir / "scoring.yaml"),
        runtime=load_runtime_config(
            require_reddit=require_reddit,
            require_openai=require_openai,
            require_sheets=require_sheets,
        ),
    )
