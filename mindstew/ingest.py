"""Two-step structured ingest of Markdown/text sources into typed wiki pages.

``process_item(vault)`` returns the ``process`` callable for ``Worker``: it raises on any failure (so the queue's
retry cap applies) and validates every generated page before writing any, so a failure leaves no partial writes.
"""

import logging
from typing import TYPE_CHECKING

import yaml
from pydantic import BaseModel, Field

from mindstew import adapter
from mindstew.links import Resolver
from mindstew.pages import list_pages, read_page
from mindstew.providers import resolve_route
from mindstew.slugs import new_page_path
from mindstew.vault import PAGE_TYPES, atomic_write_text

if TYPE_CHECKING:
    from collections.abc import Callable, Collection
    from pathlib import Path

    from mindstew.ingest_queue import QueueItem

logger = logging.getLogger(__name__)

TEXT_SUFFIXES = (".md", ".txt")
_SOURCE_READ_ERRORS = (ValueError, OSError)  # ValueError: outside the vault, or not UTF-8


class IngestError(Exception):
    """An ingest item cannot be processed (no route, unsupported source, invalid model output)."""


class Analysis(BaseModel):
    """Step 1: what the source says and which pages it warrants."""

    summary: str
    planned_pages: list[str] = Field(default_factory=list)


class GeneratedPage(BaseModel):
    """Step 2: one page to write. ``sources`` are vault-relative paths; ``body`` may contain ``[[wikilinks]]``."""

    type: str
    title: str
    sources: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    body: str = ""


class GeneratedPages(BaseModel):
    """Step 2 output."""

    pages: list[GeneratedPage]


def _read(vault: Path, name: str) -> str:
    """Return a vault file's text, or '' if unreadable."""
    try:
        return (vault / name).read_text(encoding="utf-8")
    except OSError:
        return ""


def _validate(pages: list[GeneratedPage]) -> None:
    """Raise ``IngestError`` if any page is invalid; called before anything is written."""
    for page in pages:
        if page.type not in PAGE_TYPES:
            raise IngestError(f"model returned unknown page type {page.type!r}")
        if not page.title.strip():
            raise IngestError("model returned a page with an empty title")
        for s in page.sources:
            if s.startswith(("/", "\\")) or ".." in s.replace("\\", "/").split("/"):
                raise IngestError(f"page {page.title!r} has non vault-relative source {s!r}")


def _write(vault: Path, page: GeneratedPage, source: str, overwrite: Path | None = None) -> Path:
    """Write ``page`` to a new free path in its typed folder (or over ``overwrite``) and return the path."""
    meta = {
        "type": page.type,
        "title": page.title.strip(),
        "sources": list(dict.fromkeys([source, *page.sources])),
        "tags": page.tags,
    }
    text = f"---\n{yaml.safe_dump(meta, sort_keys=False, allow_unicode=True)}---\n\n{page.body.strip()}\n"
    if overwrite:
        atomic_write_text(overwrite, text)
        return overwrite
    path = new_page_path(vault, page.type, page.title)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as f:  # "x": never overwrite an existing page
        f.write(text)
    return path


def _pick(pages: list[GeneratedPage], target: Path) -> GeneratedPage | None:
    """Pick the generated page that replaces ``target``: the one with the same title, if any."""
    title = (read_page(target).title or "").strip().casefold()
    return next((p for p in pages if title and p.title.strip().casefold() == title), None)


def _write_all(
    vault: Path, pages: list[GeneratedPage], source: str, overwrite: Path | None, target: GeneratedPage | None
) -> list[Path]:
    """Write every page; if one fails, remove the new pages already written so a retry makes no duplicates."""
    paths: list[Path] = []
    try:
        paths.extend(_write(vault, p, source, overwrite if p is target else None) for p in pages)
    except BaseException:
        for done in paths:
            if done != overwrite:
                done.unlink(missing_ok=True)
        raise
    return paths


def _log_unresolved(vault: Path, paths: list[Path]) -> None:
    """Log every ``[[wikilink]]`` in the written pages that resolves to no page."""
    resolver = Resolver(list_pages(vault))
    for path in paths:
        for link in resolver.resolve_body(read_page(path).body):
            if link.page is None:
                logger.info("unresolved link [[%s]] in %s", link.target, path)


def process_item(
    vault: Path, overwrite: Path | None = None, only: Collection[Path] = ()
) -> Callable[[QueueItem], None]:
    """Return a ``process(item)`` for ``Worker`` that ingests ``.md``/``.txt`` sources into ``vault``.

    With ``overwrite`` (an existing page, used by ``--reingest``) the generated page with the same title is
    written over it instead of to a new ``-N`` path, but only for items whose path is in ``only`` (the sources
    enqueued for that reingest); any other generated pages, and all other items, produce new pages.

    Raises (inside the returned callable) ``IngestError`` for no ingest route, an unsupported or unreadable
    source, or invalid model output; adapter errors propagate unchanged.
    """

    def process(item: QueueItem) -> None:
        """Ingest one queued text source."""
        if item.path.suffix.lower() not in TEXT_SUFFIXES:
            raise IngestError(f"unsupported source type: {item.path.name}")
        route, notices = resolve_route(vault, "ingest")
        if route is None:
            hint = "".join(f" ({n})" for n in notices)
            raise IngestError(f"no ingest route configured; set one with the providers/routes commands{hint}")
        try:
            source = item.path.resolve().relative_to(vault.resolve()).as_posix()
            text = item.path.read_text(encoding="utf-8")
        except _SOURCE_READ_ERRORS as e:
            raise IngestError(f"cannot read source {item.path}: {e}") from e

        context = f"# purpose.md\n{_read(vault, 'purpose.md')}\n\n# schema.md\n{_read(vault, 'schema.md')}"
        brief = f"{context}\n\n# Source: {source}\n{text}"
        analysis = adapter.complete(
            route,
            [
                {"role": "system", "content": "Analyze the source for a knowledge wiki: summarize it and plan pages."},
                {"role": "user", "content": brief},
            ],
            Analysis,
        )
        generated = adapter.complete(
            route,
            [
                {"role": "system", "content": "Write the planned wiki pages as JSON. Link pages with [[Title]]."},
                {"role": "user", "content": f"{brief}\n\n# Analysis\n{analysis.model_dump_json()}"},
            ],
            GeneratedPages,
        )
        _validate(generated.pages)
        target = _pick(generated.pages, overwrite) if overwrite and item.path in only else None
        _log_unresolved(vault, _write_all(vault, generated.pages, source, overwrite, target))

    return process
