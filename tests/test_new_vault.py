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


def test_six_page_types() -> None:
    """There are exactly six typed page folders."""
    assert len(PAGE_TYPE_FOLDERS) == 6


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


def test_derived_dirs_documented_as_rebuildable(make_vault: Callable[..., Path]) -> None:
    """Derived folders say they can be rebuilt."""
    root = make_vault()
    for sub in ("index", "cache"):
        assert "rebuilt" in (root / ".mindstew" / sub / "README.md").read_text(encoding="utf-8").lower()


def test_create_into_existing_empty_dir(tmp_path: Path) -> None:
    """Scaffolding into an existing empty directory works."""
    create_vault(tmp_path)
    assert is_vault(tmp_path)
