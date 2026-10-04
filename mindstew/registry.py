"""The machine-global project registry: recently used vaults, kept outside any vault."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path


def registry_path() -> Path:
    """Return the registry file, under ``$MINDSTEW_HOME`` if set, else the macOS Application Support folder."""
    home = os.environ.get("MINDSTEW_HOME")
    base = Path(home) if home else Path.home() / "Library" / "Application Support" / "mindstew"
    return base / "projects.json"


def load_projects() -> tuple[list[dict[str, str]], str | None]:
    """Read the registry, most recently used first.

    Never raises: a missing file is empty; an empty, corrupt or non-mapping file is empty with a notice.
    Entries that are not mappings with string ``path`` and ``last_used`` are dropped.

    Returns:
        ``(entries, notice)`` where each entry has ``path`` and ``last_used``, and ``notice`` is None unless
        the file was unreadable.
    """
    path = registry_path()
    if not path.exists():
        return [], None
    try:
        raw_bytes = path.read_bytes()
    except OSError:
        raw_bytes = b""
    try:
        data = json.loads(raw_bytes)  # bad UTF-8 raises UnicodeDecodeError, a ValueError
    except ValueError:
        data = None
    raw = data.get("projects") if isinstance(data, dict) else None
    if not isinstance(raw, list):
        return [], f"notice: project registry {path} is unreadable; treating it as empty"
    entries = [
        {"path": e["path"], "last_used": e["last_used"]}
        for e in raw
        if isinstance(e, dict) and isinstance(e.get("path"), str) and isinstance(e.get("last_used"), str)
    ]
    return sorted(entries, key=lambda e: e["last_used"], reverse=True), None


def register(vault: Path) -> str | None:
    """Record ``vault`` as most recently used, replacing any existing entry for it.

    Args:
        vault: The vault folder to record.

    Returns:
        A notice if the registry could not be written, else None. Never raises.
    """
    resolved = str(vault.resolve())
    entries, _ = load_projects()
    entries = [e for e in entries if e["path"] != resolved]
    entries.append({"path": resolved, "last_used": datetime.now(timezone.utc).isoformat()})
    path = registry_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"projects": entries}, indent=2), encoding="utf-8")
    except OSError:
        return f"notice: could not update project registry {path}"
    return None
