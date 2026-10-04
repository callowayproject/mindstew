"""Vault scaffolding: the on-disk layout of a mindstew vault."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

# The one place page types map to their typed folders under wiki/.
PAGE_TYPES = {
    "entity": "entities",
    "concept": "concepts",
    "source": "sources",
    "query": "queries",
    "comparison": "comparisons",
    "synthesis": "synthesis",
}
PAGE_TYPE_FOLDERS = tuple(PAGE_TYPES.values())

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
# index/ and cache/ in this folder are derived data: safe to delete, rebuilt from sources/ and wiki/.
"""

STARTER_FILES = {"purpose.md": PURPOSE_MD, "schema.md": SCHEMA_MD, f"{CONFIG_DIR}/config.yaml": CONFIG_YAML}
ESSENTIAL_DIRS = ("sources", *(f"wiki/{f}" for f in PAGE_TYPE_FOLDERS), f"{CONFIG_DIR}/skills")
DERIVED_DIRS = (f"{CONFIG_DIR}/index", f"{CONFIG_DIR}/cache")


class VaultExistsError(Exception):
    """Raised when the target folder already contains a complete vault."""


class VaultConflictError(Exception):
    """Raised when an existing entry blocks a scaffold path (e.g. a file named ``wiki``)."""


def _find_conflict(root: Path) -> Path | None:
    """Return the first existing entry of the wrong kind on a scaffold path, or None."""
    for d in (*ESSENTIAL_DIRS, *DERIVED_DIRS):
        path = root
        for part in d.split("/"):
            path = path / part
            if path.exists() and not path.is_dir():
                return path
    return next((p for f in STARTER_FILES if (p := root / f).exists() and not p.is_file()), None)


def is_vault(root: Path) -> bool:
    """Return True if ``root`` holds every essential vault file and folder (derived data is not required)."""
    return all((root / d).is_dir() for d in ESSENTIAL_DIRS) and all((root / f).is_file() for f in STARTER_FILES)


def create_vault(root: Path) -> None:
    """Scaffold a vault at ``root``, idempotently.

    Existing files and folders are left untouched and only missing pieces are created, so
    re-running continues a failed attempt.

    Args:
        root: Folder to create the vault in.

    Raises:
        VaultExistsError: if ``root`` already contains a complete vault.
        VaultConflictError: if an existing file or folder blocks a scaffold path; nothing is created.
    """
    if is_vault(root):
        raise VaultExistsError(f"{root} already contains a vault")
    if (conflict := _find_conflict(root)) is not None:
        raise VaultConflictError(f"cannot create vault: {conflict} already exists and is the wrong kind of entry")
    for d in (*ESSENTIAL_DIRS, *DERIVED_DIRS):
        (root / d).mkdir(parents=True, exist_ok=True)
    for name, content in STARTER_FILES.items():
        path = root / name
        if not path.exists():
            path.write_text(content, encoding="utf-8")
