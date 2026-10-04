"""The `mindstew` command line."""

from pathlib import Path

import click

from mindstew.vault import VaultExistsError, create_vault


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
