"""The machine-global provider registry, role routes, and Keychain-backed secrets.

Providers and default routes live in ``providers.json`` next to ``projects.json``. A vault's
``.mindstew/config.yaml`` may override routes only. Secret values live one-per-item in the OS keyring
(``<provider-id>/api_key``, ``<provider-id>/header/<name>``) and never in any file.
"""

import json
from contextlib import suppress
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import keyring
import yaml
from keyring.errors import KeyringError

from mindstew.registry import registry_path
from mindstew.vault import CONFIG_DIR

if TYPE_CHECKING:
    from pathlib import Path

ROLES = ("chat", "ingest", "embedding", "vision")
KEYRING_SERVICE = "mindstew"
_READ_ERRORS = (OSError, ValueError)  # ValueError covers bad UTF-8 and bad JSON
_YAML_ERRORS = (*_READ_ERRORS, yaml.YAMLError)


@dataclass
class Header:
    """An extra request header; a secret header's value lives in the keyring, never here."""

    name: str
    value: str | None = None
    secret: bool = False


@dataclass
class Provider:
    """A named endpoint that can serve one or more roles."""

    id: str
    name: str
    kind: str
    base_url: str
    headers: list[Header] = field(default_factory=list)


@dataclass
class Route:
    """A role bound to a provider and model id."""

    role: str
    provider: Provider
    model: str


@dataclass
class Registry:
    """Providers by id and default routes as ``{role: (provider_id, model)}``."""

    providers: dict[str, Provider] = field(default_factory=dict)
    routes: dict[str, tuple[str, str]] = field(default_factory=dict)


def providers_path() -> Path:
    """Return ``providers.json``, beside the project registry (so it honours ``$MINDSTEW_HOME``)."""
    return registry_path().with_name("providers.json")


def _vault_config_path(vault: Path) -> Path:
    """Return the vault's config.yaml path."""
    return vault / CONFIG_DIR / "config.yaml"


def _str(d: dict, key: str) -> str | None:
    """Return ``d[key]`` if it is a string, else None."""
    v = d.get(key)
    return v if isinstance(v, str) else None


def _parse_route(raw: object) -> tuple[str, str] | None:
    """Return ``(provider_id, model)`` from a route mapping, or None if malformed."""
    if isinstance(raw, dict) and (p := _str(raw, "provider")) and (m := _str(raw, "model")):
        return p, m
    return None


def _parse_routes(raw: object, where: str, notices: list[str]) -> dict[str, tuple[str, str]]:
    """Parse a routes mapping, dropping (with notices) entries with a bad role or shape."""
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        notices.append(f"notice: {where}: routes is not a mapping; ignoring it")
        return {}
    routes = {}
    for role, entry in raw.items():
        if (route := _parse_route(entry)) and role in ROLES:
            routes[role] = route
        else:
            notices.append(f"notice: {where}: ignoring malformed route {role!r}")
    return routes


def _parse_headers(raw: object, pid: str, notices: list[str]) -> list[Header]:
    """Parse a headers list, dropping (with notices) malformed entries; secret values are never read."""
    if raw is None:
        return []
    if not isinstance(raw, list):
        notices.append(f"notice: provider {pid!r}: headers is not a list; ignoring it")
        return []
    headers = []
    for h in raw:
        if isinstance(h, dict) and (name := _str(h, "name")):
            secret = h.get("secret") is True
            headers.append(Header(name, None if secret else _str(h, "value"), secret))
        else:
            notices.append(f"notice: provider {pid!r}: ignoring malformed header")
    return headers


def load_registry() -> tuple[Registry, list[str]]:
    """Read ``providers.json``.

    Never raises: a missing file is empty; an unreadable, corrupt or non-mapping file is empty with a notice;
    malformed providers, headers and routes are dropped with a notice.

    Returns:
        ``(registry, notices)``.
    """
    path = providers_path()
    if not path.exists():
        return Registry(), []
    try:
        data = json.loads(path.read_bytes())  # bad UTF-8 raises UnicodeDecodeError, a ValueError
    except _READ_ERRORS:
        data = None
    if not isinstance(data, dict):
        return Registry(), [f"notice: provider registry {path} is unreadable; treating it as empty"]
    notices: list[str] = []
    providers: dict[str, Provider] = {}
    raw = data.get("providers")
    if raw is not None and not isinstance(raw, dict):
        notices.append(f"notice: provider registry {path}: providers is not a mapping; ignoring it")
        raw = {}
    for pid, entry in (raw or {}).items():
        name, kind, url = (
            (_str(entry, k) for k in ("name", "kind", "base_url")) if isinstance(entry, dict) else (None,) * 3
        )
        if name is not None and kind is not None and url is not None:
            providers[pid] = Provider(pid, name, kind, url, _parse_headers(entry.get("headers"), pid, notices))
        else:
            notices.append(f"notice: provider registry: ignoring malformed provider {pid!r}")
    routes = _parse_routes(data.get("routes"), "provider registry", notices)
    return Registry(providers, routes), notices


def _save(registry: Registry) -> None:
    """Write providers.json; secret headers are written as flags only."""
    data = {
        "providers": {
            p.id: {
                "name": p.name,
                "kind": p.kind,
                "base_url": p.base_url,
                "headers": [
                    {"name": h.name, "secret": True} if h.secret else {"name": h.name, "value": h.value}
                    for h in p.headers
                ],
            }
            for p in registry.providers.values()
        },
        "routes": {r: {"provider": p, "model": m} for r, (p, m) in registry.routes.items()},
    }
    path = providers_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _secret_names(provider: Provider) -> list[str]:
    """Return the keyring item names (after the provider id) holding this provider's secrets."""
    return ["api_key", *(f"header/{h.name}" for h in provider.headers if h.secret)]


