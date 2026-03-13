from __future__ import annotations

import pytest

from reddit_digest.extractors.registry import patterns_for_ruleset


def test_registry_rejects_unknown_ruleset() -> None:
    with pytest.raises(KeyError, match="unknown"):
        patterns_for_ruleset("unknown")
