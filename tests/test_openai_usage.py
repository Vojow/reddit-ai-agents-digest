from __future__ import annotations

from reddit_digest.models.openai_usage import OpenAIUsageSummary


def test_openai_usage_summary_empty_returns_zeroed_summary() -> None:
    assert OpenAIUsageSummary.empty() == OpenAIUsageSummary(
        total_calls=0,
        input_tokens=0,
        output_tokens=0,
        total_tokens=0,
        operations=(),
    )
