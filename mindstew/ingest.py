"""Two-step structured ingest of Markdown/text sources into typed wiki pages.

``process_item(vault)`` returns the ``process`` callable for ``Worker``: it raises on any failure (so the queue's
retry cap applies) and validates every generated page before writing any, so a failure leaves no partial writes.
"""

import logging
import shutil
import threading
from typing import TYPE_CHECKING

import yaml
from pydantic import BaseModel, Field, field_validator

from mindstew import adapter
from mindstew.ingest_queue import enqueue, list_items
from mindstew.pages import describe_page, find_page, read_page, wiki_root
from mindstew.providers import resolve_route
from mindstew.slugs import new_page_path
from mindstew.vault import PAGE_TYPES, atomic_write_text, vault_path
from mindstew.worker import Worker

if TYPE_CHECKING:
    from collections.abc import Callable, Collection
    from pathlib import Path

    from mindstew.ingest_queue import QueueItem
    from mindstew.worker import Event

logger = logging.getLogger(__name__)

TEXT_SUFFIXES = (".md", ".txt")
CONFIG_FILES = ("schema.md", "purpose.md")  # vault configuration: model context, never source material
_META_TITLES = {n.removesuffix(".md") for n in CONFIG_FILES}
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

    @field_validator("sources", mode="before")
    @classmethod
    def _tolerate_sources(cls, v: object) -> list[str]:
        """Accept a missing, scalar or non-list ``sources`` from the model; keep only string entries."""
        if isinstance(v, str):
            return [v]
        return [s for s in v if isinstance(s, str)] if isinstance(v, list) else []


class GeneratedPages(BaseModel):
    """Step 2 output."""

    pages: list[GeneratedPage]


def _read(vault: Path, name: str) -> str:
    """Return a vault file's text, or '' if unreadable."""
    try:
        return (vault / name).read_text(encoding="utf-8")
    except OSError:
        return ""


def _validate(vault: Path, pages: list[GeneratedPage]) -> None:
    """Raise ``IngestError`` if any page is invalid; called before anything is written."""
    for page in pages:
        if page.type not in PAGE_TYPES:
            raise IngestError(f"model returned unknown page type {page.type!r}")
        if not page.title.strip():
            raise IngestError("model returned a page with an empty title")
        for s in page.sources:
            if vault_path(vault, s) is None:
                raise IngestError(f"page {page.title!r} has non vault-relative source {s!r}")


def _clean_source(vault: Path, s: str) -> str | None:
    """Return ``s`` as ``sources/<file>`` (``source:`` prefix stripped), or None if it is no source in the vault."""
    s = s.strip().removeprefix("source:").strip().replace("\\", "/").removeprefix("./")
    s = s if s.startswith("sources/") else f"sources/{s}"
    path = vault_path(vault, s)
    return s if path and path.is_file() else None


def _keep(page: GeneratedPage) -> bool:
    """False (and log) for a page with an empty body or one titled like a vault config file."""
    if not page.body.strip():
        logger.warning("skipping page %r: empty body", page.title)
    elif page.title.strip().casefold().removesuffix(".md") in _META_TITLES:
        logger.warning("skipping page %r: vault config, not a topic", page.title)
    else:
        return True
    return False


def _write(vault: Path, page: GeneratedPage, source: str, overwrite: Path | None = None) -> Path:
    """Write ``page`` to a new free path in its typed folder (or over ``overwrite``) and return the path."""
    meta = {
        "type": page.type,
        "title": page.title.strip(),
        "sources": list(dict.fromkeys([source, *filter(None, (_clean_source(vault, s) for s in page.sources))])),
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
    wiki = wiki_root(vault).resolve()
    for path in paths:
        described = describe_page(vault, str(path.resolve().relative_to(wiki)))
        for link in described[1] if described else ():
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
                {
                    "role": "system",
                    "content": (
                        "Write the planned wiki pages as JSON. Link pages with [[Title]]. "
                        "Do not emit pages with empty bodies; skip page types that have nothing to say. "
                        "schema.md and purpose.md are configuration, not source material: write no pages about them. "
                        "Keep entity titles exactly as written in the source."
                    ),
                },
                {"role": "user", "content": f"{brief}\n\n# Analysis\n{analysis.model_dump_json()}"},
            ],
            GeneratedPages,
        )
        _validate(vault, generated.pages)
        pages = [p for p in generated.pages if _keep(p)]
        target = _pick(pages, overwrite) if overwrite and item.path in only else None
        _log_unresolved(vault, _write_all(vault, pages, source, overwrite, target))

    return process


