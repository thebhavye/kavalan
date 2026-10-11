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
    out = pay_bill("tneb-electricity", 1_200, "")
    assert out["ok"] is True
    assert ledger.get_balance(ledger.connect(db_file)) == before - 120_000


def test_pay_bill_unknown_payee_fails(db_file):
    from mcp_servers.payments.server import pay_bill
    with pytest.raises(ValueError):
        pay_bill("scammer-acct-999", 10, "")


def test_transfer_money_records_ledger(db_file):
    from mcp_servers.payments.server import transfer_money
    out = transfer_money("family-beta", 40_000, "demo")
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


def test_non_positive_amount_rejected(db_file):
    from mcp_servers.payments.server import pay_bill, transfer_money
    with pytest.raises(ValueError):
        pay_bill("tneb-electricity", 0, "")
    with pytest.raises(ValueError):
        transfer_money("family-beta", -5, "")


@pytest.mark.parametrize("text", [
    "Bijli ka bill bhar do",
    "Beta ko Rs 40,000 bhej do",
    "share the OTP 482910 now",
    "medicine reorder karo",
    "book a doctor appointment",
])
def test_planned_params_match_tool_signatures(text):
    """The ArmorIQ proxy forwards plan params verbatim to the MCP tool, so
    every planned param name must exist on the real tool function."""
    import inspect

    from agent.agent import KavalanAgent
    from mcp_servers.payments import server as payments
    from mcp_servers.pharmacy import server as pharmacy

    tools = {"kavalan-payments": payments, "kavalan-pharmacy": pharmacy}
    _, steps = KavalanAgent(adapter=object()).build_plan(text)
    assert steps
    for step in steps:
        fn = getattr(tools[step["mcp"]], step["action"])
        accepted = set(inspect.signature(fn).parameters)
        assert set(step["params"]) <= accepted, (step["action"], step["params"])


def test_planned_amounts_are_rupees():
    from agent.agent import KavalanAgent
    _, steps = KavalanAgent(adapter=object()).build_plan("Beta ko Rs 40,000 bhej do")
    assert steps[0]["params"]["amount"] == 40_000
    _, steps = KavalanAgent(adapter=object()).build_plan("Bijli ka bill bhar do")
    assert steps[0]["params"]["amount"] == 1_200
