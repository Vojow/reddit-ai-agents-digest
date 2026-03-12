"""Shared model helpers."""

from __future__ import annotations

from dataclasses import asdict
from dataclasses import dataclass
from typing import Any


class ModelError(ValueError):
    """Raised when raw data cannot be normalized into a typed model."""


@dataclass(frozen=True)
class BaseModel:
    """Base class for typed models with simple serialization support."""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def require_string(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ModelError(f"'{key}' must be a non-empty string")
    return value.strip()


def optional_string(payload: dict[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ModelError(f"'{key}' must be a string when provided")
    stripped = value.strip()
    return stripped or None


def require_int(payload: dict[str, Any], key: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int):
        raise ModelError(f"'{key}' must be an integer")
    return value


def require_non_negative_int(payload: dict[str, Any], key: str) -> int:
    value = require_int(payload, key)
    if value < 0:
        raise ModelError(f"'{key}' must be greater than or equal to 0")
    return value


def require_string_list(payload: dict[str, Any], key: str) -> tuple[str, ...]:
    value = payload.get(key)
    if not isinstance(value, list) or not value:
        raise ModelError(f"'{key}' must be a non-empty list")
    items: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ModelError(f"'{key}' entries must be non-empty strings")
        items.append(item.strip())
    return tuple(items)
