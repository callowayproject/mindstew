"""The persistent, strictly serial ingest queue, kept in the vault's derived ``.mindstew/index/ingest.db``.

Every call opens its own short-lived connection, so a single background worker (or the UI thread) can call
any function safely. The database is derived data: if it is missing it is created, and if it is unreadable
it is set aside (``ingest.db.corrupt``) and recreated empty.
"""

import hashlib
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from mindstew.vault import CONFIG_DIR

MAX_ATTEMPTS = 3

_SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT NOT NULL UNIQUE,
    sha256 TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('queued', 'running', 'done', 'failed')),
    attempts INTEGER NOT NULL DEFAULT 0,
    error TEXT
)
"""


@dataclass(frozen=True)
class QueueItem:
    """A claimed queue entry."""

    id: int
    path: Path
    sha256: str
    attempts: int


@dataclass(frozen=True)
class ItemStatus:
    """A queue row as shown by ``status``."""

    id: int
    path: Path
    status: str
    attempts: int
    error: str | None


def list_items(vault: Path) -> list[ItemStatus]:
    """Return every queue entry in enqueue order."""
    with closing(_connect(vault)) as conn:
        rows = conn.execute("SELECT id, path, status, attempts, error FROM items ORDER BY id").fetchall()
    return [ItemStatus(r[0], Path(r[1]), r[2], r[3], r[4]) for r in rows]


def queue_db_path(vault: Path) -> Path:
    """Return the queue database path for ``vault``."""
    return vault / CONFIG_DIR / "index" / "ingest.db"


def _connect(vault: Path) -> sqlite3.Connection:
    """Open the queue database, creating it (and the index dir) on demand and replacing it if corrupt."""
    db = queue_db_path(vault)
    db.parent.mkdir(parents=True, exist_ok=True)
    for _ in range(2):
        conn = sqlite3.connect(db, isolation_level=None, timeout=30)
        try:
            conn.execute(_SCHEMA)
            conn.execute("SELECT count(*) FROM items").fetchone()
        except sqlite3.DatabaseError:
            conn.close()
            db.replace(db.with_name(db.name + ".corrupt"))
        else:
            return conn
    raise sqlite3.DatabaseError(f"cannot create ingest queue at {db}")  # pragma: no cover


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def enqueue(vault: Path, path: Path, *, force: bool = False) -> bool:
    """Queue ``path`` for ingest unless its content is already queued, running, done or terminally failed.

    A changed file (different SHA256) is re-queued with its attempts reset.

    Args:
        vault: The vault root.
        path: The source file to queue.
        force: Re-queue even if the content is unchanged (bypasses the hash cache).

    Returns:
        True if the file was queued, False if it was skipped.
    """
    resolved = str(path.resolve())
    digest = _sha256(path)
    with closing(_connect(vault)) as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT sha256 FROM items WHERE path = ?", (resolved,)).fetchone()
        if row and row[0] == digest and not force:
            conn.execute("COMMIT")
            return False
        conn.execute(
            "INSERT INTO items (path, sha256, status) VALUES (?, ?, 'queued') "
            "ON CONFLICT(path) DO UPDATE SET sha256 = excluded.sha256, status = 'queued', attempts = 0, error = NULL",
            (resolved, digest),
        )
        conn.execute("COMMIT")
        return True


def next_item(vault: Path) -> QueueItem | None:
    """Claim the oldest queued item and mark it running; None if the queue is empty or an item is running."""
    with closing(_connect(vault)) as conn:
        conn.execute("BEGIN IMMEDIATE")
        if conn.execute("SELECT 1 FROM items WHERE status = 'running'").fetchone():
            conn.execute("COMMIT")
            return None
        row = conn.execute(
            "SELECT id, path, sha256, attempts FROM items WHERE status = 'queued' ORDER BY id LIMIT 1"
        ).fetchone()
        if row:
            conn.execute("UPDATE items SET status = 'running' WHERE id = ?", (row[0],))
        conn.execute("COMMIT")
    return QueueItem(id=row[0], path=Path(row[1]), sha256=row[2], attempts=row[3]) if row else None


def mark_done(vault: Path, item_id: int) -> None:
    """Mark a running item done."""
    with closing(_connect(vault)) as conn:
        conn.execute("UPDATE items SET status = 'done', error = NULL WHERE id = ?", (item_id,))


def mark_failed(vault: Path, item_id: int, error: str) -> None:
    """Record a failure: back to queued, or terminal ``failed`` once ``MAX_ATTEMPTS`` is reached."""
    with closing(_connect(vault)) as conn:
        conn.execute(
            "UPDATE items SET attempts = attempts + 1, error = ?, "
            "status = CASE WHEN attempts + 1 >= ? THEN 'failed' ELSE 'queued' END WHERE id = ?",
            (error, MAX_ATTEMPTS, item_id),
        )


def recover_running(vault: Path) -> int:
    """Return items left ``running`` by an interrupted session to ``queued``; returns how many."""
    with closing(_connect(vault)) as conn:
        return conn.execute("UPDATE items SET status = 'queued' WHERE status = 'running'").rowcount
