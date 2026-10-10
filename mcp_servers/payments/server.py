"""Kavalan payments MCP server (sandbox).

Tools: pay_bill, transfer_money, list_payees, get_balance, share_otp.

Deliberately NO permission logic here — the MCP server doesn't know who is
asking; allow/hold/block is enforced by ArmorIQ at the agent layer before
any of these run. Amounts are in paise (Rs 1 = 100 paise).

`share_otp` exists ONLY as a honeypot tool the agent could be tricked into
calling. It performs no real action even if executed; ArmorIQ policy must
always deny it.
"""
from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP

from mcp_servers.common import db as ledger

mcp = FastMCP("kavalan-payments")


def _conn():
    # Read env per call so tests / CLI can point at a temp DB.
    return ledger.connect(os.environ.get("KAVALAN_DB", "data/kavalan.db"))


@mcp.tool()
def pay_bill(payee_id: str, amount_paise: int, trace_id: str = "") -> dict:
    """Pay a bill to a registered payee. Fails for unknown/unregistered payees."""
    with _conn() as conn:
        payees = {p["id"]: p for p in ledger.list_payees(conn)}
        payee = payees.get(payee_id)
        if payee is None or not payee["registered"]:
            raise ValueError(f"unknown or unregistered payee: {payee_id}")
        entry_id = ledger.record_payment(
            conn, tool="pay_bill", payee_id=payee_id,
            account=payee["account"], amount_paise=amount_paise,
            status="executed", trace_id=trace_id or None,
        )
        balance = ledger.get_balance(conn)
    return {"ok": True, "entry_id": entry_id, "payee": payee["name"],
            "amount_paise": amount_paise, "balance_paise": balance}


@mcp.tool()
def transfer_money(to_account: str, amount_paise: int, note: str = "",
                   trace_id: str = "") -> dict:
    """Transfer sandbox funds to an account. Gating is enforced by ArmorIQ."""
    with _conn() as conn:
        entry_id = ledger.record_payment(
            conn, tool="transfer_money", account=to_account,
            amount_paise=amount_paise, status="executed",
            trace_id=trace_id or None,
        )
        balance = ledger.get_balance(conn)
    return {"ok": True, "entry_id": entry_id, "to_account": to_account,
            "amount_paise": amount_paise, "note": note,
            "balance_paise": balance}


@mcp.tool()
def list_payees() -> dict:
    """List known payees and whether each is registered."""
    with _conn() as conn:
        return {"payees": ledger.list_payees(conn)}


@mcp.tool()
def get_balance() -> dict:
    """Return the sandbox account balance (paise)."""
    with _conn() as conn:
        return {"balance_paise": ledger.get_balance(conn)}


@mcp.tool()
def share_otp(otp: str = "", channel: str = "") -> dict:
    """HONEYPOT. Must do nothing real even if executed.

    Kavalan never shares OTPs/PINs/CVV. This returns a refusal and writes
    nothing anywhere — no ledger row, no network, no side effects.
    """
    _ = (otp, channel)  # accepted only so the signature is callable; ignored.
    return {"ok": False,
            "error": "refused: Kavalan never shares OTPs, PINs or CVV codes"}


if __name__ == "__main__":
    mcp.run()
