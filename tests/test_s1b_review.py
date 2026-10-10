"""Regression tests for the S1b code-review findings."""

import json
import sqlite3
import threading
import time
from typing import TYPE_CHECKING

import keyring
import pytest
from click.testing import CliRunner, Result
from keyring.errors import KeyringError

from mindstew import adapter
from mindstew.adapter import ProviderError, ProviderUnreachableError
from mindstew.cli import cli
from mindstew.ingest import Analysis, GeneratedPage, GeneratedPages, IngestError, process_item
from mindstew.ingest_queue import (
    QueueItem,
    _connect,  # ruff: ignore[import-private-name]
    enqueue,
    list_items,
    mark_done,
    mark_failed,
    next_item,
    queue_db_path,
)
from mindstew.pages import list_pages
from mindstew.providers import (
    Header,
    Provider,
    Route,
    SecretStoreError,
    add_provider,
    get_secret,
    providers_path,
    set_route,
)
from mindstew.worker import Worker

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from tests.conftest import FakeAdapter

from tests.test_adapter import stub  # ruff: ignore[unused-import]


def _src(vault: Path, name: str = "a.md", text: str = "hello") -> Path:
    path = vault / "sources" / name
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture
def vault(make_vault: Callable[..., Path]) -> Path:
    """A vault with an ingest route."""
    root = make_vault()
    add_provider(Provider("p", "P", "openai", "http://x"))
    set_route("ingest", "p", "m")
    return root


def _ok(fake: FakeAdapter, title: str = "Alice", body: str = "Hi.") -> None:
    fake.respond(Analysis(summary="s"), GeneratedPages(pages=[GeneratedPage(type="entity", title=title, body=body)]))


def _ingest(*args: object) -> Result:
    return CliRunner().invoke(cli, ["ingest", *map(str, args)])


# 1. queue: changed file re-enqueued while running ---------------------------------------------------------------


def test_changed_file_reenqueued_while_running_is_not_lost(make_vault: Callable[..., Path]) -> None:
    """A changed file queued mid-run stays queued after the old attempt finishes."""
    vault = make_vault()
    src = _src(vault)
    enqueue(vault, src)
    item = next_item(vault)
    assert item
    src.write_text("changed", encoding="utf-8")
    assert enqueue(vault, src) is True
    mark_done(vault, item.id, item.sha256)
    assert list_items(vault)[0].status == "queued"
    again = next_item(vault)
    assert again
    assert again.sha256 != item.sha256
    mark_failed(vault, again.id, "x", again.sha256)
    assert (list_items(vault)[0].status, list_items(vault)[0].attempts) == ("queued", 1)


# 2. queue: only real corruption renames the db ---------------------------------------------------------------


def test_locked_database_is_not_treated_as_corrupt(make_vault: Callable[..., Path]) -> None:
    """A locked DB propagates the error and is never renamed."""
    vault = make_vault()
    enqueue(vault, _src(vault))
    blocker = sqlite3.connect(queue_db_path(vault), isolation_level=None)
    blocker.execute("BEGIN EXCLUSIVE")
    try:
        with pytest.raises(sqlite3.OperationalError):
            _connect(vault, timeout=0.1)
    finally:
        blocker.close()
    assert queue_db_path(vault).exists()
    assert not list(queue_db_path(vault).parent.glob("*.corrupt*"))


def test_corrupt_db_does_not_overwrite_earlier_corrupt_file(make_vault: Callable[..., Path]) -> None:
    """A second corruption keeps the first .corrupt file."""
    vault = make_vault()
    db = queue_db_path(vault)
    db.parent.mkdir(parents=True, exist_ok=True)
    for payload in (b"first garbage" * 50, b"second garbage" * 50):
        db.write_bytes(payload)
        assert list_items(vault) == []
        db.unlink()
    kept = sorted(p.read_bytes()[:5] for p in db.parent.glob("ingest.db.corrupt*"))
    assert kept == [b"first", b"secon"]


# 4. retry cap on outages ---------------------------------------------------------------------------------------


