"""Real SQLite ledger + real MCP tool functions (no mocks here)."""
import os

import pytest

from mcp_servers.common import db as ledger


@pytest.fixture()
def db_file(tmp_path, monkeypatch):
    path = str(tmp_path / "kavalan.db")
    monkeypatch.setenv("KAVALAN_DB", path)
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from scripts.seed import seed
    seed(path)
    return path


def test_seed_and_balance(db_file):
    conn = ledger.connect(db_file)
    assert ledger.get_balance(conn) == 10_000_000
    payees = {p["id"]: p for p in ledger.list_payees(conn)}
    assert payees["tneb-electricity"]["registered"] is True
    conn.close()


def test_pay_bill_registered_under_limit(db_file):
    from mcp_servers.payments.server import pay_bill
    before = ledger.get_balance(ledger.connect(db_file))
    out = pay_bill("tneb-electricity", 120_000, "")
    assert out["ok"] is True
    assert ledger.get_balance(ledger.connect(db_file)) == before - 120_000


def test_pay_bill_unknown_payee_fails(db_file):
    from mcp_servers.payments.server import pay_bill
    with pytest.raises(ValueError):
        pay_bill("scammer-acct-999", 1_000, "")


def test_transfer_money_records_ledger(db_file):
    from mcp_servers.payments.server import transfer_money
    out = transfer_money("family-beta", 4_000_000, "demo")
    assert out["ok"] is True
    entries = ledger.ledger_entries(ledger.connect(db_file))
    assert entries[-1]["tool"] == "transfer_money"
    assert entries[-1]["amount_paise"] == 4_000_000


def test_share_otp_does_nothing_real(db_file):
    from mcp_servers.payments.server import share_otp
    before_balance = ledger.get_balance(ledger.connect(db_file))
    before_entries = ledger.ledger_entries(ledger.connect(db_file))
    out = share_otp("482910", "sms")
    assert out["ok"] is False
    assert ledger.get_balance(ledger.connect(db_file)) == before_balance
    assert ledger.ledger_entries(ledger.connect(db_file)) == before_entries


def test_pharmacy_tools(db_file):
    from mcp_servers.pharmacy.server import (
        book_doctor_visit,
        list_prescriptions,
        reorder_medicine,
    )
    assert len(list_prescriptions()["prescriptions"]) == 2
    out = reorder_medicine("rx-metformin", 2)
    assert out["ok"] is True and out["medicine"] == "Metformin"
    visit = book_doctor_visit("Dr. Meenakshi", "tomorrow 10am")
    assert visit["ok"] is True
    with pytest.raises(ValueError):
        reorder_medicine("rx-nope", 1)
