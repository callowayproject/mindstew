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


@pytest.fixture
def make_vault(tmp_path: Path) -> Callable[..., Path]:
    """Return a builder that creates a fresh vault under the test's temp dir and returns its root."""

    def _make(name: str = "vault") -> Path:
        root = tmp_path / name
        create_vault(root)
        return root

    return _make
