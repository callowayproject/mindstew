"""``ingest_path``: stage, enqueue and drain without Click, reporting through a callback."""

from typing import TYPE_CHECKING

import pytest

from mindstew.ingest import Analysis, GeneratedPage, GeneratedPages, ingest_path
from mindstew.pages import list_pages
from mindstew.providers import Provider, add_provider, set_route

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from tests.conftest import FakeAdapter


@pytest.fixture
def vault(make_vault: Callable[..., Path]) -> Path:
    """A vault with an ingest route."""
    root = make_vault()
    add_provider(Provider("p", "P", "openai", "http://x"))
    set_route("ingest", "p", "m")
    return root


def test_ingest_path_stages_ingests_and_reports(vault: Path, tmp_path: Path, fake_adapter: FakeAdapter) -> None:
    """A file outside the vault is copied in, ingested, and progress goes to ``emit``."""
    src = tmp_path / "in"
    src.mkdir()
    (src / "note.md").write_text("Alice.", encoding="utf-8")
    fake_adapter.respond(
        Analysis(summary="s"), GeneratedPages(pages=[GeneratedPage(type="entity", title="Alice", body="Hi.")])
    )
    lines: list[str] = []
    failed = ingest_path(vault, src, emit=lines.append)
    assert failed == 0
    assert [p.title for p in list_pages(vault)] == ["Alice"]
    assert "finished: note.md" in lines


def test_ingest_path_with_nothing_to_do(vault: Path) -> None:
    """An empty sources/ reports and returns zero failures."""
    lines: list[str] = []
    assert ingest_path(vault, emit=lines.append) == 0
    assert lines == ["nothing to ingest"]
