"""A Qt-free background worker that drains the ingest queue through a pluggable ``process(item)`` callable.

Events (``item_started``, ``item_finished``, ``item_failed``, ``queue_drained``) go to subscribers, which are
called on the worker thread; a GUI must marshal them to its own thread. Subscriber exceptions are swallowed.
"""

import logging
import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING

from mindstew.adapter import ProviderAuthError, ProviderUnreachableError
from mindstew.ingest_queue import mark_done, mark_failed, next_item, recover_running

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from mindstew.ingest_queue import QueueItem

logger = logging.getLogger(__name__)

RETRY_DELAY = 2.0  # seconds, times the attempt number, after a provider outage/auth failure (tests set 0)
_OUTAGE_ERRORS = (ProviderUnreachableError, ProviderAuthError)


@dataclass(frozen=True)
class Event:
    """A worker event. ``item_id``/``path`` are None for ``queue_drained``; ``error`` is set on ``item_failed``."""

    kind: str
    item_id: int | None = None
    path: Path | None = None
    error: str | None = None


class Worker:
    """Process queued items strictly one at a time, in enqueue order, on a daemon thread."""

    def __init__(self, vault: Path, process: Callable[[QueueItem], None], poll_interval: float = 0.5) -> None:
        self.vault = vault
        self.process = process
        self.poll_interval = poll_interval
        self._subscribers: list[Callable[[Event], None]] = []
        self._stop = threading.Event()
        self._cancelled = threading.Event()
        self._thread = threading.Thread(target=self._run, name="mindstew-ingest", daemon=True)

    def subscribe(self, callback: Callable[[Event], None]) -> None:
        """Register ``callback`` to receive every event."""
        self._subscribers.append(callback)

    def start(self) -> None:
        """Recover items left running by an interrupted session, then start the thread."""
        recover_running(self.vault)
        self._thread.start()

    def stop(self) -> None:
        """Finish the current item (if any), then exit; blocks until the thread is done."""
        self._stop.set()
        self.join()

    def cancel(self) -> None:
        """Ask the worker to exit without waiting; the in-flight item's result is abandoned and stays ``running``.

        The next session's ``start`` re-queues it.
        """
        self._cancelled.set()
        self._stop.set()

    def join(self, timeout: float | None = None) -> None:
        """Wait for the worker thread to exit."""
        self._thread.join(timeout)

    def _emit(self, event: Event) -> None:
        for callback in list(self._subscribers):
            try:
                callback(event)
            except Exception:
                logger.exception("worker subscriber failed")

    def _run(self) -> None:
        busy = False
        while not self._stop.is_set():
            item = next_item(self.vault)
            if item is None:
                if busy:
                    busy = False
                    self._emit(Event("queue_drained"))
                self._stop.wait(self.poll_interval)
                continue
            busy = True
            self._emit(Event("item_started", item.id, item.path))
            try:
                self.process(item)
            except Exception as exc:  # ruff: ignore[blind-except] any process failure drives the retry cap
                if self._cancelled.is_set():
                    return
                mark_failed(self.vault, item.id, str(exc), item.sha256)
                self._emit(Event("item_failed", item.id, item.path, str(exc)))
                if isinstance(exc, _OUTAGE_ERRORS):  # back off so an outage does not burn the retry cap at once
                    self._stop.wait(RETRY_DELAY * (item.attempts + 1))
            else:
                if self._cancelled.is_set():
                    return
                mark_done(self.vault, item.id, item.sha256)
                self._emit(Event("item_finished", item.id, item.path))
