"""Testing and quality extraction rules."""

from __future__ import annotations

import re

from reddit_digest.extractors.common import InsightPattern


TESTING_PATTERNS: tuple[InsightPattern, ...] = (
    InsightPattern(
        title="Snapshot markdown tests",
        category="testing",
        summary="Snapshot-style output tests are being used to catch formatting regressions.",
        why_it_matters="Deterministic report generation becomes testable and safer to change.",
        tags=("ai-testing", "reliability", "tooling"),
        regex=re.compile(r"snapshot.*tests?|markdown output tests"),
    ),
    InsightPattern(
        title="Deterministic prompting",
        category="testing",
        summary="Prompt stability is being treated as a software quality concern.",
        why_it_matters="Repeatable prompting improves trust in AI-assisted development workflows.",
        tags=("prompting", "reliability", "ai-testing"),
        regex=re.compile(r"deterministic"),
    ),
)
