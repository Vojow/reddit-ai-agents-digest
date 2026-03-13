"""Shared transport and artifact helpers for Reddit collection."""

from __future__ import annotations

from pathlib import Path
import json
from typing import Any

import requests

from reddit_digest.config import RuntimeConfig


def write_json_artifact(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True))
    return path


class PublicRedditTransport:
    """Shared HTTP policy for public Reddit JSON collection."""

    def __init__(
        self,
        runtime: RuntimeConfig,
        *,
        session: requests.Session | None = None,
        base_url: str = "https://www.reddit.com",
    ) -> None:
        self._session = session or requests.Session()
        self._base_url = base_url.rstrip("/")
        self._session.headers.update(
            {
                "User-Agent": runtime.reddit_user_agent or "reddit-ai-agents-digest/0.1.0",
                "Accept": "application/json",
            }
        )

    def get_json(self, path: str, *, params: dict[str, Any], timeout: int = 20) -> Any:
        response = self._session.get(f"{self._base_url}/{path.lstrip('/')}", params=params, timeout=timeout)
        response.raise_for_status()
        return response.json()
