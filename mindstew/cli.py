"""The `mindstew` command line."""

from pathlib import Path

import click

from mindstew.links import Resolver
from mindstew.pages import find_page, list_pages
from mindstew.vault import VaultExistsError, create_vault, is_vault


@click.group()
def cli() -> None:
    """Build a personal wiki from your documents."""


@cli.command()
@click.argument("path", type=click.Path(path_type=Path))
def new(path: Path) -> None:
    """Create a fresh vault at PATH."""
    try:
        create_vault(path)
    except VaultExistsError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"Created vault at {path}")


@cli.command(name="open")
@click.argument("path", type=click.Path(exists=True, file_okay=False, path_type=Path))
def open_vault(path: Path) -> None:
    """Adopt the existing folder PATH as a vault, adding only missing scaffolding."""
    if is_vault(path):
        click.echo(f"{path} is already a vault")
        return
    create_vault(path)
    click.echo(f"Opened vault at {path}")


@cli.command()
@click.argument("vault", type=click.Path(exists=True, file_okay=False, path_type=Path))
def ls(vault: Path) -> None:
    """List the pages in VAULT."""
    for page in list_pages(vault):
        click.echo(f"{page.path.relative_to(vault / 'wiki')}\t{page.type or '?'}\t{page.title or ''}")


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
        for target, linked in links:
            dest = str(linked.path.relative_to(vault / "wiki")) if linked else "(unresolved)"
            click.echo(f"  {target} -> {dest}")
