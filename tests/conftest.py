import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(autouse=True)
def _isolated_storage(tmp_path, monkeypatch):
    """Keep tests off the real data/ + logs/ dirs."""
    monkeypatch.setenv("KAVALAN_DB", str(tmp_path / "kavalan.db"))
    monkeypatch.setenv("KAVALAN_APPROVAL_DB", str(tmp_path / "approval.db"))
    monkeypatch.setenv("KAVALAN_DECISION_LOG", str(tmp_path / "decisions.jsonl"))
