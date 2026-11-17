import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


class FakeHttp:
    """Returns a saved payload for every request and remembers the query parameters."""

    def __init__(self, payload):
        self.payload, self.calls = payload, []

    def get_json(self, url, **params):
        self.calls.append((url, params))
        return self.payload


@pytest.fixture
def fixture_json():
    return lambda name: json.loads((FIXTURES / name).read_text(encoding="utf-8"))