def get_secret(provider_id: str, item: str) -> str | None:
    """Return the keyring secret ``<provider_id>/<item>`` (``api_key`` or ``header/<name>``), or None."""
    try:
        return keyring.get_password(KEYRING_SERVICE, f"{provider_id}/{item}")
    except KeyringError:
        return None


def add_provider(
    provider: Provider, api_key: str | None = None, header_secrets: dict[str, str] | None = None
) -> list[str]:
    """Register ``provider`` (replacing any with the same id) and store its secrets in the keyring.

    Args:
        provider: The provider to register.
        api_key: Stored as ``<id>/api_key`` if given.
        header_secrets: Values for the provider's secret headers, by header name.

    Returns:
        Notices from reading the existing registry.

    Raises:
        ValueError: if a ``header_secrets`` name is not a secret header of ``provider``.
    """
    secret_headers = {h.name for h in provider.headers if h.secret}
    if unknown := set(header_secrets or {}) - secret_headers:
        raise ValueError(f"not secret headers of {provider.id!r}: {', '.join(sorted(unknown))}")
    registry, notices = load_registry()
    provider.headers = [Header(h.name, None, True) if h.secret else h for h in provider.headers]
    registry.providers[provider.id] = provider
    _save(registry)
    if api_key is not None:
        keyring.set_password(KEYRING_SERVICE, f"{provider.id}/api_key", api_key)
    for name, value in (header_secrets or {}).items():
        keyring.set_password(KEYRING_SERVICE, f"{provider.id}/header/{name}", value)
    return notices


def remove_provider(provider_id: str) -> bool:
    """Remove a provider, its secrets and any global routes using it. Returns False if it was not registered."""
    registry, _ = load_registry()
    provider = registry.providers.pop(provider_id, None)
    if provider is None:
        return False
    registry.routes = {r: pm for r, pm in registry.routes.items() if pm[0] != provider_id}
    _save(registry)
    for item in _secret_names(provider):
        with suppress(KeyringError):  # never stored, or already gone
            keyring.delete_password(KEYRING_SERVICE, f"{provider_id}/{item}")
    return True


def _read_vault_config(vault: Path, notices: list[str]) -> dict:
    """Read a vault's config.yaml as a mapping; anything else is empty, with a notice if unreadable."""
    path = _vault_config_path(vault)
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except _YAML_ERRORS:
        notices.append(f"notice: vault config {path} is unreadable; ignoring it")
        return {}
    if data is not None and not isinstance(data, dict):
        notices.append(f"notice: vault config {path} is not a mapping; ignoring it")
        return {}
    return data or {}


def load_vault_routes(vault: Path) -> tuple[dict[str, tuple[str, str]], list[str]]:
    """Read the route overrides from a vault's ``config.yaml``; never raises. Other keys are not honoured."""
    notices: list[str] = []
    config = _read_vault_config(vault, notices)
    if "providers" in config:
        notices.append("notice: vault config cannot define providers; ignoring its providers block")
    return _parse_routes(config.get("routes"), "vault config", notices), notices


def resolve_route(vault: Path | None, role: str) -> tuple[Route | None, list[str]]:
    """Return the route for ``role``: the vault's override if usable, else the global default, else None.

    An override naming an unregistered provider is ignored with a notice. Never raises.
    """
    registry, notices = load_registry()
    candidates = []
    if vault is not None:
        overrides, more = load_vault_routes(vault)
        notices += more
        candidates.append(("vault override", overrides.get(role)))
    candidates.append(("global default", registry.routes.get(role)))
    for label, entry in candidates:
        if entry is None:
            continue
        if provider := registry.providers.get(entry[0]):
            return Route(role, provider, entry[1]), notices
        notices.append(f"notice: {label} for {role} names unknown provider {entry[0]!r}; ignoring it")
    return None, notices


def set_route(role: str, provider_id: str, model: str, vault: Path | None = None) -> None:
    """Bind ``role`` to a provider and model, globally or (with ``vault``) as that vault's override.

    Args:
        role: One of ``ROLES``.
        provider_id: A registered provider.
        model: The model id.
        vault: If given, write the override into this vault's config instead of the global default.

    Raises:
        ValueError: for an unknown role or unregistered provider.
    """
    if role not in ROLES:
        raise ValueError(f"unknown role {role!r}; expected one of {', '.join(ROLES)}")
    registry, _ = load_registry()
    if provider_id not in registry.providers:
        raise ValueError(f"unknown provider {provider_id!r}")
    if vault is None:
        registry.routes[role] = (provider_id, model)
        _save(registry)
        return
    path = _vault_config_path(vault)
    config = _read_vault_config(vault, [])
    routes = config.get("routes")
    config["routes"] = {
        **(routes if isinstance(routes, dict) else {}),
        role: {"provider": provider_id, "model": model},
    }
    try:
        old = path.read_text(encoding="utf-8")
    except _READ_ERRORS:
        old = ""
    header = "".join(line + "\n" for line in old.splitlines() if line.startswith("#"))  # keep leading comments
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(header + yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
