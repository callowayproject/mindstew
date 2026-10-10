"""The ``watch`` loop, driven against temp dirs with the fake adapter (no providers, no signals)."""

import threading
import time
from typing import TYPE_CHECKING

import pytest

from mindstew.cli import watch_vault
from mindstew.ingest import Analysis, GeneratedPage, GeneratedPages
from mindstew.ingest_queue import list_items, recover_running
from mindstew.pages import list_pages
from mindstew.providers import Provider, add_provider, set_route

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from pathlib import Path

    from tests.conftest import FakeAdapter


@pytest.fixture
def vault(make_vault: Callable[..., Path]) -> Path:
    """A vault with an ingest route."""
    root = make_vault()
    add_provider(Provider("p", "P", "openai", "http://x"))
    set_route("ingest", "p", "m")
    return root


class Watcher:
    """Run ``watch_vault`` on a thread, collecting its output lines."""

    def __init__(self, vault: Path, folder: Path | None = None, process: Callable | None = None) -> None:
        self.lines: list[str] = []
        self.stop = threading.Event()
        kwargs = {"process": process} if process else {}
        self.thread = threading.Thread(
            target=watch_vault,
            args=(vault, folder, self.stop),
            kwargs={"emit": self.lines.append, "settle": 0.05, **kwargs},
            daemon=True,
        )
        self.thread.start()

    def wait_for(self, cond: Callable[[], bool], timeout: float = 10) -> None:
        """Poll until ``cond()`` or fail."""
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if cond():
                return
            time.sleep(0.02)
        pytest.fail(f"timed out; output so far: {self.lines}")


@pytest.fixture
def start() -> Iterator[Callable[..., Watcher]]:
    """Factory for watchers that are always stopped at teardown."""
    made: list[Watcher] = []

    def _start(*args: object, **kwargs: object) -> Watcher:
        w = Watcher(*args, **kwargs)  # type: ignore[arg-type]
        made.append(w)
        return w

    yield _start
    for w in made:
        w.stop.set()
        w.thread.join(5)


def _ok(fake: FakeAdapter, title: str) -> None:
    fake.respond(Analysis(summary="s"), GeneratedPages(pages=[GeneratedPage(type="entity", title=title, body="b")]))


def test_new_file_in_sources_is_ingested_once_and_junk_ignored(
    vault: Path, fake_adapter: FakeAdapter, start: Callable[..., Watcher]
) -> None:
    """A supported file is ingested; hidden and unsupported files are never queued."""
    _ok(fake_adapter, "Alice")
    w = start(vault)
    (vault / "sources" / ".hidden.md").write_text("x", encoding="utf-8")
    (vault / "sources" / "pic.png").write_bytes(b"x")
    (vault / "sources" / "note.md").write_text("Alice.", encoding="utf-8")
    w.wait_for(lambda: [i.status for i in list_items(vault)] == ["done"])
    assert [i.path.name for i in list_items(vault)] == ["note.md"]
    assert [p.title for p in list_pages(vault)] == ["Alice"]
    assert any("note.md" in line for line in w.lines)


def test_modified_file_is_requeued(vault: Path, fake_adapter: FakeAdapter, start: Callable[..., Watcher]) -> None:
    """Changed content is ingested again; the same event twice is not."""
    _ok(fake_adapter, "One")
    _ok(fake_adapter, "Two")
    w = start(vault)
    note = vault / "sources" / "note.md"
    note.write_text("v1", encoding="utf-8")
    w.wait_for(lambda: len(fake_adapter.calls) == 2)
    note.write_text("v2", encoding="utf-8")
    w.wait_for(lambda: len(fake_adapter.calls) == 4)
    w.wait_for(lambda: [i.status for i in list_items(vault)] == ["done"])
    assert len(fake_adapter.calls) == 4


def test_folder_files_are_copied_into_sources(
    vault: Path, tmp_path: Path, fake_adapter: FakeAdapter, start: Callable[..., Watcher]
) -> None:
    """Files appearing in FOLDER (including existing ones) are staged into sources/ and ingested."""
    folder = tmp_path / "inbox"
    folder.mkdir()
    (folder / "old.md").write_text("old", encoding="utf-8")
    _ok(fake_adapter, "Old")
    _ok(fake_adapter, "New")
    w = start(vault, folder)
    (folder / "new.txt").write_text("new", encoding="utf-8")
    w.wait_for(lambda: len([i for i in list_items(vault) if i.status == "done"]) == 2)
    assert (vault / "sources" / "old.md").read_text(encoding="utf-8") == "old"
    assert (vault / "sources" / "new.txt").read_text(encoding="utf-8") == "new"


def test_stop_leaves_running_item_recoverable(vault: Path, start: Callable[..., Watcher]) -> None:
    """Stopping mid-item returns promptly and leaves the item running, which the next session recovers."""
    started, release = threading.Event(), threading.Event()

    def blocking(_item: object) -> None:
        started.set()
        release.wait(10)

    w = start(vault, process=blocking)
    (vault / "sources" / "note.md").write_text("x", encoding="utf-8")
    w.wait_for(started.is_set)
    w.stop.set()
    w.thread.join(5)
    assert not w.thread.is_alive()
    assert [i.status for i in list_items(vault)] == ["running"]
    release.set()
    assert recover_running(vault) == 1
