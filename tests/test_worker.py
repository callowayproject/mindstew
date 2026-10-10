"""The background ingest worker and the status command."""

import threading
from typing import TYPE_CHECKING

from click.testing import CliRunner

from mindstew.cli import cli
from mindstew.ingest_queue import QueueItem, enqueue, list_items, next_item
from mindstew.worker import Event, Worker

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


def _source(vault: Path, name: str, text: str = "x") -> Path:
    path = vault / "sources" / name
    path.write_text(text or name, encoding="utf-8")
    return path


def _run(vault: Path, process: Callable[[QueueItem], None]) -> list[Event]:
    """Run a worker until the queue drains; return the events seen."""
    events: list[Event] = []
    drained = threading.Event()

    def listener(event: Event) -> None:
        events.append(event)
        if event.kind == "queue_drained":
            drained.set()

    worker = Worker(vault, process, poll_interval=0.01)
    worker.subscribe(listener)
    worker.start()
    assert drained.wait(10)
    worker.stop()
    return events


def test_processes_in_order_one_at_a_time_with_events(make_vault: Callable[..., Path]) -> None:
    """Processes in order one at a time with events."""
    vault = make_vault()
    a, b = _source(vault, "a.txt", "a"), _source(vault, "b.txt", "b")
    enqueue(vault, a)
    enqueue(vault, b)
    active = 0
    overlap = False
    seen: list[Path] = []

    def process(item: QueueItem) -> None:
        nonlocal active, overlap
        active += 1
        overlap = overlap or active > 1
        seen.append(item.path)
        active -= 1

    events = _run(vault, process)
    assert seen == [a.resolve(), b.resolve()]
    assert not overlap
    assert [(e.kind, e.path) for e in events] == [
        ("item_started", a.resolve()),
        ("item_finished", a.resolve()),
        ("item_started", b.resolve()),
        ("item_finished", b.resolve()),
        ("queue_drained", None),
    ]
    assert {i.status for i in list_items(vault)} == {"done"}


def test_subscriber_exception_does_not_kill_worker(make_vault: Callable[..., Path]) -> None:
    """Subscriber exception does not kill worker."""
    vault = make_vault()
    enqueue(vault, _source(vault, "a.txt"))
    done = threading.Event()
    worker = Worker(vault, lambda item: None, poll_interval=0.01)

    def boom(event: Event) -> None:
        raise RuntimeError("bad subscriber")

    worker.subscribe(boom)
    worker.subscribe(lambda e: done.set() if e.kind == "queue_drained" else None)
    worker.start()
    assert done.wait(10)
    worker.stop()
    assert list_items(vault)[0].status == "done"


def test_raising_process_retries_then_fails(make_vault: Callable[..., Path]) -> None:
    """Raising process retries then fails."""
    vault = make_vault()
    enqueue(vault, _source(vault, "a.txt"))

    def process(item: QueueItem) -> None:
        raise ValueError("nope")

    events = _run(vault, process)
    failures = [e for e in events if e.kind == "item_failed"]
    assert len(failures) == 3
    assert failures[0].error == "nope"
    (item,) = list_items(vault)
    assert (item.status, item.attempts, item.error) == ("failed", 3, "nope")


def test_stop_mid_item_leaves_it_recoverable(make_vault: Callable[..., Path]) -> None:
    """Stop mid item leaves it recoverable."""
    vault = make_vault()
    enqueue(vault, _source(vault, "a.txt"))
    started, release = threading.Event(), threading.Event()

    def block(item: QueueItem) -> None:
        started.set()
        release.wait(10)

    worker = Worker(vault, block, poll_interval=0.01)
    worker.start()
    assert started.wait(10)
    worker.cancel()  # abandon without waiting for the item
    assert list_items(vault)[0].status == "running"
    release.set()
    worker.join()
    assert list_items(vault)[0].status == "running"  # cancelled result is abandoned
    # A new session recovers it and processes it again.
    assert next_item(vault) is None
    events = _run(vault, lambda item: None)
    assert [e.kind for e in events] == ["item_started", "item_finished", "queue_drained"]


def test_status_command(make_vault: Callable[..., Path]) -> None:
    """Status command."""
    vault = make_vault()
    enqueue(vault, _source(vault, "a.txt", "a"))
    enqueue(vault, _source(vault, "b.txt", "b"))
    _run(vault, lambda item: (_ for _ in ()).throw(ValueError("bad")) if item.path.name == "b.txt" else None)
    out = CliRunner().invoke(cli, ["status", str(vault)]).output
    assert "queued: 0  running: 0  done: 1  failed: 1" in out
    assert "failed\tb.txt\tbad" in out
    assert "done\ta.txt" in out
