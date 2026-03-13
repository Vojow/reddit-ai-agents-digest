from __future__ import annotations

from datetime import UTC
from datetime import datetime
import logging

import httpx
from openai import APIStatusError
from openai import RateLimitError
import pytest

from reddit_digest.models.openai_usage import OpenAIOperationUsage
from reddit_digest.models.openai_usage import OpenAIUsageSummary
from reddit_digest.pipeline import _build_openai_warning
from reddit_digest.pipeline import _is_openai_quota_error
from reddit_digest.pipeline import _log_openai_usage_summary


def test_pipeline_openai_warning_helpers_cover_main_branches(caplog: pytest.LogCaptureFixture) -> None:
    response = httpx.Response(429, request=httpx.Request("POST", "https://api.openai.com/v1/responses"))
    quota_error = APIStatusError(
        "quota",
        response=response,
        body={"error": {"code": "insufficient_quota"}},
    )
    rate_limit_error = RateLimitError("rate limited", response=response, body=None)

    assert _is_openai_quota_error(quota_error) is True
    assert _is_openai_quota_error(Exception("insufficient_quota")) is True
    assert _build_openai_warning(quota_error, skipped_steps="rewrites") == (
        "OPENAI QUOTA EXHAUSTED: rewrites were skipped. "
        "The deterministic markdown below was generated successfully without OpenAI enhancements."
    )
    assert _build_openai_warning(rate_limit_error, skipped_steps="rewrites") == (
        "OPENAI RATE LIMITED: rewrites were skipped. "
        "The deterministic markdown below was generated successfully without OpenAI enhancements."
    )
    assert _build_openai_warning(RuntimeError("boom"), skipped_steps="rewrites") is None

    usage = OpenAIUsageSummary(
        total_calls=3,
        input_tokens=12,
        output_tokens=8,
        total_tokens=20,
        operations=(
            OpenAIOperationUsage(
                operation="topic_rewrites",
                calls=1,
                input_tokens=5,
                output_tokens=3,
                total_tokens=8,
            ),
        ),
    )
    with caplog.at_level(logging.INFO):
        _log_openai_usage_summary(usage)
    assert "OpenAI usage totals: calls=3 input_tokens=12 output_tokens=8 total_tokens=20" in caplog.text
    assert "OpenAI usage for topic_rewrites: calls=1 input_tokens=5 output_tokens=3 total_tokens=8" in caplog.text
