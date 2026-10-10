"""Seed the sandbox: payees (TNEB electricity, one family member), balance,
prescriptions. Idempotent — safe to re-run. Run: make seed"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp_servers.common import db as ledger


def seed(db_path: str | None = None) -> None:
    conn = ledger.connect(db_path or os.environ.get("KAVALAN_DB", "data/kavalan.db"))
    conn.execute(
        "INSERT OR REPLACE INTO accounts (id, owner, balance_paise)"
        " VALUES ('family-primary', 'Kavalan family', 10000000)"
    )  # Rs 100,000 sandbox funds
    conn.executemany(
        "INSERT OR REPLACE INTO payees (id, name, account, registered, category)"
        " VALUES (?, ?, ?, ?, ?)",
        [
            ("tneb-electricity", "TNEB electricity", "tneb-acct-001", 1, "utility"),
            ("family-beta", "Beta (son)", "beta-acct-002", 1, "family"),
            ("apollo-pharmacy", "Apollo Pharmacy", "apollo-acct-003", 1, "pharmacy"),
        ],
    )
    conn.executemany(
        "INSERT OR REPLACE INTO prescriptions (id, medicine, dosage, active)"
        " VALUES (?, ?, ?, ?)",
        [
            ("rx-metformin", "Metformin", "500mg twice daily", 1),
            ("rx-amlodipine", "Amlodipine", "5mg once daily", 1),
        ],
    )
    conn.commit()
    balance = ledger.get_balance(conn)
    payees = ledger.list_payees(conn)
    conn.close()
    print(f"seeded: balance_paise={balance}, payees={[p['id'] for p in payees]}")


if __name__ == "__main__":
    seed()
