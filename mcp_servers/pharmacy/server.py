"""Kavalan pharmacy MCP server (sandbox).

Tools: reorder_medicine, book_doctor_visit, list_prescriptions.
No permission logic here — enforcement lives in ArmorIQ at the agent layer.
"""
from __future__ import annotations

import os
import time

from mcp.server.fastmcp import FastMCP

from mcp_servers.common import db as ledger

mcp = FastMCP("kavalan-pharmacy")


def _conn():
    return ledger.connect(os.environ.get("KAVALAN_DB", "data/kavalan.db"))


@mcp.tool()
def reorder_medicine(prescription_id: str, quantity: int = 1,
                     trace_id: str = "") -> dict:
    """Reorder medicine against an active prescription (sandbox record only)."""
    if quantity < 1:
        raise ValueError("quantity must be >= 1")
    with _conn() as conn:
        rx = {p["id"]: p for p in ledger.list_prescriptions(conn)}.get(prescription_id)
        if rx is None or not rx["active"]:
            raise ValueError(f"unknown or inactive prescription: {prescription_id}")
        entry_id = ledger.record_payment(
            conn, tool="reorder_medicine", payee_id=prescription_id,
            amount_paise=0, status="executed", trace_id=trace_id or None,
        )
    return {"ok": True, "entry_id": entry_id, "medicine": rx["medicine"],
            "dosage": rx["dosage"], "quantity": quantity}


@mcp.tool()
def book_doctor_visit(doctor: str, slot: str = "",
                      trace_id: str = "") -> dict:
    """Book a doctor visit (sandbox record only)."""
    with _conn() as conn:
        cur = conn.execute(
            "INSERT INTO visits (ts, doctor, slot, status, trace_id)"
            " VALUES (?, ?, ?, 'booked', ?)",
            (time.time(), doctor, slot, trace_id or None),
        )
        conn.commit()
        visit_id = int(cur.lastrowid)
    return {"ok": True, "visit_id": visit_id, "doctor": doctor, "slot": slot}


@mcp.tool()
def list_prescriptions() -> dict:
    """List prescriptions and whether each is active."""
    with _conn() as conn:
        return {"prescriptions": ledger.list_prescriptions(conn)}


if __name__ == "__main__":
    mcp.run()
