"""Shared fixtures."""

from typing import TYPE_CHECKING

import keyring
import pytest
from keyring.backend import KeyringBackend
from keyring.errors import PasswordDeleteError

from mindstew.vault import create_vault

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from pathlib import Path


@pytest.fixture(autouse=True)
def mindstew_home(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the machine-global registry at a temp dir so tests never touch real Application Support."""
    home = tmp_path_factory.mktemp("mindstew-home")
    monkeypatch.setenv("MINDSTEW_HOME", str(home))
    return home


@pytest.fixture(autouse=True)
def fake_keyring() -> Iterator[dict[tuple[str, str], str]]:
    """Swap in an in-memory keyring so tests never touch the real Keychain; yields its backing dict."""
    store: dict[tuple[str, str], str] = {}

    class Fake(KeyringBackend):
        priority = 1

        def get_password(self, service: str, username: str) -> str | None:
            return store.get((service, username))

        def set_password(self, service: str, username: str, password: str) -> None:
            store[service, username] = password

        def delete_password(self, service: str, username: str) -> None:
            if (service, username) not in store:
                raise PasswordDeleteError(username)
            del store[service, username]

    previous = keyring.get_keyring()
    keyring.set_keyring(Fake())
    yield store
    keyring.set_keyring(previous)


@pytest.fixture(autouse=True)
def no_retry_delay(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the worker's outage backoff instant unless a test sets its own."""
    monkeypatch.setattr("mindstew.worker.RETRY_DELAY", 0)


class FakeAdapter:
    """Deterministic stand-in for ``mindstew.adapter``: canned responses in order, and a call log."""

    def __init__(self) -> None:
        self.calls: list[tuple] = []  # (route, messages, output_type) per complete() call
        self.pings: list = []  # routes passed to ping()
        self._queue: list = []

    def respond(self, *responses: object) -> None:
        """Queue responses for upcoming ``complete`` calls; an Exception instance is raised instead of returned."""
        self._queue.extend(responses)

    def complete(self, route: object, messages: list, output_type: type) -> object:
        """Log the call and return (or raise) the next canned response."""
        self.calls.append((route, messages, output_type))
        assert self._queue, "FakeAdapter: no canned response left; call fake_adapter.respond(...)"
        response = self._queue.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    def ping(self, route: object) -> None:
        """Log the ping; always succeeds."""
        self.pings.append(route)


@pytest.fixture
def fake_adapter(monkeypatch: pytest.MonkeyPatch) -> FakeAdapter:
    """Replace ``mindstew.adapter.complete``/``ping`` so no test reaches a provider.

    Code under test must call them as ``adapter.complete(...)`` (module attribute), not import the names.
    """
    fake = FakeAdapter()
    monkeypatch.setattr("mindstew.adapter.complete", fake.complete)
    monkeypatch.setattr("mindstew.adapter.ping", fake.ping)
    return fake


@pytest.fixture
def make_vault(tmp_path: Path) -> Callable[..., Path]:
    """Return a builder that creates a fresh vault under the test's temp dir and returns its root."""

    def _make(name: str = "vault") -> Path:
        root = tmp_path / name
        create_vault(root)
        return root

    return _make
