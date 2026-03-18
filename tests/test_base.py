from __future__ import annotations

from dataclasses import dataclass

import pytest

from reddit_digest.models.base import BaseModel
from reddit_digest.models.base import ModelError
from reddit_digest.models.base import optional_string
from reddit_digest.models.base import require_int
from reddit_digest.models.base import require_non_negative_int
from reddit_digest.models.base import require_string
from reddit_digest.models.base import require_string_list


def test_model_base_helpers_validate_and_serialize() -> None:
    @dataclass(frozen=True)
    class ExampleModel(BaseModel):
        value: str

    assert require_string({"name": "  Codex  "}, "name") == "Codex"
    assert optional_string({"name": "  "}, "name") is None
    assert require_int({"count": 3}, "count") == 3
    assert require_non_negative_int({"count": 0}, "count") == 0
    assert require_string_list({"tags": [" one ", "two"]}, "tags") == ("one", "two")
    assert ExampleModel("ok").to_dict() == {"value": "ok"}

    with pytest.raises(ModelError, match="must be a non-empty string"):
        require_string({"name": ""}, "name")
    with pytest.raises(ModelError, match="must be greater than or equal to 0"):
        require_non_negative_int({"count": -1}, "count")