def stage(
    sources: Path, base: Path, path: Path, *, overwrite: bool = False, emit: Callable[[str], None] = lambda _: None
) -> Path | None:
    """Return the ``sources/`` path for ``path`` (under ``base``), copying it in if needed; None if skipped.

    Hidden files and vault config files are skipped silently, unsupported ones are reported to ``emit`` and
    skipped, and a clashing different file already in ``sources/`` is kept and reported unless ``overwrite``.
    """
    rel = path.relative_to(base)
    if any(part.startswith(".") for part in rel.parts):
        return None
    if path.parent == sources.parent and path.name in CONFIG_FILES:
        return None
    if path.suffix.lower() not in TEXT_SUFFIXES:
        emit(f"skipped (unsupported): {rel}")
        return None
    if path.is_relative_to(sources):
        return path
    dest = sources / rel
    if dest.exists() and dest.read_bytes() != path.read_bytes():
        if not overwrite:
            emit(f"skipped (exists in sources/, not overwritten): {rel}")
            return None
        shutil.copy2(path, dest)
    elif not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
    return dest


def collect(vault: Path, root: Path, emit: Callable[[str], None] = lambda _: None) -> list[Path]:
    """Stage the text sources under ``root`` (a file or folder) in ``vault/sources`` and return their paths."""
    sources = (vault / "sources").resolve()
    root = root.resolve()
    base = root.parent if root.is_file() else root
    found = [root] if root.is_file() else sorted(p for p in root.rglob("*") if p.is_file())
    return [dest for path in found if (dest := stage(sources, base, path, emit=emit))]


def show_event(emit: Callable[[str], None]) -> Callable[[Event], None]:
    """Return a worker subscriber that reports each item event to ``emit`` as a line."""

    def show(e: Event) -> None:
        if e.kind != "queue_drained":
            emit(
                f"{e.kind.removeprefix('item_')}: {e.path.name if e.path else ''}"
                + (f" ({e.error})" if e.error else "")
            )

    return show


def drain(vault: Path, process: Callable[[QueueItem], None], emit: Callable[[str], None]) -> int:
    """Run the worker until ``queue_drained``, reporting to ``emit``; return how many pending items ended failed."""
    pending = {i.id for i in list_items(vault) if i.status in ("queued", "running")}
    if not pending:
        emit("nothing to ingest")
        return 0
    drained = threading.Event()
    worker = Worker(vault, process, poll_interval=0.05)
    worker.subscribe(show_event(emit))
    worker.subscribe(lambda e: drained.set() if e.kind == "queue_drained" else None)
    worker.start()
    try:
        drained.wait()
    finally:
        worker.stop()
    return sum(1 for i in list_items(vault) if i.id in pending and i.status == "failed")


def reingest_page(vault: Path, page: str, *, emit: Callable[[str], None] = lambda _: None) -> int:
    """Regenerate ``page`` (relative to ``wiki/``) in place from its sources; return how many items failed.

    Raises ``ValueError`` for an unknown page or a source outside the vault, before enqueuing anything.
    """
    found = find_page(vault, page)
    if found is None:
        raise ValueError(f"no such page: {page}")
    for rel in found.sources:  # validate everything before enqueuing anything
        if vault_path(vault, rel) is None:
            raise ValueError(f"page source is not inside the vault: {rel!r}")
    only: set[Path] = set()
    for rel in found.sources:
        src = vault / rel
        if src.is_file():
            enqueue(vault, src, force=True)
            only.add(src.resolve())
        else:
            emit(f"skipped (missing source): {rel}")
    return drain(vault, process_item(vault, found.path, only), emit)


def ingest_path(vault: Path, path: Path | None = None, *, emit: Callable[[str], None] = lambda _: None) -> int:
    """Stage ``path`` (a file or folder; default: all of ``sources/``), enqueue it and run the queue.

    Progress lines go to ``emit``. Returns the number of items that failed.
    """
    for src in collect(vault, path or vault / "sources", emit):
        enqueue(vault, src, retry_failed=True)
    return drain(vault, process_item(vault), emit)
