"""Configuration loading and validation."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
import os
import re
import subprocess
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
    teams_webhook_url: str | None
    gcp_workload_identity_provider: str | None
    gcp_service_account_email: str | None
    google_service_account_json: str | None
    google_sheets_spreadsheet_id: str | None


@dataclass(frozen=True)
class AppConfig:
    subreddits: SubredditConfig
    scoring: ScoringConfig
    runtime: RuntimeConfig


ENV_KEY_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


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


def _env_raw(name: str, env: Mapping[str, str] | None) -> str | None:
    if env is not None and name in env:
        return env[name]
    return os.getenv(name)


def _env_flag(name: str, default: bool, *, env: Mapping[str, str] | None = None) -> bool:
    raw = _env_raw(name, env)
    if raw is None:
        return default

    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ConfigError(f"Environment variable {name} must be a boolean value")


def _env_int(name: str, default: int, *, env: Mapping[str, str] | None = None) -> int:
    raw = _env_raw(name, env)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigError(f"Environment variable {name} must be an integer") from exc
    if value <= 0:
        raise ConfigError(f"Environment variable {name} must be greater than 0")
    return value


def _env_non_negative_int(name: str, default: int, *, env: Mapping[str, str] | None = None) -> int:
    raw = _env_raw(name, env)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigError(f"Environment variable {name} must be an integer") from exc
    if value < 0:
        raise ConfigError(f"Environment variable {name} must be greater than or equal to 0")
    return value


def _env_optional(name: str, env: Mapping[str, str] | None = None) -> str | None:
    value = _env_raw(name, env)
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _require_env(name: str, *, env: Mapping[str, str] | None = None) -> str:
    value = _env_optional(name, env)
    if value is None:
        raise ConfigError(f"Missing required environment variable: {name}")
    return value


def _load_dotenv(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    loaded: dict[str, str] = {}

    for line_number, line in enumerate(path.read_text().splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("export "):
            stripped = stripped[len("export ") :].lstrip()
        if "=" not in stripped:
            raise ConfigError(f"{path}:{line_number}: expected KEY=VALUE")

        key, raw_value = stripped.split("=", maxsplit=1)
        key = key.strip()
        if not ENV_KEY_PATTERN.match(key):
            raise ConfigError(f"{path}:{line_number}: invalid environment variable name '{key}'")

        value = _parse_dotenv_value(raw_value.strip())
        loaded[key] = value
    return loaded


def _parse_dotenv_value(raw_value: str) -> str:
    if not raw_value:
        return ""
    if len(raw_value) >= 2 and raw_value[0] == raw_value[-1] and raw_value[0] in {'"', "'"}:
        return raw_value[1:-1]

    comment_index = _find_unquoted_comment(raw_value)
    value = raw_value[:comment_index] if comment_index is not None else raw_value
    return value.rstrip()


def _find_unquoted_comment(value: str) -> int | None:
    in_single = False
    in_double = False
    previous = ""
    for index, character in enumerate(value):
        if character == "'" and not in_double:
            in_single = not in_single
        elif character == '"' and not in_single:
            in_double = not in_double
        elif character == "#" and not in_single and not in_double and (index == 0 or previous.isspace()):
            return index
        previous = character
    return None


def _discover_primary_worktree_root(root: Path) -> Path | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "worktree", "list", "--porcelain"],
            capture_output=True,
            check=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None

    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            return Path(line.removeprefix("worktree ").strip()).expanduser()
    return None


def _resolve_dotenv_path(root: Path) -> Path | None:
    local_dotenv = root / ".env"
    if local_dotenv.exists():
        return local_dotenv

    primary_root = _discover_primary_worktree_root(root)
    if primary_root is None:
        return None

    primary_dotenv = primary_root / ".env"
    if primary_dotenv.exists():
        return primary_dotenv
    return None


def load_subreddit_config(path: Path, *, env: Mapping[str, str] | None = None) -> SubredditConfig:
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
        lookback_hours=_env_int("LOOKBACK_HOURS", _require_positive_int(fetch, "lookback_hours", path=path), env=env),
        sort_modes=tuple(sort_modes),
        min_post_score=_env_non_negative_int(
            "MIN_POST_SCORE",
            _require_non_negative_int(fetch, "min_post_score", path=path),
            env=env,
        ),
        min_comments=_env_non_negative_int(
            "MIN_COMMENTS",
            _require_non_negative_int(fetch, "min_comments", path=path),
            env=env,
        ),
        max_posts_per_subreddit=_env_int(
            "MAX_POSTS_PER_SUBREDDIT",
            _require_positive_int(fetch, "max_posts_per_subreddit", path=path),
            env=env,
        ),
        max_comments_per_post=_env_int(
            "MAX_COMMENTS_PER_POST",
            _require_positive_int(fetch, "max_comments_per_post", path=path),
            env=env,
        ),
    )

    return SubredditConfig(
        primary=tuple(_require_list(payload, "primary", path=path)),
        secondary=tuple(_optional_list(payload, "secondary", path=path)),
        include_secondary=_env_flag("INCLUDE_SECONDARY_SUBREDDITS", include_secondary, env=env),
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


def load_runtime_config(
    *,
    require_reddit: bool = False,
    require_openai: bool = False,
    require_sheets: bool = False,
    env: Mapping[str, str] | None = None,
) -> RuntimeConfig:
    runtime = RuntimeConfig(
        reddit_client_id=_env_optional("REDDIT_CLIENT_ID", env),
        reddit_client_secret=_env_optional("REDDIT_CLIENT_SECRET", env),
        reddit_user_agent=_env_optional("REDDIT_USER_AGENT", env),
        openai_api_key=_env_optional("OPENAI_API_KEY", env),
        openai_model=_env_optional("OPENAI_MODEL", env) or "gpt-5-mini",
        teams_webhook_url=_env_optional("TEAMS_WEBHOOK_URL", env),
        gcp_workload_identity_provider=_env_optional("GCP_WORKLOAD_IDENTITY_PROVIDER", env),
        gcp_service_account_email=_env_optional("GCP_SERVICE_ACCOUNT_EMAIL", env),
        google_service_account_json=_env_optional("GOOGLE_SERVICE_ACCOUNT_JSON", env),
        google_sheets_spreadsheet_id=_env_optional("GOOGLE_SHEETS_SPREADSHEET_ID", env),
    )

    if require_reddit:
        _require_env("REDDIT_USER_AGENT", env=env)
    if require_openai:
        _require_env("OPENAI_API_KEY", env=env)
    if require_sheets:
        _require_env("GOOGLE_SHEETS_SPREADSHEET_ID", env=env)

    return runtime


def load_config(
    base_path: Path | None = None,
    *,
    require_reddit: bool = False,
    require_openai: bool = False,
    require_sheets: bool = False,
) -> AppConfig:
    root = base_path or Path.cwd()
    dotenv_path = _resolve_dotenv_path(root)
    env = {**(_load_dotenv(dotenv_path) if dotenv_path is not None else {}), **os.environ}
    config_dir = root / "config"
    return AppConfig(
        subreddits=load_subreddit_config(config_dir / "subreddits.yaml", env=env),
        scoring=load_scoring_config(config_dir / "scoring.yaml"),
        runtime=load_runtime_config(
            require_reddit=require_reddit,
            require_openai=require_openai,
            require_sheets=require_sheets,
            env=env,
        ),
    )
