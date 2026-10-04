"""Tests for vault scaffolding and the `mindstew new` command."""

import shutil
from typing import TYPE_CHECKING

from click.testing import CliRunner

from mindstew.cli import cli
from mindstew.vault import PAGE_TYPE_FOLDERS, create_vault, is_vault

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


def test_new_creates_full_tree(tmp_path: Path) -> None:
    """`new` builds the whole vault tree and exits 0."""
    root = tmp_path / "v"
    result = CliRunner().invoke(cli, ["new", str(root)])

    assert result.exit_code == 0, result.output
    assert (root / "sources").is_dir()
    for folder in PAGE_TYPE_FOLDERS:
        assert (root / "wiki" / folder).is_dir()
    assert (root / ".mindstew" / "config.yaml").is_file()
    for sub in ("index", "cache", "skills"):
        assert (root / ".mindstew" / sub).is_dir()


def test_never_creates_obsidian_dir(make_vault: Callable[..., Path]) -> None:
    """No Obsidian config is ever created."""
    assert not (make_vault() / ".obsidian").exists()


def test_purpose_and_schema_are_plain_markdown(make_vault: Callable[..., Path]) -> None:
    """Starter purpose and schema are editable Markdown."""
    root = make_vault()
    for name in ("purpose.md", "schema.md"):
        text = (root / name).read_text(encoding="utf-8")
        assert text.startswith("# ")
        assert len(text.splitlines()) > 3


def test_refuses_existing_vault(make_vault: Callable[..., Path]) -> None:
    """`new` refuses an existing vault and leaves it untouched."""
    root = make_vault()
    (root / "purpose.md").write_text("mine", encoding="utf-8")

    result = CliRunner().invoke(cli, ["new", str(root)])

    assert result.exit_code != 0
    assert "already contains a vault" in result.output
    assert (root / "purpose.md").read_text(encoding="utf-8") == "mine"


def test_derived_data_is_rebuildable(make_vault: Callable[..., Path]) -> None:
    """Deleting derived folders leaves the vault valid."""
    root = make_vault()
    shutil.rmtree(root / ".mindstew" / "index")
    shutil.rmtree(root / ".mindstew" / "cache")

    assert is_vault(root)
    result = CliRunner().invoke(cli, ["new", str(root)])
    assert "already contains a vault" in result.output


def test_derived_dirs_created_empty(make_vault: Callable[..., Path]) -> None:
    """Derived folders start empty."""
    root = make_vault()
    for sub in ("index", "cache"):
        assert list((root / ".mindstew" / sub).iterdir()) == []


def test_new_resumes_partial_vault_without_overwriting(tmp_path: Path) -> None:
    """A second `new` fills in what a failed attempt left behind and keeps existing files."""
    (tmp_path / "wiki" / "entities").mkdir(parents=True)
    (tmp_path / "purpose.md").write_text("mine", encoding="utf-8")
    (tmp_path / "wiki" / "entities" / "Ada.md").write_text("keep", encoding="utf-8")

    result = CliRunner().invoke(cli, ["new", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert is_vault(tmp_path)
    assert (tmp_path / "purpose.md").read_text(encoding="utf-8") == "mine"
    assert (tmp_path / "wiki" / "entities" / "Ada.md").read_text(encoding="utf-8") == "keep"
    assert (tmp_path / "schema.md").is_file()


def test_new_resumes_after_marker_written_first(tmp_path: Path) -> None:
    """Order doesn't matter: a lone config.yaml is not a complete vault."""
    (tmp_path / ".mindstew").mkdir()
    (tmp_path / ".mindstew" / "config.yaml").write_text("x: 1\n", encoding="utf-8")

    assert not is_vault(tmp_path)
    create_vault(tmp_path)
    assert is_vault(tmp_path)
    assert (tmp_path / ".mindstew" / "config.yaml").read_text(encoding="utf-8") == "x: 1\n"


def test_create_into_existing_empty_dir(tmp_path: Path) -> None:
    """Scaffolding into an existing empty directory works."""
    create_vault(tmp_path)
    assert is_vault(tmp_path)
