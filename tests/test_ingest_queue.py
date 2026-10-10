"""The persistent serial ingest queue."""

import shutil
from typing import TYPE_CHECKING

from mindstew.ingest_queue import enqueue, mark_done, mark_failed, next_item, queue_db_path, recover_running

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


def _source(vault: Path, name: str = "a.txt", text: str = "hello") -> Path:
    path = vault / "sources" / name
    path.write_text(text, encoding="utf-8")
    return path


def test_enqueue_then_next_item_runs_one_at_a_time(make_vault: Callable[..., Path]) -> None:
    """Enqueue then next item runs one at a time."""
    vault = make_vault()
    a, b = _source(vault, "a.txt"), _source(vault, "b.txt", "other")
    assert enqueue(vault, a) is True
    assert enqueue(vault, b) is True
    first = next_item(vault)
    assert first is not None
    assert first.path == a.resolve()
    assert next_item(vault) is None  # first still running
    mark_done(vault, first.id)
    second = next_item(vault)
    assert second is not None
    assert second.path == b.resolve()


def test_next_item_on_empty_queue(make_vault: Callable[..., Path]) -> None:
    """Next item on empty queue."""
    assert next_item(make_vault()) is None


def test_restart_resumes_running_item(make_vault: Callable[..., Path]) -> None:
    """Restart resumes running item."""
    vault = make_vault()
    enqueue(vault, _source(vault))
    item = next_item(vault)
    assert item is not None
    assert next_item(vault) is None
    assert recover_running(vault) == 1  # "restart": a fresh connection finds the item still running
    again = next_item(vault)
    assert again is not None
    assert again.id == item.id


def test_third_failure_is_terminal(make_vault: Callable[..., Path]) -> None:
    """Third failure is terminal."""
    vault = make_vault()
    path = _source(vault)
    enqueue(vault, path)
    for _ in range(3):
        item = next_item(vault)
        assert item is not None
        mark_failed(vault, item.id, "boom")
    assert next_item(vault) is None
    assert enqueue(vault, path) is False  # same content: never retried


def test_failure_below_cap_requeues(make_vault: Callable[..., Path]) -> None:
    """Failure below cap requeues."""
    vault = make_vault()
    enqueue(vault, _source(vault))
    item = next_item(vault)
    assert item is not None
    mark_failed(vault, item.id, "boom")
    retry = next_item(vault)
    assert retry is not None
    assert retry.attempts == 1


def test_unchanged_file_skipped_changed_requeued(make_vault: Callable[..., Path]) -> None:
    """Unchanged file skipped changed requeued."""
    vault = make_vault()
    path = _source(vault)
    enqueue(vault, path)
    item = next_item(vault)
    assert item is not None
    mark_done(vault, item.id)
    assert enqueue(vault, path) is False
    _source(vault, text="changed")
    assert enqueue(vault, path) is True
    again = next_item(vault)
    assert again is not None
    assert again.attempts == 0


def test_enqueue_already_queued_is_noop(make_vault: Callable[..., Path]) -> None:
    """Enqueue already queued is noop."""
    vault = make_vault()
    path = _source(vault)
    assert enqueue(vault, path) is True
    assert enqueue(vault, path) is False


def test_deleting_index_dir_starts_empty(make_vault: Callable[..., Path]) -> None:
    """Deleting index dir starts empty."""
    vault = make_vault()
    enqueue(vault, _source(vault))
    shutil.rmtree(vault / ".mindstew" / "index")
    assert next_item(vault) is None
    assert queue_db_path(vault).exists()


def test_corrupt_db_does_not_crash(make_vault: Callable[..., Path]) -> None:
    """Corrupt db does not crash."""
    vault = make_vault()
    queue_db_path(vault).write_bytes(b"this is not a sqlite database" * 100)
    assert next_item(vault) is None
    assert enqueue(vault, _source(vault)) is True
    assert next_item(vault) is not None
