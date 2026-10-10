"""Opt-in smoke test against a real OpenAI-compatible provider; see docs/agents/testing.md."""

import os
from typing import TYPE_CHECKING

import pytest
from pydantic import BaseModel

from mindstew import adapter
from mindstew.providers import Provider, Route

if TYPE_CHECKING:
    from collections.abc import MutableMapping

BASE_URL = os.environ.get("MINDSTEW_LIVE_BASE_URL")
MODEL = os.environ.get("MINDSTEW_LIVE_MODEL")

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(not (BASE_URL and MODEL), reason="set MINDSTEW_LIVE_BASE_URL and MINDSTEW_LIVE_MODEL"),
]


class Answer(BaseModel):
    """Smallest structured reply, enough to prove json_schema output round-trips."""

    word: str


@pytest.fixture
def route(fake_keyring: MutableMapping[tuple[str, str], str]) -> Route:
    """A route to the live endpoint; the key goes to the in-memory keyring, never the real Keychain."""
    if key := os.environ.get("MINDSTEW_LIVE_API_KEY"):
        fake_keyring["mindstew", "live/api_key"] = key
    provider = Provider(id="live", name="live", kind="openai-compatible", base_url=BASE_URL or "")
    return Route(role="ingest", provider=provider, model=MODEL or "")


def test_ping(route: Route) -> None:
    """The endpoint is reachable and accepts the credentials."""
    adapter.ping(route)


def test_structured_output(route: Route) -> None:
    """The provider accepts the strict json_schema request and returns a valid ``Answer``."""
    answer = adapter.complete(route, [{"role": "user", "content": "Reply with one word."}], Answer)
    assert answer.word
