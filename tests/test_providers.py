"""Tests for the provider registry, routes and Keychain-backed secrets."""

import json
from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner

from mindstew.cli import cli
from mindstew.providers import (
    Header,
    Provider,
    add_provider,
    get_secret,
    load_registry,
    providers_path,
    remove_provider,
    resolve_route,
    set_route,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


def _openai(**kw) -> Provider:
    """Return a plain OpenAI provider."""
    return Provider(id="openai", name="OpenAI", kind="openai-compatible", base_url="https://api.openai.com/v1", **kw)


def test_add_provider_round_trips_and_keeps_secrets_out_of_the_file(fake_keyring: dict) -> None:
    """Secret values go to the keyring under per-item names; providers.json only flags them."""
    add_provider(
        _openai(headers=[Header("X-Org", "acme"), Header("X-Token", None, secret=True)]),
        api_key="sk-SECRET-1",
        header_secrets={"X-Token": "tok-SECRET-2"},
    )

    registry, notices = load_registry()
    assert notices == []
    got = registry.providers["openai"]
    assert got.headers == [Header("X-Org", "acme"), Header("X-Token", None, secret=True)]
    text = providers_path().read_text(encoding="utf-8")
    assert "SECRET" not in text
    assert fake_keyring == {
        ("mindstew", "openai/api_key"): "sk-SECRET-1",
        ("mindstew", "openai/header/X-Token"): "tok-SECRET-2",
    }
    assert get_secret("openai", "api_key") == "sk-SECRET-1"
    assert get_secret("openai", "header/X-Token") == "tok-SECRET-2"


def test_secret_header_value_never_written_even_if_supplied_on_the_header(fake_keyring: dict) -> None:
    """A secret Header carrying a value is stripped before it reaches providers.json."""
    add_provider(_openai(headers=[Header("X-Token", "LEAK", secret=True)]))
    assert "LEAK" not in providers_path().read_text(encoding="utf-8")


def test_vault_override_beats_global_default(make_vault: Callable[..., Path], fake_keyring: dict) -> None:
    """resolve_route prefers the vault's route, falling back to the global default."""
    vault = make_vault()
    add_provider(_openai())
    add_provider(
        Provider(id="mistral", name="Mistral", kind="openai-compatible", base_url="https://api.mistral.ai/v1")
    )
    set_route("chat", "openai", "gpt-x")

    route, _ = resolve_route(vault, "chat")
    assert (route.provider.id, route.model) == ("openai", "gpt-x")

    set_route("chat", "mistral", "mistral-large", vault=vault)
    route, _ = resolve_route(vault, "chat")
    assert (route.provider.id, route.model) == ("mistral", "mistral-large")
    # the global default is untouched and other roles still fall through
    assert resolve_route(None, "chat")[0].provider.id == "openai"
    assert resolve_route(vault, "vision")[0] is None


def test_set_route_in_vault_preserves_other_config(make_vault: Callable[..., Path], fake_keyring: dict) -> None:
    """Writing an override keeps existing config keys."""
    vault = make_vault()
    cfg = vault / ".mindstew" / "config.yaml"
    cfg.write_text("# mine\nother: 1\n", encoding="utf-8")
    add_provider(_openai())
    set_route("embedding", "openai", "text-embedding-3-small", vault=vault)
    text = cfg.read_text(encoding="utf-8")
    assert "other: 1" in text
    assert "text-embedding-3-small" in text


def test_providers_cannot_be_defined_in_a_vault_config(make_vault: Callable[..., Path], fake_keyring: dict) -> None:
    """A `providers:` block in a vault's config.yaml is ignored with a notice."""
    vault = make_vault()
    (vault / ".mindstew" / "config.yaml").write_text(
        "providers:\n  evil: {name: x, kind: k, base_url: http://evil}\nroutes:\n  chat: {provider: evil, model: m}\n",
        encoding="utf-8",
    )
    route, notices = resolve_route(vault, "chat")
    assert route is None
    assert any("providers" in n for n in notices)
    assert any("evil" in n for n in notices)


def test_set_route_rejects_bad_role_or_unknown_provider(fake_keyring: dict) -> None:
    """Routes need a known role and a registered provider."""
    add_provider(_openai())
    with pytest.raises(ValueError, match="role"):
        set_route("nope", "openai", "m")
    with pytest.raises(ValueError, match="provider"):
        set_route("chat", "ghost", "m")


def test_remove_provider_clears_keyring_and_routes(fake_keyring: dict) -> None:
    """Removing a provider deletes its secrets and the global routes that used it."""
    add_provider(_openai(headers=[Header("X-Token", None, secret=True)]), api_key="k", header_secrets={"X-Token": "t"})
    set_route("chat", "openai", "m")
    assert remove_provider("openai") is True
    assert fake_keyring == {}
    registry, _ = load_registry()
    assert registry.providers == {} and registry.routes == {}
    assert remove_provider("openai") is False


@pytest.mark.parametrize("content", ["", "not json", "[]", "null", '"s"', '{"providers": 3, "routes": []}', "\xff"])
def test_load_registry_tolerates_malformed_files(content: str) -> None:
    """Corrupt or non-mapping files read as empty, with a notice when unreadable."""
    path = providers_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content.encode("latin-1"))
    registry, notices = load_registry()
    assert registry.providers == {} and registry.routes == {}
    assert notices


