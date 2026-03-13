"""Tracked OpenAI client wrapper."""

from __future__ import annotations

from collections.abc import MutableMapping
from dataclasses import dataclass
from typing import Any
from typing import Protocol

from openai import OpenAI

from reddit_digest.config import RuntimeConfig
from reddit_digest.models.openai_usage import OpenAIOperationUsage
from reddit_digest.models.openai_usage import OpenAIUsageSummary


class ResponsesClient(Protocol):
    def create(self, **kwargs: Any) -> Any:
        ...


class SDKClient(Protocol):
    responses: ResponsesClient


class OpenAITextClient(Protocol):
    def create_text(self, *, operation: str, model: str, input: str) -> str:
        ...

    def usage_summary(self) -> OpenAIUsageSummary:
        ...


@dataclass
class _UsageAccumulator:
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


class TrackedOpenAIClient(OpenAITextClient):
    def __init__(self, client: SDKClient) -> None:
        self._client = client
        self._usage_by_operation: MutableMapping[str, _UsageAccumulator] = {}

    def create_text(self, *, operation: str, model: str, input: str) -> str:
        response = self._client.responses.create(
            model=model,
            input=input,
        )
        self._record_usage(operation, response)
        return response.output_text

    def usage_summary(self) -> OpenAIUsageSummary:
        operations = tuple(
            OpenAIOperationUsage(
                operation=operation,
                calls=usage.calls,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                total_tokens=usage.total_tokens,
            )
            for operation, usage in sorted(self._usage_by_operation.items())
        )
        return OpenAIUsageSummary(
            total_calls=sum(item.calls for item in operations),
            input_tokens=sum(item.input_tokens for item in operations),
            output_tokens=sum(item.output_tokens for item in operations),
            total_tokens=sum(item.total_tokens for item in operations),
            operations=operations,
        )

    def _record_usage(self, operation: str, response: Any) -> None:
        usage = _extract_usage(response)
        accumulator = self._usage_by_operation.setdefault(operation, _UsageAccumulator())
        accumulator.calls += 1
        accumulator.input_tokens += usage["input_tokens"]
        accumulator.output_tokens += usage["output_tokens"]
        accumulator.total_tokens += usage["total_tokens"]


def build_openai_client(runtime: RuntimeConfig) -> OpenAITextClient:
    return TrackedOpenAIClient(OpenAI(api_key=runtime.openai_api_key))


def _extract_usage(response: Any) -> dict[str, int]:
    usage = getattr(response, "usage", None)
    if usage is None and isinstance(response, dict):
        usage = response.get("usage")

    return {
        "input_tokens": _coerce_usage_int(usage, "input_tokens"),
        "output_tokens": _coerce_usage_int(usage, "output_tokens"),
        "total_tokens": _coerce_usage_int(usage, "total_tokens"),
    }


def _coerce_usage_int(usage: Any, field_name: str) -> int:
    if usage is None:
        return 0
    if isinstance(usage, dict):
        value = usage.get(field_name, 0)
    else:
        value = getattr(usage, field_name, 0)
    if value in (None, ""):
        return 0
    return int(value)
