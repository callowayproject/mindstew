"""Two-step text ingest."""

import logging
from typing import TYPE_CHECKING

import pytest

from mindstew import adapter
from mindstew import ingest as ingest_mod
from mindstew.ingest import Analysis, GeneratedPage, GeneratedPages, IngestError, process_item
from mindstew.ingest_queue import QueueItem, enqueue, list_items, mark_done, next_item
from mindstew.pages import list_pages
from mindstew.providers import Provider, add_provider, set_route

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from mindstew.pages import Page
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


def test_empty_and_config_pages_skipped_valid_written(
    vault: Path, fake_adapter: FakeAdapter, caplog: pytest.LogCaptureFixture
) -> None:
    """Empty/whitespace-body and schema/purpose-titled pages are skipped and logged; the rest is written."""
    pages = [_page(title="E", body=""), _page(title="W", body=" \n"), _page(title="Schema"), _page(title="purpose.md")]
    fake_adapter.respond(Analysis(summary="s"), GeneratedPages(pages=[*pages, _page(title="Good")]))
    with caplog.at_level("WARNING"):
        process_item(vault)(_item(vault))
    assert [p.title for p in list_pages(vault)] == ["Good"]
    assert caplog.text.count("skipping page") == 4


def test_sources_normalized(vault: Path, fake_adapter: FakeAdapter) -> None:
    """``source:`` prefixes collapse into ``sources/<file>``, duplicates and unresolvable entries are dropped."""
    (vault / "sources" / "a.md").write_text("a", encoding="utf-8")
    (vault / "outside.md").write_text("x", encoding="utf-8")
    page = _page(sources=["sources/a.md", "source:a.md", "source:ghost.md", "source:../outside.md", "sources/note.md"])
    fake_adapter.respond(Analysis(summary="s"), GeneratedPages(pages=[page]))
    process_item(vault)(_item(vault))
    assert list_pages(vault)[0].sources == ["sources/note.md", "sources/a.md"]


@pytest.mark.parametrize("bad", [None, "sources/note.md", {"a": 1}, [None, 3]])
def test_malformed_sources_tolerated(vault: Path, fake_adapter: FakeAdapter, bad: object) -> None:
    """A null, scalar or non-list ``sources`` from the model does not crash ingest."""
    page = GeneratedPage.model_validate({"type": "entity", "title": "A", "body": "b", "sources": bad})
    fake_adapter.respond(Analysis(summary="s"), GeneratedPages(pages=[page]))
    process_item(vault)(_item(vault))
    assert list_pages(vault)[0].sources == ["sources/note.md"]


def test_step2_prompt_has_guards(vault: Path, fake_adapter: FakeAdapter) -> None:
    """The step-2 system prompt carries the empty-body, config and title-fidelity instructions."""
    fake_adapter.respond(Analysis(summary="s"), GeneratedPages(pages=[_page()]))
    process_item(vault)(_item(vault))
    system = fake_adapter.calls[1][1][0]["content"]
    for phrase in ("empty bodies", "schema.md and purpose.md", "exactly as written"):
        assert phrase in system


def test_log_unresolved_lists_vault_once_and_skips_outside_paths(
    make_vault: Callable[..., Path], monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, tmp_path: Path
) -> None:
    """Logging unresolved links costs one vault listing per ingest, and a path outside ``wiki/`` is skipped."""
    vault = make_vault()
    written = []
    for name in ("a", "b"):
        page = vault / "wiki" / "entities" / f"{name}.md"
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text("---\ntype: entity\ntitle: T\n---\nsee [[Ghost]]\n", encoding="utf-8")
        written.append(page)
    outside = tmp_path / "elsewhere.md"
    outside.write_text("x", encoding="utf-8")
    calls: list[int] = []
    real = ingest_mod.list_pages

    def counting(v: Path) -> list[Page]:
        calls.append(1)
        return real(v)

    monkeypatch.setattr(ingest_mod, "list_pages", counting)
    with caplog.at_level(logging.INFO, logger="mindstew.ingest"):
        ingest_mod._log_unresolved(vault, [*written, outside])
    assert len(calls) == 1
    assert caplog.text.count("unresolved link [[Ghost]]") == 2