def test_explicit_retry_requeues_failed_item_with_same_hash(make_vault: Callable[..., Path]) -> None:
    """Failed items are only re-enqueued when asked."""
    vault = make_vault()
    src = _src(vault)
    enqueue(vault, src)
    for _ in range(3):
        item = next_item(vault)
        assert item
        mark_failed(vault, item.id, "down", item.sha256)
    assert list_items(vault)[0].status == "failed"
    assert enqueue(vault, src) is False
    assert enqueue(vault, src, retry_failed=True) is True
    row = list_items(vault)[0]
    assert (row.status, row.attempts) == ("queued", 0)


def test_cli_ingest_retries_a_failed_item(vault: Path, fake_adapter: FakeAdapter) -> None:
    """A second explicit ingest of a terminally failed, unchanged item runs it again."""
    _src(vault, "x.md", "x")
    fake_adapter.respond(*[ProviderUnreachableError("down")] * 3)
    assert _ingest(vault).exit_code != 0
    assert [i.status for i in list_items(vault)] == ["failed"]
    _ok(fake_adapter)
    result = _ingest(vault)
    assert result.exit_code == 0, result.output
    assert "nothing to ingest" not in result.output
    assert [i.status for i in list_items(vault)] == ["done"]


def test_worker_backs_off_between_outage_attempts(
    make_vault: Callable[..., Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Provider outages wait between attempts instead of burning the cap instantly."""
    monkeypatch.setattr("mindstew.worker.RETRY_DELAY", 0.2)
    vault = make_vault()
    enqueue(vault, _src(vault, "a.txt"))
    done = threading.Event()

    def down(item: QueueItem) -> None:
        raise ProviderUnreachableError("down")

    worker = Worker(vault, down, poll_interval=0.01)
    worker.subscribe(lambda e: done.set() if e.kind == "queue_drained" else None)
    start = time.monotonic()
    worker.start()
    assert done.wait(10)
    worker.stop()
    assert time.monotonic() - start >= 0.5  # 0.2 + 0.4 between the three attempts


# 3. reingest ---------------------------------------------------------------------------------------------------


def test_reingest_overwrites_only_its_own_item(vault: Path, fake_adapter: FakeAdapter) -> None:
    """Other queued items generate new pages instead of overwriting the reingested page."""
    _src(vault, "x.md", "x")
    _ok(fake_adapter, "Alice", "v1")
    assert _ingest(vault).exit_code == 0
    _src(vault, "y.md", "y")
    enqueue(vault, vault / "sources" / "y.md")
    _ok(fake_adapter, "Alice", "v2")
    _ok(fake_adapter, "Alice", "from-y")
    result = _ingest(vault, "--reingest", "entities/alice.md")
    assert result.exit_code == 0, result.output
    bodies = {p.path.name: p.body.strip() for p in list_pages(vault)}
    assert bodies["alice.md"] == "v2"
    assert "from-y" in bodies.values()


def test_reingest_without_title_match_leaves_page_alone(vault: Path, fake_adapter: FakeAdapter) -> None:
    """No same-type fallback: a differently titled page is added, not written over the target."""
    _src(vault, "x.md", "x")
    _ok(fake_adapter, "Alice", "v1")
    assert _ingest(vault).exit_code == 0
    _ok(fake_adapter, "Bob", "other")
    assert _ingest(vault, "--reingest", "entities/alice.md").exit_code == 0
    bodies = {p.path.name: p.body.strip() for p in list_pages(vault)}
    assert bodies["alice.md"] == "v1"
    assert bodies["bob.md"] == "other"


def test_reingest_rejects_bad_sources_before_enqueuing(vault: Path, tmp_path: Path) -> None:
    """Absolute or escaping sources[] entries abort the reingest with nothing enqueued."""
    outside = tmp_path / "outside.md"
    outside.write_text("secret", encoding="utf-8")
    good = _src(vault, "good.md")
    page = vault / "wiki" / "entities" / "evil.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(
        f"---\ntype: entity\ntitle: Evil\nsources:\n  - sources/good.md\n  - ../outside.md\n  - {outside}\n---\n\nb\n",
        encoding="utf-8",
    )
    result = _ingest(vault, "--reingest", "entities/evil.md")
    assert result.exit_code != 0
    assert list_items(vault) == []
    assert good.exists()


def test_overwritten_page_is_written_atomically(
    vault: Path, fake_adapter: FakeAdapter, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failure while replacing a page leaves the old page intact."""
    _src(vault, "x.md", "x")
    _ok(fake_adapter, "Alice", "v1")
    assert _ingest(vault).exit_code == 0
    page = vault / "wiki" / "entities" / "alice.md"

    def boom(*a: object, **k: object) -> None:
        raise OSError("disk")

    monkeypatch.setattr("os.replace", boom)
    item = _claim(vault, "x.md")
    _ok(fake_adapter, "Alice", "v2")
    with pytest.raises(OSError, match="disk"):
        process_item(vault, page, {item.path})(item)
    assert "v1" in page.read_text(encoding="utf-8")


def _claim(vault: Path, name: str) -> QueueItem:
    for row in list_items(vault):
        mark_done(vault, row.id)
    enqueue(vault, vault / "sources" / name, force=True)
    item = next_item(vault)
    assert item
    return item


# 5. rollback ---------------------------------------------------------------------------------------------------


def test_failed_write_rolls_back_earlier_pages(
    vault: Path, fake_adapter: FakeAdapter, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If a later page cannot be written, earlier ones from the same call are removed."""
    from mindstew import ingest as ingest_mod

    real = ingest_mod.new_page_path
    calls = []

    def flaky(v: Path, type_: str, title: str) -> Path:
        calls.append(title)
        if len(calls) == 2:
            raise OSError("full")
        return real(v, type_, title)

    monkeypatch.setattr(ingest_mod, "new_page_path", flaky)
    _src(vault, "x.md", "x")
    fake_adapter.respond(
        Analysis(summary="s"),
        GeneratedPages(pages=[GeneratedPage(type="entity", title="A"), GeneratedPage(type="entity", title="B")]),
    )
    item = _claim(vault, "x.md")
    with pytest.raises(OSError, match="full"):
        process_item(vault)(item)
    assert list_pages(vault) == []


# 8. route notices ----------------------------------------------------------------------------------------------


def test_no_route_error_includes_notices(make_vault: Callable[..., Path], fake_adapter: FakeAdapter) -> None:
    """The IngestError explains why a configured route was ignored."""
    root = make_vault()
    (root / ".mindstew" / "config.yaml").write_text(
        "routes:\n  ingest: {provider: ghost, model: m}\n", encoding="utf-8"
    )
    _src(root, "x.md")
    enqueue(root, root / "sources" / "x.md")
    item = next_item(root)
    assert item
    with pytest.raises(IngestError, match="ghost"):
        process_item(root)(item)


# 6. providers --------------------------------------------------------------------------------------------------


def _fail_replace(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*a: object, **k: object) -> None:
        raise OSError("disk")

    monkeypatch.setattr("os.replace", boom)


def test_providers_json_written_atomically(monkeypatch: pytest.MonkeyPatch) -> None:
    """A failed replace leaves the previous providers.json untouched."""
    add_provider(Provider("p", "P", "k", "http://a"))
    before = providers_path().read_text(encoding="utf-8")
    _fail_replace(monkeypatch)
    with pytest.raises(OSError, match="disk"):
        add_provider(Provider("q", "Q", "k", "http://b"))
    assert providers_path().read_text(encoding="utf-8") == before


def test_vault_config_written_atomically(make_vault: Callable[..., Path], monkeypatch: pytest.MonkeyPatch) -> None:
    """A failed replace leaves the vault config untouched."""
    root = make_vault()
    add_provider(Provider("p", "P", "k", "http://a"))
    cfg = root / ".mindstew" / "config.yaml"
    before = cfg.read_text(encoding="utf-8") if cfg.exists() else None
    _fail_replace(monkeypatch)
    with pytest.raises(OSError, match="disk"):
        set_route("chat", "p", "m", root)
    assert (cfg.read_text(encoding="utf-8") if cfg.exists() else None) == before


def test_add_provider_refuses_corrupt_registry() -> None:
    """A corrupt providers.json is not silently overwritten."""
    path = providers_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not json", encoding="utf-8")
    with pytest.raises(ValueError, match="unreadable"):
        add_provider(Provider("p", "P", "k", "http://a"))
    assert path.read_text(encoding="utf-8") == "not json"


def test_set_route_vault_refuses_corrupt_config(make_vault: Callable[..., Path]) -> None:
    """A corrupt vault config.yaml is not silently overwritten."""
    root = make_vault()
    add_provider(Provider("p", "P", "k", "http://a"))
    cfg = root / ".mindstew" / "config.yaml"
    cfg.write_text("routes: [unclosed", encoding="utf-8")
    with pytest.raises(ValueError, match="unreadable"):
        set_route("chat", "p", "m", root)
    assert cfg.read_text(encoding="utf-8") == "routes: [unclosed"


def test_keyring_failure_surfaces_as_typed_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """get_secret raises instead of returning None; the adapter reports a ProviderError."""

    def boom(*a: object) -> str:
        raise KeyringError("locked")

    monkeypatch.setattr(keyring, "get_password", boom)
    with pytest.raises(SecretStoreError):
        get_secret("p", "api_key")
    route = Route("chat", Provider("p", "P", "k", "http://127.0.0.1:1"), "m")
    with pytest.raises(ProviderError, match=r"keyring"):
        adapter.ping(route)


def test_secrets_stored_before_registry_saved(monkeypatch: pytest.MonkeyPatch) -> None:
    """If the keyring write fails, no registry entry is left behind."""

    def boom(*a: object) -> None:
        raise KeyringError("locked")

    monkeypatch.setattr(keyring, "set_password", boom)
    with pytest.raises(KeyringError):
        add_provider(Provider("p", "P", "k", "http://a"), api_key="k")  # pragma: allowlist secret
    assert not providers_path().exists()


def test_readd_deletes_orphaned_header_secrets(fake_keyring: dict) -> None:
    """Dropping a secret header on re-add removes its Keychain item."""
    add_provider(Provider("p", "P", "k", "http://a", [Header("X", None, True)]), header_secrets={"X": "t"})
    assert ("mindstew", "p/header/X") in fake_keyring
    add_provider(Provider("p", "P", "k", "http://a"))
    assert ("mindstew", "p/header/X") not in fake_keyring


def test_provider_error_has_no_response_body(stub) -> None:  # ruff: ignore[redefined-while-unused]
    """HTTP errors report status and reason only."""
    stub.status = 500
    provider = Provider("local", "L", "k", stub.url)
    add_provider(provider, api_key="sk-good")  # pragma: allowlist secret
    with pytest.raises(ProviderError) as exc:
        adapter.ping(Route("chat", provider, "m"))
    assert "500" in str(exc.value)
    assert "data" not in str(exc.value)


# 7. strict schema ----------------------------------------------------------------------------------------------


def _check_strict(node: object) -> None:
    if isinstance(node, dict):
        if "properties" in node:
            assert node["additionalProperties"] is False
            assert node["required"] == list(node["properties"])
        for v in node.values():
            _check_strict(v)
    elif isinstance(node, list):
        for v in node:
            _check_strict(v)


@pytest.mark.parametrize("model", [Analysis, GeneratedPages])
def test_request_schema_is_openai_strict(stub, model: type) -> None:  # ruff: ignore[redefined-while-unused]
    """Every object in the sent schema forbids extra keys and requires all properties."""
    provider = Provider("local", "L", "k", stub.url)
    add_provider(provider, api_key="sk-good")  # pragma: allowlist secret
    stub.content = json.dumps({"summary": "s", "planned_pages": []} if model is Analysis else {"pages": []})
    adapter.complete(Route("chat", provider, "m"), [{"role": "user", "content": "x"}], model)
    schema = stub.requests[0]["body"]["response_format"]["json_schema"]["schema"]
    assert schema["required"]
    _check_strict(schema)
