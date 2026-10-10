"""Approval flow: hold -> phone page -> approve -> agent resumes via ArmorIQ."""
from fastapi.testclient import TestClient

from agent.agent import KavalanAgent
from agent.armoriq_adapter import ExecutionOutcome, PlanContext
from agent.decisions import Decision, DecisionType
from approval import store
from approval.app import app


def test_hold_approve_resume(tmp_path, monkeypatch):
    monkeypatch.setenv("KAVALAN_APPROVAL_DB", str(tmp_path / "approval.db"))
    client = TestClient(app)

    held_id = store.add_held(trace_id="t1", tool="kavalan-payments.transfer_money",
                             args={"to_account": "family-beta", "amount": 4000000},
                             reason="above threshold")
    assert client.get("/pending").json()["pending"][0]["id"] == held_id
    page = client.get(f"/approve/{held_id}")
    assert page.status_code == 200 and f"Approve #{held_id}" in page.text

    res = client.post("/decision", json={"id": held_id, "approved": True})
    assert res.json() == {"id": held_id, "status": "approved"}

    executed = []

    class FakeAdapter:
        def declare_plan(self, *, goal, steps, user_email, prompt="", **kw):
            return PlanContext(goal=goal, steps=steps, trace_id="t2")

        def execute(self, *, mcp, action, params, plan, user_email):
            executed.append((mcp, action, params))
            return ExecutionOutcome(
                decision=Decision(DecisionType.ALLOWED, f"{mcp}.{action}",
                                  params, reason="approved retry allowed",
                                  trace_id="t2"),
                data={"entry_id": 9})

        def log_decision(self, decision):
            pass

    agent = KavalanAgent(adapter=FakeAdapter())
    out = agent.resume_held(held_id, "amma@example.com")
    assert executed and executed[0][1] == "transfer_money"
    assert "Done" in out or "Ho gaya" in out


def test_reject_never_executes(tmp_path, monkeypatch):
    monkeypatch.setenv("KAVALAN_APPROVAL_DB", str(tmp_path / "approval.db"))
    client = TestClient(app)
    held_id = store.add_held(trace_id="t3", tool="kavalan-payments.transfer_money",
                             args={"to_account": "x", "amount": 1}, reason="hold")
    assert client.post("/decision", json={"id": held_id, "approved": False}).json()[
        "status"] == "rejected"
    assert client.get("/pending").json() == {"pending": []}
