"""SQLite sandbox ledger helpers.

Fake money only — no real UPI, bank or customer data. Amounts are stored in
paise (integers) to avoid float rounding issues.
"""
from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    id TEXT PRIMARY KEY,
    owner TEXT NOT NULL,
    balance_paise INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS payees (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    account TEXT NOT NULL,
    registered INTEGER NOT NULL DEFAULT 1,
    category TEXT NOT NULL DEFAULT 'other'
);
CREATE TABLE IF NOT EXISTS ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    tool TEXT NOT NULL,
    payee_id TEXT,
    account TEXT,
    amount_paise INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL,
    trace_id TEXT
);
CREATE TABLE IF NOT EXISTS prescriptions (
    id TEXT PRIMARY KEY,
    medicine TEXT NOT NULL,
    dosage TEXT NOT NULL DEFAULT '',
    active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS visits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    doctor TEXT NOT NULL,
    slot TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'booked',
    trace_id TEXT
);
"""

DEFAULT_ACCOUNT = "family-primary"


def default_db_path() -> Path:
    return Path(os.environ.get("KAVALAN_DB", "data/kavalan.db"))


def connect(path: str | os.PathLike | None = None) -> sqlite3.Connection:
    """Open the sandbox DB (creating parents + schema as needed)."""
    db_path = Path(path) if path is not None else default_db_path()
    if str(db_path) != ":memory:" and db_path.parent != Path("."):
        db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def get_balance(conn: sqlite3.Connection, account_id: str = DEFAULT_ACCOUNT) -> int:
    row = conn.execute(
        "SELECT balance_paise FROM accounts WHERE id = ?", (account_id,)
    ).fetchone()
    if row is None:
        raise ValueError(f"unknown account: {account_id}")
    return int(row["balance_paise"])


def list_payees(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT id, name, account, registered, category FROM payees ORDER BY id"
    ).fetchall()
    return [
        {
            "id": r["id"],
            "name": r["name"],
            "account": r["account"],
            "registered": bool(r["registered"]),
            "category": r["category"],
        }
        for r in rows
    ]


def is_registered_payee(conn: sqlite3.Connection, payee_id: str) -> bool:
    row = conn.execute(
        "SELECT registered FROM payees WHERE id = ?", (payee_id,)
    ).fetchone()
    return row is not None and bool(row["registered"])


def record_payment(
    conn: sqlite3.Connection,
    *,
    tool: str,
    amount_paise: int,
    payee_id: str | None = None,
    account: str | None = None,
    status: str = "executed",
    trace_id: str | None = None,
    from_account: str = DEFAULT_ACCOUNT,
) -> int:
    """Append a ledger row; decrements the sandbox balance when executed."""
    if amount_paise < 0:
        raise ValueError("amount_paise must be >= 0")
    if status == "executed":
        balance = get_balance(conn, from_account)
        if balance < amount_paise:
            raise ValueError(
                f"insufficient sandbox funds: have {balance}, need {amount_paise}"
            )
        conn.execute(
            "UPDATE accounts SET balance_paise = balance_paise - ? WHERE id = ?",
            (amount_paise, from_account),
        )
    cur = conn.execute(
        "INSERT INTO ledger (ts, tool, payee_id, account, amount_paise, status, trace_id)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (time.time(), tool, payee_id, account, amount_paise, status, trace_id),
    )
    conn.commit()
    return int(cur.lastrowid)


def ledger_entries(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT * FROM ledger ORDER BY id").fetchall()
    return [dict(r) for r in rows]


def list_prescriptions(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT id, medicine, dosage, active FROM prescriptions ORDER BY id"
    ).fetchall()
    return [
        {"id": r["id"], "medicine": r["medicine"], "dosage": r["dosage"],
         "active": bool(r["active"])}
        for r in rows
    ]
