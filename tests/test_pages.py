"""Tests for the page model, tolerant frontmatter reader and `ls`/`show`."""

from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner

from mindstew.cli import cli
from mindstew.pages import list_pages, read_page
from mindstew.vault import PAGE_TYPES

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_six_page_types_map_to_folders() -> None:
    """The six types map to their typed folders."""
    assert PAGE_TYPES == {
        "entity": "entities",
        "concept": "concepts",
        "source": "sources",
        "query": "queries",
        "comparison": "comparisons",
        "synthesis": "synthesis",
    }


def test_reads_well_formed_page(tmp_path: Path) -> None:
    """A well-formed page yields type, title, sources, tags and body; unknown fields are ignored."""
    p = _write(
        tmp_path / "p.md",
        "---\ntype: entity\ntitle: Ada\nsources: [sources/a.pdf]\ntags: [x, y]\nmood: happy\n---\nBody\n",
    )
    page = read_page(p)
    assert (page.type, page.title, page.sources, page.tags) == ("entity", "Ada", ["sources/a.pdf"], ["x", "y"])
    assert page.body == "Body\n"


@pytest.mark.parametrize("bad", ["", "null", "~", "42", "just text", "[a, b]", "- a\n- b", "{unclosed: ["])
def test_malformed_frontmatter_block_never_raises(tmp_path: Path, bad: str) -> None:
    """Non-mapping or unparseable frontmatter yields an empty page rather than an error."""
    page = read_page(_write(tmp_path / "p.md", f"---\n{bad}\n---\nBody\n"))
    assert (page.type, page.title, page.sources, page.tags) == (None, None, [], [])


@pytest.mark.parametrize("field", ["type", "sources", "tags", "title"])
@pytest.mark.parametrize("bad", ["", "null", "42", "scalar", "{a: b}", "[1, {a: b}]"])
def test_malformed_field_values_are_skipped(tmp_path: Path, field: str, bad: str) -> None:
    """Absent, null, scalar and non-mapping field values never raise and are not kept."""
    page = read_page(_write(tmp_path / "p.md", f"---\n{field}: {bad}\ntitle: Keep\n---\n"))
    assert page.type is None
    assert page.sources == []
    assert page.tags == []
    if field != "title":
        assert page.title == "Keep"


def test_no_frontmatter_and_unterminated(tmp_path: Path) -> None:
    """Pages without a closed frontmatter block are all body."""
    assert read_page(_write(tmp_path / "a.md", "hello")).body == "hello"
    assert read_page(_write(tmp_path / "b.md", "---\ntype: entity\n")).type is None


def _fixture_vault(make_vault: Callable[..., Path]) -> Path:
    root = make_vault()
    wiki = root / "wiki"
    ada = "---\ntype: entity\ntitle: Ada\nsources: [sources/a.pdf]\n---\nAda wrote code.\n"
    _write(wiki / "entities" / "ada.md", ada)
    _write(wiki / "concepts" / "broken.md", "---\ntype: [oops\nsources: nope\n---\nStill readable.\n")
    _write(wiki / "concepts" / "nofm.md", "No frontmatter.\n")
    for name in ("index.md", "log.md", "overview.md"):
        _write(wiki / name, "---\ntype: bogus\n---\n")
    _write(root / "purpose.md", "# Purpose\n")
    return root


def test_list_pages_skips_exempt_root_files(make_vault: Callable[..., Path]) -> None:
    """Only pages in typed folders are listed."""
    names = [p.path.name for p in list_pages(_fixture_vault(make_vault))]
    assert names == ["broken.md", "nofm.md", "ada.md"]


def test_ls_and_show_on_partly_broken_vault(make_vault: Callable[..., Path]) -> None:
    """`ls` lists every page and `show` prints metadata and body, even for broken pages."""
    root = _fixture_vault(make_vault)
    runner = CliRunner()

    ls = runner.invoke(cli, ["ls", str(root)])
    assert ls.exit_code == 0, ls.output
    assert "entities/ada.md\tentity\tAda" in ls.output
    assert "concepts/broken.md\t?" in ls.output
    assert "index.md" not in ls.output

    show = runner.invoke(cli, ["show", str(root), "entities/ada"])
    assert show.exit_code == 0, show.output
    assert "title: Ada" in show.output
    assert "sources: sources/a.pdf" in show.output
    assert "Ada wrote code." in show.output

    assert runner.invoke(cli, ["show", str(root), "concepts/broken"]).exit_code == 0
    assert runner.invoke(cli, ["show", str(root), "index"]).exit_code != 0
    assert runner.invoke(cli, ["show", str(root), "entities/../../purpose"]).exit_code != 0
