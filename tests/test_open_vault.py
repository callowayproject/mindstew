"""Tests for non-destructive vault adoption via `mindstew open`."""

from typing import TYPE_CHECKING

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


def test_open_missing_path_fails_clearly(tmp_path: Path) -> None:
    """A nonexistent path is a clear error."""
    result = CliRunner().invoke(cli, ["open", str(tmp_path / "nope")])

    assert result.exit_code != 0
    assert "does not exist" in result.output
