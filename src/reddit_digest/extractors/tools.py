"""Tool extraction rules."""

from __future__ import annotations

import re

from reddit_digest.extractors.common import InsightPattern


TOOL_PATTERNS: tuple[InsightPattern, ...] = (
    InsightPattern(
        title="Codex",
        category="tools",
        summary="Codex is being used as an agentic coding tool in real workflows.",
        why_it_matters="It appears in hands-on discussions about practical agent-assisted coding.",
        tags=("ai-agents", "tooling", "coding-agents"),
        regex=re.compile(r"\bcodex\b"),
    ),
    InsightPattern(
        title="Claude Code",
        category="tools",
        summary="Claude Code is being used to support structured software workflows.",
        why_it_matters="It is discussed as an applied coding tool rather than generic AI chat.",
        tags=("ai-agents", "tooling", "ai-dev-workflow"),
        regex=re.compile(r"\bclaude code\b"),
    ),
)
