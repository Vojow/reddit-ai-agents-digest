"""Declarative extraction rule registry."""

from __future__ import annotations

from dataclasses import dataclass
import re

from reddit_digest.extractors.common import InsightPattern


@dataclass(frozen=True)
class RuleSet:
    name: str
    patterns: tuple[InsightPattern, ...]


def _build_patterns(definitions: tuple[dict[str, object], ...]) -> tuple[InsightPattern, ...]:
    patterns: list[InsightPattern] = []
    for definition in definitions:
        patterns.append(
            InsightPattern(
                title=str(definition["title"]),
                category=str(definition["category"]),
                summary=str(definition["summary"]),
                why_it_matters=str(definition["why_it_matters"]),
                tags=tuple(str(tag) for tag in definition["tags"]),
                regex=re.compile(str(definition["regex"])),
            )
        )
    return tuple(patterns)


_RULE_DEFINITIONS: tuple[tuple[str, tuple[dict[str, object], ...]], ...] = (
    (
        "tools",
        (
            {
                "title": "Codex",
                "category": "tools",
                "summary": "Codex is being used as an agentic coding tool in real workflows.",
                "why_it_matters": "It appears in hands-on discussions about practical agent-assisted coding.",
                "tags": ("ai-agents", "tooling", "coding-agents"),
                "regex": r"\bcodex\b",
            },
            {
                "title": "Claude Code",
                "category": "tools",
                "summary": "Claude Code is being used to support structured software workflows.",
                "why_it_matters": "It is discussed as an applied coding tool rather than generic AI chat.",
                "tags": ("ai-agents", "tooling", "ai-dev-workflow"),
                "regex": r"\bclaude code\b",
            },
        ),
    ),
    (
        "approaches",
        (
            {
                "title": "Test-first refactors",
                "category": "approaches",
                "summary": "Authors are using tests or fixtures before asking agents to change production code.",
                "why_it_matters": "This makes AI-assisted changes safer and easier to verify.",
                "tags": ("ai-dev-workflow", "ai-testing", "reliability"),
                "regex": r"test-first|fixtures before|before asking the model",
            },
            {
                "title": "Context snapshots",
                "category": "approaches",
                "summary": "Teams are capturing local context snapshots before each AI-assisted change.",
                "why_it_matters": "Stable context helps with recovery and reduces drift across iterations.",
                "tags": ("ai-dev-workflow", "coding-agents", "prompting"),
                "regex": r"context file|snapshot the repo state|context snapshots?",
            },
        ),
    ),
    (
        "guides",
        (
            {
                "title": "Local context file pattern",
                "category": "guides",
                "summary": "A reusable context-file pattern is being shared as a repeatable resource.",
                "why_it_matters": "It gives other practitioners a concrete way to structure agent context.",
                "tags": ("prompting", "coding-agents", "tooling"),
                "regex": r"context file",
            },
            {
                "title": "Prompt recovery checklist",
                "category": "guides",
                "summary": "People are sharing explicit recovery steps for resuming interrupted agent work.",
                "why_it_matters": "Recovery patterns make longer-running AI workflows more reliable.",
                "tags": ("reliability", "prompting", "ai-dev-workflow"),
                "regex": r"prompt recovery|recovery",
            },
        ),
    ),
    (
        "testing",
        (
            {
                "title": "Snapshot markdown tests",
                "category": "testing",
                "summary": "Snapshot-style output tests are being used to catch formatting regressions.",
                "why_it_matters": "Deterministic report generation becomes testable and safer to change.",
                "tags": ("ai-testing", "reliability", "tooling"),
                "regex": r"snapshot.*tests?|markdown output tests",
            },
            {
                "title": "Deterministic prompting",
                "category": "testing",
                "summary": "Prompt stability is being treated as a software quality concern.",
                "why_it_matters": "Repeatable prompting improves trust in AI-assisted development workflows.",
                "tags": ("prompting", "reliability", "ai-testing"),
                "regex": r"deterministic",
            },
        ),
    ),
)

RULESETS: tuple[RuleSet, ...] = tuple(
    RuleSet(name=name, patterns=_build_patterns(definitions))
    for name, definitions in _RULE_DEFINITIONS
)


def patterns_for_ruleset(name: str) -> tuple[InsightPattern, ...]:
    for ruleset in RULESETS:
        if ruleset.name == name:
            return ruleset.patterns
    raise KeyError(name)
