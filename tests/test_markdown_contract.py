from __future__ import annotations


EXPECTED_SECTIONS = [
    "## Executive Summary",
    "## Top Tools Mentioned",
    "## Top Approaches / Workflows",
    "## Top Guides / Resources",
    "## Testing and Quality Insights",
    "## Notable Threads",
    "## Top Threads By Subreddit",
    "## Emerging Themes",
]


def test_sample_digest_contains_expected_sections(sample_digest_markdown: str) -> None:
    for section in EXPECTED_SECTIONS:
        assert section in sample_digest_markdown


def test_sample_digest_section_order(sample_digest_markdown: str) -> None:
    positions = [sample_digest_markdown.index(section) for section in EXPECTED_SECTIONS]
    assert positions == sorted(positions)


def test_watch_next_section_follows_emerging_themes_when_present(sample_digest_markdown: str) -> None:
    if "## Watch Next" not in sample_digest_markdown:
        return

    assert sample_digest_markdown.index("## Emerging Themes") < sample_digest_markdown.index("## Watch Next")
