"""Wiki pages: a tolerant frontmatter reader and page listing."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import yaml

from mindstew.links import Resolver
from mindstew.vault import PAGE_TYPE_FOLDERS, PAGE_TYPES, vault_path

if TYPE_CHECKING:
    from pathlib import Path

    from mindstew.links import Link


def wiki_root(vault: Path) -> Path:
    """Return the vault's ``wiki/`` folder."""
    return vault / "wiki"


@dataclass(frozen=True)
class Page:
    """A wiki page as read from disk; invalid metadata is left as None / empty."""

    path: Path
    type: str | None = None
    title: str | None = None
    sources: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)
    body: str = ""

    def wiki_relpath(self, vault: Path) -> str:
        """Return this page's path relative to the vault's ``wiki/`` folder."""
        return str(self.path.relative_to(wiki_root(vault)))


def _str_list(value: object) -> list[str]:
    """Return the string items of a list, or [] for anything else."""
    return [v for v in value if isinstance(v, str)] if isinstance(value, list) else []


def _split_frontmatter(text: str) -> tuple[object, str]:
    """Split ``text`` into parsed frontmatter (any YAML value, or None) and body. Never raises."""
    lines = text.split("\n")
    if not lines or lines[0].rstrip() != "---":
        return None, text
    for i, line in enumerate(lines[1:], start=1):
        if line.rstrip() == "---":
            try:
                meta = yaml.safe_load("\n".join(lines[1:i]))
            except yaml.YAMLError:
                meta = None
            return meta, "\n".join(lines[i + 1 :])
    return None, text


def read_page(path: Path) -> Page:
    """Read the page at ``path``, keeping only the valid frontmatter fields. Unknown fields are ignored."""
    meta, body = _split_frontmatter(path.read_text(encoding="utf-8", errors="replace"))
    if not isinstance(meta, dict):
        meta = {}
    page_type, title = meta.get("type"), meta.get("title")
    return Page(
        path=path,
        type=page_type if isinstance(page_type, str) and page_type in PAGE_TYPES else None,
        title=title if isinstance(title, str) else None,
        sources=_str_list(meta.get("sources")),
        tags=_str_list(meta.get("tags")),
        aliases=_str_list(meta.get("aliases")),
        body=body,
    )


def list_pages(vault: Path) -> list[Page]:
    """Return every page in the vault's typed folders, sorted by path."""
    wiki = wiki_root(vault)
    # Pages live only in typed folders, so index/log/overview/purpose/schema at the root are never scanned.
    paths = (p for folder in PAGE_TYPE_FOLDERS for p in (wiki / folder).rglob("*.md"))
    return [read_page(p) for p in sorted(paths)]


def page_file(vault: Path, name: str) -> Path | None:
    """Return the resolved file for a page path relative to ``wiki/`` (``.md`` optional), or None if not a page."""
    rel = name if name.endswith(".md") else f"{name}.md"
    wiki = wiki_root(vault).resolve()
    path = vault_path(wiki, rel)
    if not path or not path.is_file() or path.relative_to(wiki).parts[0] not in PAGE_TYPE_FOLDERS:
        return None
    return path


def find_page(vault: Path, name: str) -> Page | None:
    """Find a page by path relative to ``wiki/`` (the ``.md`` suffix is optional)."""
    path = page_file(vault, name)
    return read_page(path) if path else None


def describe_page(
    vault: Path, name: str, *, pages: list[Page] | None = None, resolver: Resolver | None = None
) -> tuple[Page, list[Link]] | None:
    """Return the page at ``name`` (relative to ``wiki/``) and its links resolved against the whole vault, or None.

    A caller describing many pages passes the vault's ``pages`` (and a ``resolver`` over them) to avoid relisting.
    """
    path = page_file(vault, name)
    pages = list_pages(vault) if pages is None else pages
    found = next((p for p in pages if path and p.path.resolve() == path), None)
    return (found, (resolver or Resolver(pages)).resolve_body(found.body)) if found else None
