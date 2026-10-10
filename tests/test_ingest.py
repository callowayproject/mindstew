"""Two-step text ingest."""

from typing import TYPE_CHECKING

import pytest

from mindstew import adapter
from mindstew.ingest import Analysis, GeneratedPage, GeneratedPages, IngestError, process_item
from mindstew.ingest_queue import QueueItem, enqueue, list_items, mark_done, next_item
from mindstew.pages import list_pages
from mindstew.providers import Provider, add_provider, set_route

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from tests.conftest import FakeAdapter


@pytest.fixture
def vault(make_vault: Callable[..., Path]) -> Path:
    """Ingest behaviour."""
    root = make_vault()
    add_provider(Provider("p", "P", "openai", "http://x"))
    set_route("ingest", "p", "m")
    return root


def _item(vault: Path, text: str = "Alice met Bob.", name: str = "note.md") -> QueueItem:
    """Queue a source and claim it (the queue is serial, so finish anything an earlier call left running)."""
    for row in list_items(vault):
        mark_done(vault, row.id)
    (vault / "sources" / name).write_text(text, encoding="utf-8")
    enqueue(vault, vault / "sources" / name)
    item = next_item(vault)
    assert item
    return item


def _page(**kw: object) -> GeneratedPage:
    return GeneratedPage(**{"type": "entity", "title": "Alice", "tags": ["people"], "body": "See [[Bob]].", **kw})


def test_writes_pages_with_frontmatter(vault: Path, fake_adapter: FakeAdapter) -> None:
    """Ingest behaviour."""
    fake_adapter.respond(
        Analysis(summary="two people"),
        GeneratedPages(pages=[_page(), _page(title="Bob", body="Knows [[Alice]].")]),
    )
    process_item(vault)(_item(vault))
    pages = {p.title: p for p in list_pages(vault)}
    assert set(pages) == {"Alice", "Bob"}
    assert pages["Alice"].type == "entity"
    assert pages["Alice"].sources == ["sources/note.md"]
    assert pages["Alice"].tags == ["people"]
    assert "[[Bob]]" in pages["Alice"].body
    assert pages["Alice"].path.parent == vault / "wiki" / "entities"
    assert [c[2] for c in fake_adapter.calls] == [Analysis, GeneratedPages]
    assert "Alice met Bob." in fake_adapter.calls[0][1][-1]["content"]


def test_collision_gets_number_and_existing_untouched(vault: Path, fake_adapter: FakeAdapter) -> None:
    """Ingest behaviour."""
    existing = vault / "wiki" / "entities" / "alice.md"
    existing.write_text("mine", encoding="utf-8")
    fake_adapter.respond(Analysis(summary="s"), GeneratedPages(pages=[_page(), _page()]))
    process_item(vault)(_item(vault))
    assert existing.read_text(encoding="utf-8") == "mine"
    assert (vault / "wiki" / "entities" / "alice-2.md").exists()
    assert (vault / "wiki" / "entities" / "alice-3.md").exists()


def test_unknown_type_fails_without_partial_writes(vault: Path, fake_adapter: FakeAdapter) -> None:
    """Ingest behaviour."""
    fake_adapter.respond(Analysis(summary="s"), GeneratedPages(pages=[_page(), _page(type="bogus")]))
    with pytest.raises(IngestError):
        process_item(vault)(_item(vault))
    assert list_pages(vault) == []


def test_empty_title_and_bad_source_fail(vault: Path, fake_adapter: FakeAdapter) -> None:
    """Ingest behaviour."""
    for i, bad in enumerate((_page(title="  "), _page(sources=["../etc/passwd"]), _page(sources=["/abs"]))):
        fake_adapter.respond(Analysis(summary="s"), GeneratedPages(pages=[bad]))
        with pytest.raises(IngestError):
            process_item(vault)(_item(vault, name=f"n{i}.md"))
    assert list_pages(vault) == []


def test_no_route_raises(make_vault: Callable[..., Path], fake_adapter: FakeAdapter) -> None:
    """Ingest behaviour."""
    root = make_vault()
    with pytest.raises(IngestError, match="ingest"):
        process_item(root)(_item(root))
    assert fake_adapter.calls == []


def test_adapter_error_propagates(vault: Path, fake_adapter: FakeAdapter) -> None:
    """Ingest behaviour."""
    fake_adapter.respond(adapter.InvalidModelOutputError("bad"))
    with pytest.raises(adapter.InvalidModelOutputError):
        process_item(vault)(_item(vault))


def test_unsupported_extension_and_binary_fail(vault: Path, fake_adapter: FakeAdapter) -> None:
    """Ingest behaviour."""
    with pytest.raises(IngestError):
        process_item(vault)(_item(vault, name="a.pdf"))
    (vault / "sources" / "b.txt").write_bytes(b"\xff\xfe\x00bad")
    for row in list_items(vault):
        mark_done(vault, row.id)
    enqueue(vault, vault / "sources" / "b.txt")
    item = next_item(vault)
    assert item
    with pytest.raises(IngestError):
        process_item(vault)(item)
    assert fake_adapter.calls == []
