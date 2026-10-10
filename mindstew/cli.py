"""The `mindstew` command line."""

from pathlib import Path

import click

from mindstew.links import Resolver
from mindstew.pages import find_page, list_pages
from mindstew.providers import (
    ROLES,
    Header,
    Provider,
    add_provider,
    load_registry,
    remove_provider,
    resolve_route,
    set_route,
)
from mindstew.registry import load_projects, register
from mindstew.vault import VaultConflictError, VaultExistsError, create_vault, fill_scaffold, is_vault


@click.group()
def cli() -> None:
    """Build a personal wiki from your documents."""


@cli.command()
@click.argument("path", type=click.Path(path_type=Path))
def new(path: Path) -> None:
    """Create a fresh vault at PATH."""
    try:
        create_vault(path)
    except (VaultExistsError, VaultConflictError) as exc:
        raise click.ClickException(str(exc)) from exc
    _register(path)
    click.echo(f"Created vault at {path}")


def _register(path: Path) -> None:
    """Record ``path`` in the project registry, echoing any notice to stderr."""
    if notice := register(path):
        click.echo(notice, err=True)


@cli.command(name="open")
@click.argument("path", type=click.Path(exists=True, file_okay=False, path_type=Path))
def open_vault(path: Path) -> None:
    """Adopt the existing folder PATH as a vault, adding only missing scaffolding."""
    was_vault = is_vault(path)
    try:
        fill_scaffold(path)
    except VaultConflictError as exc:
        raise click.ClickException(str(exc)) from exc
    _register(path)
    click.echo(f"{path} is already a vault" if was_vault else f"Opened vault at {path}")


@cli.command()
@click.argument("vault", required=False, type=click.Path(exists=True, file_okay=False, path_type=Path))
def ls(vault: Path | None) -> None:
    """List the pages in VAULT, or the registered projects when VAULT is omitted."""
    if vault is None:
        projects, notice = load_projects()
        if notice:
            click.echo(notice, err=True)
        for entry in projects:
            missing = "" if Path(entry["path"]).is_dir() else "\t(missing)"
            click.echo(f"{entry['path']}{missing}")
        return
    for page in list_pages(vault):
        click.echo(f"{page.wiki_relpath(vault)}\t{page.type or '?'}\t{page.title or ''}")


@cli.group()
def provider() -> None:
    """Manage model providers and role routes."""


_VAULT_OPT = click.option(
    "--vault", type=click.Path(exists=True, file_okay=False, path_type=Path), help="Apply to this vault only."
)


@provider.command(name="add")
@click.argument("provider_id")
@click.option("--name", help="Display name (default: the id).")
@click.option("--kind", default="openai-compatible", show_default=True)
@click.option("--base-url", required=True)
@click.option("--api-key", "api_key", is_flag=True, help="Prompt for the API key (stored in the Keychain).")
@click.option("--header", "headers", multiple=True, metavar="NAME=VALUE", help="A non-secret header.")
@click.option("--secret-header", "secret_headers", multiple=True, metavar="NAME", help="Prompt for a secret header.")
def provider_add(
    provider_id: str,
    name: str | None,
    kind: str,
    base_url: str,
    api_key: bool,
    headers: tuple[str, ...],
    secret_headers: tuple[str, ...],
) -> None:
    """Register (or replace) provider PROVIDER_ID; secrets go to the Keychain, never providers.json."""
    parsed = []
    for h in headers:
        hname, sep, value = h.partition("=")
        if not sep or not hname:
            raise click.BadParameter(f"{h!r} is not NAME=VALUE", param_hint="--header")
        parsed.append(Header(hname, value))
    parsed += [Header(n, None, secret=True) for n in secret_headers]
    key = click.prompt("API key", hide_input=True) if api_key else None
    secrets = {n: click.prompt(f"Value for header {n}", hide_input=True) for n in secret_headers}
    notices = add_provider(Provider(provider_id, name or provider_id, kind, base_url, parsed), key, secrets)
    for notice in notices:
        click.echo(notice, err=True)
    click.echo(f"Added provider {provider_id}")


@provider.command(name="ls")
@_VAULT_OPT
def provider_ls(vault: Path | None) -> None:
    """List providers, then the routes (effective ones when --vault is given)."""
    registry, notices = load_registry()
    for p in registry.providers.values():
        click.echo(f"{p.id}\t{p.kind}\t{p.base_url}")
    for role in ROLES:
        route, more = resolve_route(vault, role)
        notices += more
        if route:
            click.echo(f"{role}\t{route.provider.id}\t{route.model}")
    for notice in dict.fromkeys(notices):
        click.echo(notice, err=True)


@provider.command(name="rm")
@click.argument("provider_id")
def provider_rm(provider_id: str) -> None:
    """Remove PROVIDER_ID, its Keychain secrets and any global routes using it."""
    if not remove_provider(provider_id):
        raise click.ClickException(f"no such provider: {provider_id}")
    click.echo(f"Removed provider {provider_id}")


@provider.command(name="set-route")
@click.argument("role", type=click.Choice(ROLES))
@click.argument("provider_id")
@click.argument("model")
@_VAULT_OPT
def provider_set_route(role: str, provider_id: str, model: str, vault: Path | None) -> None:
    """Route ROLE to PROVIDER_ID and MODEL, globally or as a --vault override."""
    try:
        set_route(role, provider_id, model, vault)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"{role} -> {provider_id} / {model}")


@cli.command()
@click.argument("vault", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.argument("page")
def show(vault: Path, page: str) -> None:
    """Print the metadata and body of PAGE (a path relative to wiki/) in VAULT."""
    found = find_page(vault, page)
    if found is None:
        raise click.ClickException(f"no such page: {page}")
    click.echo(f"type: {found.type or '?'}")
    click.echo(f"title: {found.title or ''}")
    click.echo(f"sources: {', '.join(found.sources)}")
    click.echo(f"tags: {', '.join(found.tags)}")
    click.echo()
    click.echo(found.body.lstrip("\n"), nl=False)
    links = Resolver(list_pages(vault)).resolve_body(found.body)
    if links:
        click.echo("\nlinks:")
        for link in links:
            dest = link.page.wiki_relpath(vault) if link.page else "(unresolved)"
            click.echo(f"  {link.target} -> {dest}")
