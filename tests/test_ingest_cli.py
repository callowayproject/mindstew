"""The ``ingest`` command, end to end through the CLI with the fake adapter."""

from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner, Result

from mindstew.cli import cli
from mindstew.ingest import Analysis, GeneratedPage, GeneratedPages
from mindstew.ingest_queue import enqueue, list_items, next_item
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


def _ok(fake: FakeAdapter, title: str = "Alice", body: str = "Hi.") -> None:
    fake.respond(
        Analysis(summary="s"),
        GeneratedPages(pages=[GeneratedPage(type="entity", title=title, body=body)]),
    )


def _run(*args: object) -> Result:
    return CliRunner().invoke(cli, ["ingest", *map(str, args)])


def test_single_file_outside_sources_is_copied_and_ingested(
    vault: Path, tmp_path: Path, fake_adapter: FakeAdapter
) -> None:
    """A file elsewhere is copied into sources/ and ingested, with progress printed."""
    src = tmp_path / "note.md"
    src.write_text("Alice.", encoding="utf-8")
    _ok(fake_adapter)
    result = _run(vault, src)
    assert result.exit_code == 0, result.output
    assert (vault / "sources" / "note.md").read_text(encoding="utf-8") == "Alice."
    assert [p.title for p in list_pages(vault)] == ["Alice"]
    assert "note.md" in result.output
    assert [i.status for i in list_items(vault)] == ["done"]


def test_copy_does_not_overwrite(vault: Path, tmp_path: Path, fake_adapter: FakeAdapter) -> None:
    """An existing different file in sources/ is kept and the clash is reported."""
    (vault / "sources" / "note.md").write_text("original", encoding="utf-8")
    src = tmp_path / "note.md"
    src.write_text("other", encoding="utf-8")
    result = _run(vault, src)
    assert (vault / "sources" / "note.md").read_text(encoding="utf-8") == "original"
    assert "exists" in result.output
    assert list_items(vault) == []


def test_folder_is_recursive_skips_hidden_and_unsupported(
    vault: Path, tmp_path: Path, fake_adapter: FakeAdapter
) -> None:
    """Folder import takes .md/.txt recursively; hidden and unsupported files are skipped, unsupported reported."""
    d = tmp_path / "in"
    (d / "sub").mkdir(parents=True)
    (d / ".hidden").mkdir()
    (d / "a.md").write_text("a", encoding="utf-8")
    (d / "sub" / "b.txt").write_text("b", encoding="utf-8")
    (d / "pic.png").write_bytes(b"x")
    (d / ".secret.md").write_text("s", encoding="utf-8")
    (d / ".hidden" / "c.md").write_text("c", encoding="utf-8")
    _ok(fake_adapter, "A")
    _ok(fake_adapter, "B")
    result = _run(vault, d)
    assert result.exit_code == 0, result.output
    assert sorted(i.path.name for i in list_items(vault)) == ["a.md", "b.txt"]
    assert (vault / "sources" / "sub" / "b.txt").is_file()
    assert "unsupported" in result.output
    assert "pic.png" in result.output
    assert "secret" not in result.output


def test_bare_vault_ingests_sources(vault: Path, fake_adapter: FakeAdapter) -> None:
    """With no path, files already under sources/ are enqueued."""
    (vault / "sources" / "x.md").write_text("x", encoding="utf-8")
    _ok(fake_adapter)
    result = _run(vault)
    assert result.exit_code == 0, result.output
    assert [i.status for i in list_items(vault)] == ["done"]


def test_failed_item_exits_nonzero(vault: Path, fake_adapter: FakeAdapter) -> None:
    """An item that exhausts its retries makes the command exit non-zero."""
    (vault / "sources" / "x.md").write_text("x", encoding="utf-8")
    fake_adapter.respond(*[RuntimeError("boom")] * 3)
    result = _run(vault)
    assert result.exit_code != 0
    assert "boom" in result.output
    assert [i.status for i in list_items(vault)] == ["failed"]


def test_relaunch_recovers_running_item(vault: Path, fake_adapter: FakeAdapter) -> None:
    """An item left running by a killed session is recovered and finished by the next invocation."""
    src = vault / "sources" / "x.md"
    src.write_text("x", encoding="utf-8")
    enqueue(vault, src)
    assert next_item(vault)  # now 'running', as if the process died mid-item
    _ok(fake_adapter)
    result = _run(vault)
    assert result.exit_code == 0, result.output
    assert [i.status for i in list_items(vault)] == ["done"]


def test_reingest_bypasses_hash_and_overwrites_named_page(vault: Path, fake_adapter: FakeAdapter) -> None:
    """--reingest regenerates the page in place even though the source is unchanged."""
    (vault / "sources" / "x.md").write_text("x", encoding="utf-8")
    _ok(fake_adapter, "Alice", "v1")
    assert _run(vault).exit_code == 0
    _ok(fake_adapter, "Alice", "v2")
    result = CliRunner().invoke(cli, ["ingest", str(vault), "--reingest", "entities/alice.md"])
    assert result.exit_code == 0, result.output
    pages = list_pages(vault)
    assert [p.path.name for p in pages] == ["alice.md"]
    assert pages[0].body.strip() == "v2"


def test_reingest_unknown_page_errors(vault: Path) -> None:
    """A page that does not exist is a usage error."""
    result = CliRunner().invoke(cli, ["ingest", str(vault), "--reingest", "entities/nope.md"])
    assert result.exit_code != 0
    assert "no such page" in result.output
