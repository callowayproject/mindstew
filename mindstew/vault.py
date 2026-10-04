"""Vault scaffolding: the on-disk layout of a mindstew vault."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

PAGE_TYPE_FOLDERS = ("entities", "concepts", "sources", "queries", "comparisons", "synthesis")

CONFIG_DIR = ".mindstew"

PURPOSE_MD = """# Purpose

Describe what this wiki is for. The ingest process reads this file to decide what matters.

- What topics or questions does this wiki cover?
- Who is it for?
- What should be emphasized or ignored?

Edit this file freely; it is plain Markdown.
"""

SCHEMA_MD = f"""# Schema

Every wiki page lives in a typed folder under `wiki/` and starts with YAML frontmatter:

```yaml
---
type: entity
title: Page title
sources: [sources/example.pdf]
tags: [optional]
---
```

Page types and their folders: {", ".join(f"`wiki/{f}/`" for f in PAGE_TYPE_FOLDERS)}.

Links between pages are `[[wikilinks]]` in the body, matched case-insensitively against titles.

Edit this file freely; it is plain Markdown.
"""

CONFIG_YAML = """# Per-vault mindstew configuration.
"""

DERIVED_README = """# Derived data

Everything in this folder can be rebuilt from `sources/` and `wiki/`.
Deleting it is safe; it is regenerated on demand.
"""


class VaultExistsError(Exception):
    """Raised when the target folder already contains a vault."""


def is_vault(root: Path) -> bool:
    """Return True if ``root`` already holds a mindstew vault."""
    return (root / CONFIG_DIR).exists()


def create_vault(root: Path) -> None:
    """Scaffold a fresh vault at ``root``.

    Args:
        root: Folder to create the vault in.

    Raises:
        VaultExistsError: if ``root`` already contains a vault.
    """
    if is_vault(root):
        raise VaultExistsError(f"{root} already contains a vault")
    (root / "sources").mkdir(parents=True, exist_ok=True)
    for folder in PAGE_TYPE_FOLDERS:
        (root / "wiki" / folder).mkdir(parents=True, exist_ok=True)
    (root / "purpose.md").write_text(PURPOSE_MD, encoding="utf-8")
    (root / "schema.md").write_text(SCHEMA_MD, encoding="utf-8")
    config = root / CONFIG_DIR
    (config / "skills").mkdir(parents=True)
    for derived in ("index", "cache"):
        (config / derived).mkdir()
        (config / derived / "README.md").write_text(DERIVED_README, encoding="utf-8")
    (config / "config.yaml").write_text(CONFIG_YAML, encoding="utf-8")
