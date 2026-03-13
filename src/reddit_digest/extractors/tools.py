"""Tool extraction rules."""

from __future__ import annotations

from reddit_digest.extractors.common import InsightPattern
from reddit_digest.extractors.registry import patterns_for_ruleset


TOOL_PATTERNS: tuple[InsightPattern, ...] = patterns_for_ruleset("tools")
