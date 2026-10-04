"""Filesystem-safe page slugs with numeric disambiguation."""

import unicodedata
from pathlib import PurePath
from typing import TYPE_CHECKING

from mindstew.vault import PAGE_TYPES

if TYPE_CHECKING:
    from pathlib import Path


MAX_FILENAME_BYTES = 250  # headroom under the 255-byte limit of Linux and macOS filesystems
# Windows device names are reserved even with an extension ("con.md"). Linux/macOS reserve only "." and "..".
WINDOWS_RESERVED = frozenset({"con", "prn", "aux", "nul", *(f"{d}{i}" for d in ("com", "lpt") for i in range(1, 10))})


def slugify(title: str) -> str:
    """Lowercase ``title`` and join its letter/digit runs with hyphens; unicode letters are kept. May return ''."""
    text = unicodedata.normalize("NFKC", title).lower()
    # Combining marks (Devanagari vowel signs, Thai, etc.) belong to the letter they modify.
    return "-".join("".join(c if c.isalnum() or unicodedata.category(c)[0] == "M" else " " for c in text).split())


def new_page_path(vault: Path, page_type: str, title: str, fallback: str = "") -> Path:
    """Return a free ``wiki/<typed folder>/<slug>[-N].md`` path; never one that exists, even by case.

    An empty slug from ``title`` falls back to ``fallback`` (a filename; its extension is dropped), then to "untitled".
    The name is capped at ``MAX_FILENAME_BYTES`` (suffix included) and Windows device names get a ``-page`` tail.
    """
    if page_type not in PAGE_TYPES:
        msg = f"unknown page type: {page_type!r}"
        raise ValueError(msg)
    folder = vault / "wiki" / PAGE_TYPES[page_type]
    base = slugify(title) or slugify(PurePath(fallback).stem) or "untitled"
    if base in WINDOWS_RESERVED:
        base += "-page"
    # ponytail: lowercase scan per call; fine for human-scale folders, cache if ingest creates thousands.
    taken = {p.name.casefold() for p in folder.iterdir()} if folder.is_dir() else set()
    n = 1
    while True:
        suffix = f"-{n}" if n > 1 else ""
        room = MAX_FILENAME_BYTES - len(".md") - len(suffix)
        # Cut on a character boundary, then drop any hyphen left dangling.
        slug = base.encode()[:room].decode(errors="ignore").rstrip("-") + suffix
        if f"{slug}.md" not in taken:
            return folder / f"{slug}.md"
        n += 1
