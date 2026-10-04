"""Shared fixtures."""

from typing import TYPE_CHECKING

import pytest

from mindstew.vault import create_vault

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


@pytest.fixture
def make_vault(tmp_path: Path) -> Callable[..., Path]:
    """Return a builder that creates a fresh vault under the test's temp dir and returns its root."""

    def _make(name: str = "vault") -> Path:
        root = tmp_path / name
        create_vault(root)
        return root

    return _make
