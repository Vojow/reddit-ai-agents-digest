"""Workflow and approach extraction rules."""

from __future__ import annotations

import re

from reddit_digest.extractors.common import InsightPattern


APPROACH_PATTERNS: tuple[InsightPattern, ...] = (
    InsightPattern(
        title="Test-first refactors",
        category="approaches",
        summary="Authors are using tests or fixtures before asking agents to change production code.",
        why_it_matters="This makes AI-assisted changes safer and easier to verify.",
        tags=("ai-dev-workflow", "ai-testing", "reliability"),
        regex=re.compile(r"test-first|fixtures before|before asking the model"),
    ),
    InsightPattern(
        title="Context snapshots",
        category="approaches",
        summary="Teams are capturing local context snapshots before each AI-assisted change.",
        why_it_matters="Stable context helps with recovery and reduces drift across iterations.",
        tags=("ai-dev-workflow", "coding-agents", "prompting"),
        regex=re.compile(r"context file|snapshot the repo state|context snapshots?"),
    ),
)
