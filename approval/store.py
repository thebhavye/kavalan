"""Held-action store (SQLite). A family member approves HELD actions here;
the agent resumes an action ONLY after an approval row is recorded, and
re-submits through ArmorIQ — never executing on local state alone."""
from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path

STATUS_PENDING = "pending"
STATUS_APPROVED = "approved"
STATUS_REJECTED = "rejected"

# Format of args_json. v1 rows stored `amount` in paise; v2 stores whole
# rupees. Rows older than ARGS_VERSION are never resumed (fail closed) —
# replaying a v1 amount as rupees would move 100x the intended money.
ARGS_VERSION = 2

SCHEMA = """
CREATE TABLE IF NOT EXISTS held_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at REAL NOT NULL,
    decided_at REAL,
    trace_id TEXT NOT NULL,
    tool TEXT NOT NULL,
    args_json TEXT NOT NULL DEFAULT '{}',
    reason TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending',
    args_version INTEGER NOT NULL DEFAULT 1
);
"""


def default_db_path() -> Path:
    return Path(os.environ.get("KAVALAN_APPROVAL_DB", "data/approval.db"))


def connect(path: str | os.PathLike | None = None) -> sqlite3.Connection:
    db_path = Path(path) if path is not None else default_db_path()
    if str(db_path) != ":memory:":
        db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    _migrate(conn)
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    """Add args_version to pre-existing DBs; old rows default to v1 (paise)."""
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(held_actions)")}
    if "args_version" not in cols:
        conn.execute("ALTER TABLE held_actions"
                     " ADD COLUMN args_version INTEGER NOT NULL DEFAULT 1")
        conn.commit()


def add_held(*, trace_id: str, tool: str, args: dict, reason: str,
             path: str | os.PathLike | None = None) -> int:
    with connect(path) as conn:
        cur = conn.execute(
            "INSERT INTO held_actions"
            " (created_at, trace_id, tool, args_json, reason, status, args_version)"
            " VALUES (?, ?, ?, ?, ?, 'pending', ?)",
            (time.time(), trace_id, tool, json.dumps(args, ensure_ascii=False), reason,
             ARGS_VERSION),
        )
        conn.commit()
        return int(cur.lastrowid)


def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["args"] = json.loads(d.pop("args_json") or "{}")
    return d


def list_pending(path: str | os.PathLike | None = None) -> list[dict]:
    with connect(path) as conn:
        rows = conn.execute(
            "SELECT * FROM held_actions WHERE status = 'pending' ORDER BY id"
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_held(held_id: int, path: str | os.PathLike | None = None) -> dict | None:
    with connect(path) as conn:
        row = conn.execute(
            "SELECT * FROM held_actions WHERE id = ?", (held_id,)
        ).fetchone()
    return _row_to_dict(row) if row else None


def set_decision(held_id: int, approved: bool,
                 path: str | os.PathLike | None = None) -> dict | None:
    status = STATUS_APPROVED if approved else STATUS_REJECTED
    with connect(path) as conn:
        cur = conn.execute(
            "UPDATE held_actions SET status = ?, decided_at = ?"
            " WHERE id = ? AND status = 'pending'",
            (status, time.time(), held_id),
        )
        conn.commit()
        if cur.rowcount == 0:
            return get_held(held_id, path)
    return get_held(held_id, path)
