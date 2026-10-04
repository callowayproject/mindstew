"""Tests for the shared wikilink resolver and `show` link output."""

from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner

from mindstew.cli import cli
from mindstew.links import Resolver, extract_links
from mindstew.pages import list_pages, read_page

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_extract_links_forms_and_dedupe() -> None:
    """Display text, heading and block anchors are stripped; order is kept and duplicates dropped."""
    body = "[[Ada]] [[Ada Lovelace|Ada]] [[Babbage#History]] [[ada]] [[Note^blk]] [[  ]] [[#Local]]"
    assert extract_links(body) == ["Ada", "Ada Lovelace", "Babbage", "ada", "Note"]


def test_frontmatter_links_field_is_ignored(tmp_path: Path) -> None:
    """Only the body contributes links."""
    page = read_page(_write(tmp_path / "p.md", "---\nlinks: ['[[Hidden]]']\n---\nSee [[Shown]].\n"))
    assert extract_links(page.body) == ["Shown"]


def _vault_with_pages(make_vault: Callable[..., Path], pages: dict[str, str]) -> Resolver:
    root = make_vault()
    for rel, text in pages.items():
        _write(root / "wiki" / rel, text)
    return Resolver(list_pages(root))


def test_resolves_case_insensitively_with_anchors_and_aliases(make_vault: Callable[..., Path]) -> None:
    """Title match ignores case; `|display`, `#heading` and frontmatter aliases all reach the page."""
    r = _vault_with_pages(
        make_vault,
        {"entities/ada.md": "---\ntitle: Ada Lovelace\naliases: [Countess, ada l]\n---\n"},
    )
    for target in ("Ada Lovelace", "ada lovelace", "ADA LOVELACE", "countess", "Ada L"):
        page = r.resolve(target)
        assert page is not None, target
        assert page.title == "Ada Lovelace"
    assert [t for t, _ in r.resolve_body("[[ada lovelace|Ada]] [[Countess#Life]]")] == ["ada lovelace", "Countess"]
    assert all(p is not None for _, p in r.resolve_body("[[ada lovelace|Ada]] [[Countess#Life]]"))


def test_unresolved_never_raises(make_vault: Callable[..., Path]) -> None:
    """Unknown targets resolve to None."""
    r = _vault_with_pages(make_vault, {"entities/ada.md": "---\ntitle: Ada\n---\n"})
    assert r.resolve("Nobody") is None
    assert r.resolve("") is None
    assert r.resolve_body("[[Nobody]]") == [("Nobody", None)]


def test_duplicate_titles_resolve_to_first_path(make_vault: Callable[..., Path]) -> None:
    """Ambiguity is deterministic: the page sorting first by path wins; a title beats another page's alias."""
    r = _vault_with_pages(
        make_vault,
        {
            "entities/b.md": "---\ntitle: Dup\n---\n",
            "concepts/a.md": "---\ntitle: Dup\n---\n",
            "concepts/c.md": "---\ntitle: Other\naliases: [Dup]\n---\n",
        },
    )
    page = r.resolve("dup")
    assert page is not None
    assert page.path.parts[-2:] == ("concepts", "a.md")


@pytest.mark.parametrize("bad", ["", "null", "42", "scalar", "{a: b}", "[1, {a: b}, null]"])
@pytest.mark.parametrize("field", ["title", "aliases"])
def test_malformed_title_and_alias_fields_are_skipped(make_vault: Callable[..., Path], field: str, bad: str) -> None:
    """Absent, null, scalar and non-mapping title/aliases never raise."""
    r = _vault_with_pages(make_vault, {"entities/x.md": f"---\n{field}: {bad}\n---\n"})
    assert r.resolve("anything") is None


def test_show_prints_resolved_and_unresolved_links(make_vault: Callable[..., Path]) -> None:
    """`show` lists each link as resolved (with its page) or unresolved."""
    root = make_vault()
    _write(
        root / "wiki" / "entities" / "ada.md",
        "---\ntype: entity\ntitle: Ada\n---\nSee [[Babbage#Work]] and [[Ghost]].\n",
    )
    _write(root / "wiki" / "entities" / "babbage.md", "---\ntype: entity\ntitle: Babbage\n---\n")
    out = CliRunner().invoke(cli, ["show", str(root), "entities/ada"])
    assert out.exit_code == 0, out.output
    assert "Babbage -> entities/babbage.md" in out.output
    assert "Ghost -> (unresolved)" in out.output
