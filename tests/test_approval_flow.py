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
                             args={"to_account": "family-beta", "amount": 40000},
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


def test_legacy_paise_row_is_never_resumed(tmp_path, monkeypatch):
    """A row held before amounts switched to rupees must not replay at 100x."""
    import sqlite3

    db = tmp_path / "approval.db"
    monkeypatch.setenv("KAVALAN_APPROVAL_DB", str(db))
    # Pre-upgrade DB: no args_version column, amount in paise.
    legacy = sqlite3.connect(db)
    legacy.executescript(
        "CREATE TABLE held_actions (id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " created_at REAL NOT NULL, decided_at REAL, trace_id TEXT NOT NULL,"
        " tool TEXT NOT NULL, args_json TEXT NOT NULL DEFAULT '{}',"
        " reason TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'pending');"
        "INSERT INTO held_actions (created_at, trace_id, tool, args_json, status)"
        " VALUES (0, 'old', 'kavalan-payments.transfer_money',"
        " '{\"to_account\": \"family-beta\", \"amount\": 4000000}', 'approved');")
    legacy.commit()
    legacy.close()

    row = store.get_held(1)
    assert row["args_version"] == 1

    class NeverCalled:
        def declare_plan(self, **kw):
            raise AssertionError("legacy row must not reach ArmorIQ")

        execute = declare_plan

    out = KavalanAgent(adapter=NeverCalled()).resume_held(1, "amma@example.com")
    assert "not executing" in out

    # New rows are written at the current version and stay resumable.
    new_id = store.add_held(trace_id="t", tool="kavalan-payments.transfer_money",
                            args={"amount": 40000}, reason="hold")
    assert store.get_held(new_id)["args_version"] == store.ARGS_VERSION


def test_concurrent_first_migrations_do_not_collide(tmp_path, monkeypatch):
    """The loser of a migration race re-checks under the lock and skips ALTER."""
    import sqlite3

    db = tmp_path / "approval.db"
    legacy = sqlite3.connect(db)
    legacy.execute(
        "CREATE TABLE held_actions (id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " created_at REAL NOT NULL, decided_at REAL, trace_id TEXT NOT NULL,"
        " tool TEXT NOT NULL, args_json TEXT NOT NULL DEFAULT '{}',"
        " reason TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'pending')")
    legacy.commit()
    legacy.close()

    winner, loser = sqlite3.connect(db), sqlite3.connect(db)
    for conn in (winner, loser):
        conn.row_factory = sqlite3.Row
    store._migrate(winner)

    # The loser's unlocked fast-path check ran before the winner committed,
    # so it reports "missing" once; the locked re-check must see the truth.
    real = store._has_args_version
    calls = []

    def stale_then_real(conn):
        calls.append(conn)
        return False if len(calls) == 1 else real(conn)

    monkeypatch.setattr(store, "_has_args_version", stale_then_real)
    store._migrate(loser)  # must not raise "duplicate column name"
    assert len(calls) == 2  # fast path said missing; locked re-check ran
    assert real(loser)
    winner.close()
    loser.close()
