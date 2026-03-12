"""Guide and resource extraction rules."""

from __future__ import annotations

import re

from reddit_digest.extractors.common import InsightPattern


GUIDE_PATTERNS: tuple[InsightPattern, ...] = (
    InsightPattern(
        title="Local context file pattern",
        category="guides",
        summary="A reusable context-file pattern is being shared as a repeatable resource.",
        why_it_matters="It gives other practitioners a concrete way to structure agent context.",
        tags=("prompting", "coding-agents", "tooling"),
        regex=re.compile(r"context file"),
    ),
    InsightPattern(
        title="Prompt recovery checklist",
        category="guides",
        summary="People are sharing explicit recovery steps for resuming interrupted agent work.",
        why_it_matters="Recovery patterns make longer-running AI workflows more reliable.",
        tags=("reliability", "prompting", "ai-dev-workflow"),
        regex=re.compile(r"prompt recovery|recovery"),
    ),
)
