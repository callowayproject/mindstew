"""The `mindstew` command line."""

from pathlib import Path

import click

from mindstew.links import Resolver
from mindstew.pages import find_page, list_pages
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
