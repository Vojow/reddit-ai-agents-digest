"""Bootstrap preflight checks for local and automated runs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os

from reddit_digest.config import ConfigError
from reddit_digest.config import load_config


@dataclass(frozen=True)
class PreflightResult:
    ok: bool
    errors: tuple[str, ...]
    warnings: tuple[str, ...] = ()


def run_preflight(*, base_path: Path, skip_sheets: bool = False, markdown_only: bool = False) -> PreflightResult:
    del markdown_only

    errors: list[str] = []
    root = base_path

    if not root.exists():
        return PreflightResult(ok=False, errors=(f"Base path does not exist: {root}",))
    if not root.is_dir():
        return PreflightResult(ok=False, errors=(f"Base path is not a directory: {root}",))

    for relative_path in ("pyproject.toml", "config/subreddits.yaml", "config/scoring.yaml"):
        required_path = root / relative_path
        if not required_path.exists():
            errors.append(f"Required path is missing: {required_path}")

    if not errors:
        try:
            load_config(
                root,
                require_reddit=True,
                require_sheets=not skip_sheets,
            )
        except ConfigError as exc:
            errors.append(str(exc))

    for relative_path in ("reports", "data/raw", "data/processed", "data/state"):
        message = _check_write_target(root / relative_path)
        if message is not None:
            errors.append(message)

    return PreflightResult(ok=not errors, errors=tuple(errors))


def format_preflight_result(result: PreflightResult) -> str:
    lines = ["Preflight passed." if result.ok else "Preflight failed."]
    lines.extend(f"- {item}" for item in result.errors)
    lines.extend(f"- Warning: {item}" for item in result.warnings)
    return "\n".join(lines) + "\n"


def _check_write_target(target_path: Path) -> str | None:
    existing_ancestor = _nearest_existing_ancestor(target_path)
    if existing_ancestor is None:
        return f"Could not resolve an existing ancestor for: {target_path}"
    if not existing_ancestor.is_dir():
        return f"Existing ancestor is not a directory: {existing_ancestor}"
    if not os.access(existing_ancestor, os.W_OK | os.X_OK):
        return f"Write access is not available for: {existing_ancestor}"
    if target_path.exists() and not target_path.is_dir():
        return f"Expected a directory path but found a file: {target_path}"
    return None


def _nearest_existing_ancestor(path: Path) -> Path | None:
    current = path
    while True:
        if current.exists():
            return current
        if current.parent == current:
            return None
        current = current.parent
