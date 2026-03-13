from __future__ import annotations

from types import SimpleNamespace

from reddit_digest.openai_client import TrackedOpenAIClient


class FakeResponsesClient:
    def __init__(self, responses: list[object]) -> None:
        self._responses = list(responses)

    def create(self, **_kwargs):
        return self._responses.pop(0)


class FakeSDKClient:
    def __init__(self, responses: list[object]) -> None:
        self.responses = FakeResponsesClient(responses)


def test_tracked_openai_client_aggregates_usage_by_operation() -> None:
    client = TrackedOpenAIClient(
        FakeSDKClient(
            [
                SimpleNamespace(output_text='{"ok": true}', usage=SimpleNamespace(input_tokens=11, output_tokens=7, total_tokens=18)),
                SimpleNamespace(output_text='{"ok": true}', usage={"input_tokens": 5, "output_tokens": 3, "total_tokens": 8}),
                SimpleNamespace(output_text='{"ok": true}', usage=SimpleNamespace(input_tokens=4, output_tokens=2, total_tokens=6)),
            ]
        )
    )

    client.create_text(operation="generate_openai_suggestions", model="gpt-5-mini", input="one")
    client.create_text(operation="generate_openai_suggestions", model="gpt-5-mini", input="two")
    client.create_text(operation="rewrite_openai_topics", model="gpt-5-mini", input="three")

    usage = client.usage_summary()

    assert usage.total_calls == 3
    assert usage.input_tokens == 20
    assert usage.output_tokens == 12
    assert usage.total_tokens == 32
    assert usage.operations[0].operation == "generate_openai_suggestions"
    assert usage.operations[0].calls == 2
    assert usage.operations[0].total_tokens == 26
    assert usage.operations[1].operation == "rewrite_openai_topics"
    assert usage.operations[1].calls == 1
    assert usage.operations[1].total_tokens == 6


def test_tracked_openai_client_treats_missing_usage_as_zero() -> None:
    client = TrackedOpenAIClient(FakeSDKClient([SimpleNamespace(output_text='{"ok": true}', usage=None)]))

    client.create_text(operation="generate_openai_suggestions", model="gpt-5-mini", input="one")
    usage = client.usage_summary()

    assert usage.total_calls == 1
    assert usage.input_tokens == 0
    assert usage.output_tokens == 0
    assert usage.total_tokens == 0
