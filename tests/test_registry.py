"""Tests for the machine-global project registry and `mindstew ls` without a path."""

import json
from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner

from mindstew.cli import cli
from mindstew.registry import registry_path

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


def _ls() -> str:
    result = CliRunner().invoke(cli, ["ls"])
    assert result.exit_code == 0, result.output
    return result.output


def test_new_and_open_register_without_duplicates(tmp_path: Path, make_vault: Callable[..., Path]) -> None:
    """`new` and `open` register the vault; reopening it keeps a single entry."""
    runner = CliRunner()
    new_root = tmp_path / "fresh"
    runner.invoke(cli, ["new", str(new_root)])
    existing = make_vault("existing")
    runner.invoke(cli, ["open", str(existing)])
    runner.invoke(cli, ["open", str(existing)])

    entries = json.loads(registry_path().read_text())["projects"]
    assert sorted(e["path"] for e in entries) == sorted([str(new_root.resolve()), str(existing.resolve())])


def test_ls_without_path_lists_most_recent_first(tmp_path: Path) -> None:
    """Registered projects are listed most recently used first, and survive across invocations."""
    runner = CliRunner()
    a, b = tmp_path / "a", tmp_path / "b"
    runner.invoke(cli, ["new", str(a)])
    runner.invoke(cli, ["new", str(b)])
    assert _ls().splitlines() == [str(b.resolve()), str(a.resolve())]

    runner.invoke(cli, ["open", str(a)])
    assert _ls().splitlines() == [str(a.resolve()), str(b.resolve())]


def test_ls_with_path_still_lists_pages(make_vault: Callable[..., Path]) -> None:
    """Giving `ls` a path keeps listing pages, not projects."""
    root = make_vault()
    (root / "wiki" / "entities" / "ada.md").write_text("---\ntype: entity\ntitle: Ada\n---\n")
    result = CliRunner().invoke(cli, ["ls", str(root)])
    assert "entities/ada.md" in result.output


def test_ls_tolerates_vault_folder_that_no_longer_exists(tmp_path: Path) -> None:
    """A registered vault that has been deleted is still listed, flagged as missing."""
    gone = tmp_path / "gone"
    CliRunner().invoke(cli, ["new", str(gone)])
    for child in sorted(gone.rglob("*"), reverse=True):
        child.unlink() if child.is_file() else child.rmdir()
    gone.rmdir()
    assert "(missing)" in _ls()


def test_missing_registry_lists_nothing() -> None:
    """No registry file yet is a normal empty state."""
    assert not _ls()


@pytest.mark.parametrize(
    "content",
    ["", "{not json", "[1, 2]", '"text"', '{"projects": "nope"}', '{"projects": [1, null, {"path": 5}, {}]}'],
)
def test_bad_registry_is_empty_with_notice_and_recoverable(content: str, tmp_path: Path) -> None:
    """Empty, corrupt or malformed registry content never raises, and the next register repairs it."""
    path = registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    runner = CliRunner()
    result = runner.invoke(cli, ["ls"])
    assert result.exit_code == 0, result.output
    assert not result.stdout

    root = tmp_path / "v"
    assert runner.invoke(cli, ["new", str(root)]).exit_code == 0
    assert _ls().splitlines() == [str(root.resolve())]


def test_corrupt_registry_prints_notice() -> None:
    """A corrupt file produces a notice on stderr."""
    path = registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not json")
    result = CliRunner().invoke(cli, ["ls"])
    assert "registry" in result.stderr.lower()


def test_registry_never_inside_vault(tmp_path: Path) -> None:
    """The registry lives under MINDSTEW_HOME, not in the vault."""
    root = tmp_path / "v"
    CliRunner().invoke(cli, ["new", str(root)])
    assert not list(root.rglob("projects.json"))
    assert registry_path().is_file()


def test_unwritable_registry_warns_but_command_succeeds(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """If the registry cannot be written, `new` still succeeds and prints a notice."""
    blocker = tmp_path / "blocker"
    blocker.write_text("")
    monkeypatch.setenv("MINDSTEW_HOME", str(blocker))
    result = CliRunner().invoke(cli, ["new", str(tmp_path / "v")])
    assert result.exit_code == 0, result.output
    assert "could not update" in result.stderr


def test_new_on_corrupt_registry_prints_notice_and_repairs(tmp_path: Path) -> None:
    """`new` does not silently overwrite a corrupt registry: it says so on stderr."""
    path = registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not json")
    result = CliRunner().invoke(cli, ["new", str(tmp_path / "v")])
    assert result.exit_code == 0, result.output
    assert "unreadable" in result.stderr
    assert json.loads(path.read_text())["projects"]
