"""Filesystem-safe page slugs with numeric disambiguation."""

import re
import unicodedata
from typing import TYPE_CHECKING

from mindstew.vault import PAGE_TYPES

if TYPE_CHECKING:
    from pathlib import Path


def slugify(title: str) -> str:
    """Lowercase ``title`` and join its letter/digit runs with hyphens; unicode letters are kept. May return ''."""
    text = unicodedata.normalize("NFKC", title).casefold()
    return "-".join(re.findall(r"[^\W_]+", text))


def new_page_path(vault: Path, page_type: str, title: str, fallback: str = "") -> Path:
    """Return a free ``wiki/<typed folder>/<slug>[-N].md`` path; never one that exists, even by case.

    An empty slug from ``title`` falls back to ``fallback`` (e.g. a source filename), then to "untitled".
    """
    if page_type not in PAGE_TYPES:
        msg = f"unknown page type: {page_type!r}"
        raise ValueError(msg)
    folder = vault / "wiki" / PAGE_TYPES[page_type]
    base = slugify(title) or slugify(fallback) or "untitled"
    # ponytail: lowercase scan per call; fine for human-scale folders, cache if ingest creates thousands.
    taken = {p.name.casefold() for p in folder.iterdir()} if folder.is_dir() else set()
    slug, n = base, 1
    while f"{slug}.md" in taken:
        n += 1
        slug = f"{base}-{n}"
    return folder / f"{slug}.md"
