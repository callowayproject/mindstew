"""Tests for non-destructive vault adoption via `mindstew open`."""

from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner

from mindstew.cli import cli
from mindstew.vault import is_vault

if TYPE_CHECKING:
    from pathlib import Path


def _snapshot(root: Path) -> dict[str, bytes | None]:
    """Map every path under root to its bytes (None for directories)."""
    return {str(p.relative_to(root)): (p.read_bytes() if p.is_file() else None) for p in root.rglob("*")}


def _obsidian_vault(root: Path) -> None:
    (root / ".obsidian").mkdir(parents=True)
    (root / ".obsidian" / "app.json").write_text('{"a": 1}', encoding="utf-8")
    (root / "Notes").mkdir()
    (root / "Notes" / "Ada.md").write_text("# Ada\n[[Babbage]]\n", encoding="utf-8")
    (root / "purpose.md").write_text("mine", encoding="utf-8")


def test_open_preserves_existing_files(tmp_path: Path) -> None:
    """Every pre-existing file stays byte-identical and no .obsidian is added or changed."""
    _obsidian_vault(tmp_path)
    before = _snapshot(tmp_path)

    result = CliRunner().invoke(cli, ["open", str(tmp_path)])

    assert result.exit_code == 0, result.output
    after = _snapshot(tmp_path)
    assert {k: v for k, v in after.items() if k in before} == before
    assert is_vault(tmp_path)
    assert (tmp_path / "schema.md").is_file()


def test_open_does_not_create_obsidian_dir(tmp_path: Path) -> None:
    """A folder without .obsidian/ gets none."""
    result = CliRunner().invoke(cli, ["open", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert is_vault(tmp_path)
    assert not (tmp_path / ".obsidian").exists()


def test_open_is_idempotent(tmp_path: Path) -> None:
    """Opening an existing vault twice succeeds and changes nothing."""
    CliRunner().invoke(cli, ["open", str(tmp_path)])
    before = _snapshot(tmp_path)

    result = CliRunner().invoke(cli, ["open", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert _snapshot(tmp_path) == before


@pytest.mark.parametrize(
    ("name", "is_dir"), [("wiki", False), ("sources", False), (".mindstew", False), ("purpose.md", True)]
)
def test_open_conflicting_entry_fails_cleanly(tmp_path: Path, name: str, is_dir: bool) -> None:
    """A wrong-kind entry on a scaffold path gives a clear error and leaves the folder untouched."""
    if is_dir:
        (tmp_path / name).mkdir()
    else:
        (tmp_path / name).write_text("x", encoding="utf-8")
    before = _snapshot(tmp_path)

    result = CliRunner().invoke(cli, ["open", str(tmp_path)])

    assert result.exit_code != 0
    assert name in result.output
    assert "Traceback" not in result.output
    assert _snapshot(tmp_path) == before


def test_open_dangling_symlink_fails_cleanly(tmp_path: Path) -> None:
    """A dangling symlink on a scaffold path is a conflict, not a traceback."""
    (tmp_path / "wiki").symlink_to(tmp_path / "missing")

    result = CliRunner().invoke(cli, ["open", str(tmp_path)])

    assert result.exit_code != 0
    assert "wiki" in result.output
    assert "Traceback" not in result.output
    assert not (tmp_path / "sources").exists()


def test_open_missing_path_fails_clearly(tmp_path: Path) -> None:
    """A nonexistent path is a clear error."""
    result = CliRunner().invoke(cli, ["open", str(tmp_path / "nope")])

    assert result.exit_code != 0
    assert "does not exist" in result.output


def test_open_adds_missing_derived_dirs(tmp_path: Path) -> None:
    """A vault missing only .mindstew/index and cache gets them back, touching nothing else."""
    CliRunner().invoke(cli, ["open", str(tmp_path)])
    (tmp_path / "purpose.md").write_text("mine", encoding="utf-8")
    (tmp_path / ".mindstew" / "index").rmdir()
    (tmp_path / ".mindstew" / "cache").rmdir()
    before = _snapshot(tmp_path)

    result = CliRunner().invoke(cli, ["open", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert (tmp_path / ".mindstew" / "index").is_dir()
    assert (tmp_path / ".mindstew" / "cache").is_dir()
    assert {k: v for k, v in _snapshot(tmp_path).items() if k in before} == before
    again = _snapshot(tmp_path)
    CliRunner().invoke(cli, ["open", str(tmp_path)])
    assert _snapshot(tmp_path) == again


def test_open_leaves_obsidian_dir_byte_identical(tmp_path: Path) -> None:
    """A pre-existing .obsidian/ is unchanged by open."""
    _obsidian_vault(tmp_path)
    (tmp_path / ".obsidian" / "plugins").mkdir()
    (tmp_path / ".obsidian" / "plugins" / "x.json").write_bytes(b"\x00\x01")
    before = {k: v for k, v in _snapshot(tmp_path).items() if k.startswith(".obsidian")}

    CliRunner().invoke(cli, ["open", str(tmp_path)])

    after = {k: v for k, v in _snapshot(tmp_path).items() if k.startswith(".obsidian")}
    assert after == before
