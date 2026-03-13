"""Typed OpenAI usage models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OpenAIOperationUsage:
    operation: str
    calls: int
    input_tokens: int
    output_tokens: int
    total_tokens: int


@dataclass(frozen=True)
class OpenAIUsageSummary:
    total_calls: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    operations: tuple[OpenAIOperationUsage, ...]

    @classmethod
    def empty(cls) -> "OpenAIUsageSummary":
        return cls(
            total_calls=0,
            input_tokens=0,
            output_tokens=0,
            total_tokens=0,
            operations=(),
        )
