"""Watch a folder: settle, stage into ``sources/``, enqueue and ingest. Click-free; a GUI can start and stop it."""

from __future__ import annotations

import queue
import threading
from pathlib import Path
from typing import TYPE_CHECKING

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from mindstew.ingest import process_item, show_event, stage
from mindstew.ingest_queue import enqueue
from mindstew.worker import Worker

if TYPE_CHECKING:
    from collections.abc import Callable

    from mindstew.ingest_queue import QueueItem


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
                dest = stage(sources, root, path, overwrite=True, emit=emit) if path.is_relative_to(root) else None
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
