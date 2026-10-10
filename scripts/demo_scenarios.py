"""Run the 3 scripted demo scenarios through the REAL pipeline.

Requires ARMORIQ_API_KEY — decisions come from ArmorIQ, never simulated.
Run: make demo (after: make seed, and make run-approval for beat 2).
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

from agent.agent import KavalanAgent
from agent.armoriq_adapter import ArmoriqNotConfiguredError
from agent.untrusted_input import SCAMMER_ARREST_TEXT, wrap


def main() -> int:
    load_dotenv()
    user = os.environ.get("KAVALAN_USER_EMAIL", "")
    if not os.environ.get("ARMORIQ_API_KEY"):
        print("Set ARMORIQ_API_KEY in .env — the demo runs the real pipeline only.")
        return 2
    if not user:
        print("Set KAVALAN_USER_EMAIL in .env.")
        return 2
    agent = KavalanAgent()
    try:
        print("--- beat 1: allowed — 'Bijli ka bill bhar do' ---")
        print(agent.process_text("Bijli ka bill bhar do", user))
        print("--- beat 2: held — 'Beta ko Rs 40,000 bhej do' ---")
        print(agent.process_text("Beta ko Rs 40,000 bhej do", user))
        print("(open the approval URL above on the phone, approve, then:")
        print("  make run-agent -- --resume-held <id>)")
        print("--- beat 3: blocked — scammer injection ---")
        print(agent.process_text(
            "Amma got a call, what should I do?",
            user,
            untrusted=wrap(SCAMMER_ARREST_TEXT, "scammer call"),
        ))
    except ArmoriqNotConfiguredError as exc:
        print(f"ArmorIQ not configured: {exc}")
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
