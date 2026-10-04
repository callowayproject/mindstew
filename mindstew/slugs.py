"""Filesystem-safe page slugs with numeric disambiguation."""

import unicodedata
from pathlib import PurePath
from typing import TYPE_CHECKING

from mindstew.vault import PAGE_TYPES

if TYPE_CHECKING:
    from pathlib import Path


def slugify(title: str) -> str:
    """Lowercase ``title`` and join its letter/digit runs with hyphens; unicode letters are kept. May return ''."""
    text = unicodedata.normalize("NFKC", title).lower()
    # Combining marks (Devanagari vowel signs, Thai, etc.) belong to the letter they modify.
    return "-".join("".join(c if c.isalnum() or unicodedata.category(c)[0] == "M" else " " for c in text).split())


def new_page_path(vault: Path, page_type: str, title: str, fallback: str = "") -> Path:
    """Return a free ``wiki/<typed folder>/<slug>[-N].md`` path; never one that exists, even by case.

    An empty slug from ``title`` falls back to ``fallback`` (a filename; its extension is dropped), then to "untitled".
    """
    if page_type not in PAGE_TYPES:
        msg = f"unknown page type: {page_type!r}"
        raise ValueError(msg)
    folder = vault / "wiki" / PAGE_TYPES[page_type]
    base = slugify(title) or slugify(PurePath(fallback).stem) or "untitled"
    # ponytail: lowercase scan per call; fine for human-scale folders, cache if ingest creates thousands.
    taken = {p.name.casefold() for p in folder.iterdir()} if folder.is_dir() else set()
    slug, n = base, 1
    while f"{slug}.md" in taken:
        n += 1
        slug = f"{base}-{n}"
    return folder / f"{slug}.md"
