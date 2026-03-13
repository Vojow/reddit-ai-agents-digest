"""Testing and quality extraction rules."""

from __future__ import annotations

from reddit_digest.extractors.common import InsightPattern
from reddit_digest.extractors.registry import patterns_for_ruleset


TESTING_PATTERNS: tuple[InsightPattern, ...] = patterns_for_ruleset("testing")