def test_load_registry_missing_file_is_empty_without_notice() -> None:
    """No file yet is normal."""
    registry, notices = load_registry()
    assert registry.providers == {} and notices == []


def test_load_registry_drops_malformed_entries() -> None:
    """Bad providers, headers and routes are dropped with notices; good ones survive."""
    path = providers_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    good = {"name": "G", "kind": "k", "base_url": "u", "headers": [{"name": "A", "value": "1"}, 5, {"value": "x"}]}
    data = {
        "providers": {"good": good, "bad": "x", "worse": {"name": 1}, "nohdr": {**good, "headers": "oops"}},
        "routes": {
            "chat": {"provider": "good", "model": "m"},
            "vision": 7,
            "bogus": {"provider": "good", "model": "m"},
        },
    }
    path.write_text(json.dumps(data), encoding="utf-8")
    registry, notices = load_registry()
    assert set(registry.providers) == {"good", "nohdr"}
    assert registry.providers["good"].headers == [Header("A", "1")]
    assert registry.providers["nohdr"].headers == []
    assert set(registry.routes) == {"chat"}
    assert notices


@pytest.mark.parametrize(
    "config",
    [
        "",
        "[1, 2]",
        "- a",
        "just a string",
        "routes: 3",
        "routes: [a]",
        "routes: {chat: 4}",
        "{bad: [",
        "routes: {chat: {provider: 1}}",
        "routes: {zzz: {provider: p, model: m}}",
    ],
)
def test_malformed_vault_config_falls_back_to_global(
    make_vault: Callable[..., Path], fake_keyring: dict, config: str
) -> None:
    """Whatever is in config.yaml, resolve_route never raises and falls back to the global default."""
    vault = make_vault()
    (vault / ".mindstew" / "config.yaml").write_text(config, encoding="utf-8")
    add_provider(_openai())
    set_route("chat", "openai", "gpt-x")
    route, _ = resolve_route(vault, "chat")
    assert (route.provider.id, route.model) == ("openai", "gpt-x")


def test_missing_vault_config_falls_back_to_global(tmp_path: Path, fake_keyring: dict) -> None:
    """A folder with no config.yaml still resolves to the global default."""
    add_provider(_openai())
    set_route("chat", "openai", "gpt-x")
    assert resolve_route(tmp_path, "chat")[0].model == "gpt-x"


def test_cli_provider_lifecycle(make_vault: Callable[..., Path], fake_keyring: dict) -> None:
    """Add / ls / set-route (global and --vault) / rm through the CLI; secrets are prompted, not echoed."""
    runner = CliRunner()
    vault = make_vault()
    result = runner.invoke(
        cli,
        [
            "provider",
            "add",
            "openai",
            "--name",
            "OpenAI",
            "--kind",
            "openai-compatible",
            "--base-url",
            "https://x/v1",
            "--api-key",
            "--header",
            "X-Org=acme",
            "--secret-header",
            "X-Token",
        ],
        input="sk-SECRET\ntok-SECRET\n",
    )
    assert result.exit_code == 0, result.output
    assert "SECRET" not in result.output
    assert fake_keyring["mindstew", "openai/api_key"] == "sk-SECRET"

    result = runner.invoke(cli, ["provider", "ls"])
    assert result.exit_code == 0 and "openai" in result.output and "SECRET" not in result.output

    assert runner.invoke(cli, ["provider", "set-route", "chat", "openai", "gpt-x"]).exit_code == 0
    assert (
        runner.invoke(cli, ["provider", "set-route", "vision", "openai", "gpt-v", "--vault", str(vault)]).exit_code
        == 0
    )
    result = runner.invoke(cli, ["provider", "ls", "--vault", str(vault)])
    assert "chat\topenai\tgpt-x" in result.output and "vision\topenai\tgpt-v" in result.output

    bad = runner.invoke(cli, ["provider", "set-route", "chat", "ghost", "m"])
    assert bad.exit_code != 0 and "provider" in bad.output

    assert runner.invoke(cli, ["provider", "rm", "openai"]).exit_code == 0
    assert fake_keyring == {}
    assert runner.invoke(cli, ["provider", "rm", "openai"]).exit_code != 0
