"""Tests for slugs and numeric disambiguation (headless core API, no CLI)."""

from typing import TYPE_CHECKING

import pytest

from mindstew.slugs import MAX_FILENAME_BYTES, WINDOWS_RESERVED, new_page_path, slugify

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Ada Lovelace", "ada-lovelace"),
        ("  ADA   lovelace  ", "ada-lovelace"),
        ("Ada, Countess of Lovelace!", "ada-countess-of-lovelace"),
        ("a/b\\c:d*e?", "a-b-c-d-e"),
        ("snake_case & more", "snake-case-more"),
        ("Café Münster", "café-münster"),
        ("日本語 メモ", "日本語-メモ"),
        ("\uff21\uff44\uff41", "ada"),  # NFKC folds full-width forms
        ("\u0939\u093f\u0928\u094d\u0926\u0940", "\u0939\u093f\u0928\u094d\u0926\u0940"),  # combining marks kept
        ("", ""),
        ("!!! ???", ""),
    ],
)
def test_slugify(title: str, expected: str) -> None:
    """Slugs are lowercase, hyphen-separated and free of filesystem-hostile characters."""
    assert slugify(title) == expected


def test_new_page_path_disambiguates_against_disk(make_vault: Callable[..., Path]) -> None:
    """Each collision takes the next free suffix and nothing existing is overwritten."""
    root = make_vault()
    names = []
    for _ in range(3):
        path = new_page_path(root, "entity", "Ada Lovelace")
        assert not path.exists()
        path.write_text("x", encoding="utf-8")
        names.append(path.name)
    assert names == ["ada-lovelace.md", "ada-lovelace-2.md", "ada-lovelace-3.md"]


def test_collision_is_per_typed_folder_and_case_insensitive(make_vault: Callable[..., Path]) -> None:
    """The same slug in another typed folder is free; a case-variant file on disk still collides."""
    root = make_vault()
    (root / "wiki" / "entities" / "Ada.MD").write_text("x", encoding="utf-8")
    assert new_page_path(root, "concept", "Ada").name == "ada.md"
    assert new_page_path(root, "entity", "Ada").name == "ada-2.md"


def test_fallback_used_for_symbol_only_title(make_vault: Callable[..., Path]) -> None:
    """An unusable title falls back to the given name, then to 'untitled', and is still disambiguated."""
    root = make_vault()
    assert new_page_path(root, "source", "???", fallback="Report Q3.pdf").name == "report-q3.md"
    first = new_page_path(root, "source", "", fallback="")
    assert first.name == "untitled.md"
    first.write_text("x", encoding="utf-8")
    assert new_page_path(root, "source", "!!").name == "untitled-2.md"


def test_unknown_page_type_raises(make_vault: Callable[..., Path]) -> None:
    """Only the six page types are valid."""
    with pytest.raises(ValueError, match="page type"):
        new_page_path(make_vault(), "bogus", "x")


def test_gap_in_suffixes_is_filled(make_vault: Callable[..., Path]) -> None:
    """The lowest free suffix wins even when a higher one exists."""
    root = make_vault()
    for name in ("x.md", "x-3.md"):
        (root / "wiki" / "concepts" / name).write_text("x", encoding="utf-8")
    assert new_page_path(root, "concept", "x").name == "x-2.md"


@pytest.mark.parametrize("title", ["x" * 400, "日本語" * 100, ("word " * 100)])
def test_long_titles_are_capped_including_suffix(make_vault: Callable[..., Path], title: str) -> None:
    """Names stay within the byte cap on every collision, and truncation never splits a character."""
    root = make_vault()
    for _ in range(12):
        path = new_page_path(root, "entity", title)
        assert len(path.name.encode()) <= MAX_FILENAME_BYTES
        assert not path.exists()
        path.write_text("x", encoding="utf-8")
    assert len(list((root / "wiki" / "entities").iterdir())) == 12


@pytest.mark.parametrize("title", ["CON", "nul", "Com1", "LPT9", "aux", "COM\u00b9"])
def test_windows_reserved_names_are_avoided(make_vault: Callable[..., Path], title: str) -> None:
    """Device names are not valid filenames on Windows, with or without an extension."""
    name = new_page_path(make_vault(), "entity", title).name
    assert name.removesuffix(".md") not in WINDOWS_RESERVED
    assert name.endswith("-page.md")


def test_reserved_lookalikes_are_untouched(make_vault: Callable[..., Path]) -> None:
    """Only exact device names are rewritten."""
    assert new_page_path(make_vault(), "entity", "Console").name == "console.md"
