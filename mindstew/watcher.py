"""Watch a folder: settle, stage into ``sources/``, enqueue and ingest. Click-free; a GUI can start and stop it."""

from __future__ import annotations

import queue
import shutil
import threading
from pathlib import Path
from typing import TYPE_CHECKING

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from mindstew.ingest import CONFIG_FILES, TEXT_SUFFIXES, process_item
from mindstew.ingest_queue import enqueue
from mindstew.worker import Event, Worker

if TYPE_CHECKING:
    from collections.abc import Callable

    from mindstew.ingest_queue import QueueItem


def stage(
    sources: Path, base: Path, path: Path, emit: Callable[[str], None], *, overwrite: bool = False
) -> Path | None:
    """Return the ``sources/`` path for ``path`` (under ``base``), copying it in if needed; None if skipped.

    Hidden files are skipped silently, unsupported ones are reported and skipped, and a clashing different file
    already in ``sources/`` is kept and reported unless ``overwrite`` (then it is replaced).
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


def show_event(emit: Callable[[str], None]) -> Callable[[Event], None]:
    """Return a worker subscriber that renders events as one-line messages for ``emit``."""

    def show(e: Event) -> None:
        if e.kind != "queue_drained":
            emit(
                f"{e.kind.removeprefix('item_')}: {e.path.name if e.path else ''}"
                + (f" ({e.error})" if e.error else "")
            )

    return show


class _Collector(FileSystemEventHandler):
    """Collect the paths of created, modified and moved-in files."""

    def __init__(self) -> None:
        self.paths: queue.SimpleQueue[Path] = queue.SimpleQueue()

    def on_any_event(self, event: FileSystemEvent) -> None:
        """Record the file an event touched (the destination for moves)."""
        if event.event_type in ("created", "modified", "moved") and not event.is_directory:
            self.paths.put(Path(str(getattr(event, "dest_path", "") or event.src_path)))


def watch_vault(
    vault: Path,
    folder: Path | None,
    stop: threading.Event,
    *,
    emit: Callable[[str], None],
    process: Callable[[QueueItem], None] | None = None,
    settle: float = 0.5,
) -> None:
    """Watch ``folder`` (default ``vault/sources``), enqueue new/changed text files and ingest them until ``stop``.

    Files from ``folder`` are copied into ``sources/``. A file is enqueued once its size is unchanged across a
    ``settle`` interval, so partial writes are not ingested. Existing files are scanned at start (the queue skips
    unchanged ones). On stop the in-flight item is abandoned and stays ``running``; the next worker start recovers it.
    """
    sources = (vault / "sources").resolve()
    root = (folder or sources).resolve()
    collector = _Collector()
    observer = Observer()
    observer.schedule(collector, str(root), recursive=True)
    observer.start()
    worker = Worker(vault, process or process_item(vault), poll_interval=0.05)
    worker.subscribe(show_event(emit))
    worker.start()
    sizes = {p.resolve(): -1 for p in root.rglob("*") if p.is_file()}
    try:
        while not stop.wait(settle):
            while not collector.paths.empty():
                sizes[collector.paths.get().resolve()] = -1
            for path, last in list(sizes.items()):
                try:
                    size = path.stat().st_size
                except OSError:
                    del sizes[path]
                    continue
                if size != last:
                    sizes[path] = size
                    continue
                del sizes[path]
                dest = stage(sources, root, path, emit, overwrite=True) if path.is_relative_to(root) else None
                if dest and enqueue(vault, dest):
                    emit(f"queued: {dest.name}")
    finally:
        observer.stop()
        worker.cancel()
        observer.join()


class Watcher:
    """A startable, stoppable watch of ``folder`` (default ``vault/sources``); runs on its own thread."""

    def __init__(
        self,
        vault: Path,
        folder: Path | None = None,
        *,
        emit: Callable[[str], None],
        process: Callable[[QueueItem], None] | None = None,
        settle: float = 0.5,
    ) -> None:
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=watch_vault,
            args=(vault, folder, self._stop),
            kwargs={"emit": emit, "process": process, "settle": settle},
            daemon=True,
        )

    def start(self) -> None:
        """Begin watching."""
        self._thread.start()

    def stop(self) -> None:
        """Stop watching and wait for shutdown; the in-flight item stays ``running`` for recovery. Idempotent."""
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join()
