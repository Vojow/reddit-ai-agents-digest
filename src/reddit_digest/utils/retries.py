"""Retry helpers for transient operations."""

from __future__ import annotations

from collections.abc import Callable
import logging
import time
from typing import TypeVar


T = TypeVar("T")


def retry_call(
    func: Callable[[], T],
    *,
    operation: str,
    logger: logging.Logger,
    attempts: int = 3,
    delay_seconds: float = 0.25,
) -> T:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return func()
        except Exception as exc:
            last_error = exc
            logger.warning("%s failed on attempt %s/%s: %s", operation, attempt, attempts, exc)
            if attempt == attempts:
                break
            time.sleep(delay_seconds)
    assert last_error is not None
    raise last_error
