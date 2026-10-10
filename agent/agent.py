"""Kavalan agent loop (TEXT mode first).

Builds an intent plan per user request, declares it through the ArmorIQ
adapter, then executes each step through the adapter. The agent NEVER decides
allow/hold/block itself — it only reacts to the adapter's Decisions.

TODO: replace the keyword plan builder with an LLM call (LLM_API_KEY), and
route execution via ArmorIQ proxy -> registered MCP servers (currently the
adapter's invoke() result carries the tool outcome; see TODO(armoriq-docs)
in armoriq_adapter.py re: proxy routing to local MCP servers).
"""
from __future__ import annotations

import os
import re
import uuid

from agent.armoriq_adapter import ArmoriqAdapter, PlanContext
from agent.decisions import DecisionType
from agent.language import detect_language, reply
from agent.untrusted_input import UntrustedContent
from approval import store as approval_store

AMOUNT_RE = re.compile(r"(?:rs\.?|₹)\s*([\d,]+)", re.IGNORECASE)

BILL_WORDS = ("bill", "bijli", "electricity", "tneb", "bhar", "pay")
TRANSFER_WORDS = ("bhej", "transfer", "send", "beta", "son", "payee")
OTP_WORDS = ("otp", "pin", "cvv", "digital arrest", "arrest", "cbi", "share")
MEDICINE_WORDS = ("medicine", "dawai", "tablet", "reorder", "pharmacy", "marunthu")
DOCTOR_WORDS = ("doctor", "appointment", "visit", "clinic", "hospital")

DEFAULT_BILL_PAISA = 120_000  # Rs 1,200 typical TNEB bill (scaffold default)


def parse_amount_paise(text: str) -> int | None:
    match = AMOUNT_RE.search(text)
    if not match:
        return None
    return int(match.group(1).replace(",", "")) * 100


class KavalanAgent:
    def __init__(self, adapter: ArmoriqAdapter | None = None,
                 approval_base_url: str | None = None) -> None:
        self.adapter = adapter or ArmoriqAdapter()
        self.base_url = (approval_base_url
                         or os.environ.get("APPROVAL_BASE_URL", "http://127.0.0.1:8000"))
        self.mcp_payments = os.environ.get("ARMORIQ_MCP_PAYMENTS", "kavalan-payments")
        self.mcp_pharmacy = os.environ.get("ARMORIQ_MCP_PHARMACY", "kavalan-pharmacy")

    # -- planning (scaffold: keyword rules; TODO: LLM) -------------------
    def build_plan(self, text: str) -> tuple[str, list[dict]]:
        lowered = text.lower()
        if any(w in lowered for w in OTP_WORDS):
            otp = re.search(r"\b(\d{4,8})\b", text)
            return ("share received OTP code", [{
                "action": "share_otp",
                "mcp": self.mcp_payments,
                "params": {"otp": otp.group(1) if otp else "",
                           "channel": "phone"},
            }])
        if any(w in lowered for w in TRANSFER_WORDS):
            amount = parse_amount_paise(text) or 0
            return ("send money to family member", [{
                "action": "transfer_money",
                "mcp": self.mcp_payments,
                "params": {"to_account": "family-beta",
                           "amount": amount, "note": text[:120]},
            }])
        if any(w in lowered for w in BILL_WORDS):
            amount = parse_amount_paise(text) or DEFAULT_BILL_PAISA
            return ("pay electricity bill", [{
                "action": "pay_bill",
                "mcp": self.mcp_payments,
                "params": {"payee_id": "tneb-electricity", "amount": amount},
            }])
        if any(w in lowered for w in MEDICINE_WORDS):
            return ("reorder medicine", [{
                "action": "reorder_medicine",
                "mcp": self.mcp_pharmacy,
                "params": {"prescription_id": "rx-metformin", "quantity": 1},
            }])
        if any(w in lowered for w in DOCTOR_WORDS):
            return ("book doctor visit", [{
                "action": "book_doctor_visit",
                "mcp": self.mcp_pharmacy,
                "params": {"doctor": "Dr. Meenakshi", "slot": "tomorrow 10am"},
            }])
        return ("unknown request", [])

    # -- main entry ------------------------------------------------------
    def process_text(self, text: str, user_email: str,
                     untrusted: UntrustedContent | None = None) -> str:
        lang = detect_language(text)
        prompt = text
        if untrusted is not None:
            prompt = f"{text}\n{untrusted.as_context()}"
        goal, steps = self.build_plan(prompt)
        if not steps:
            return reply("blocked", lang, reason="I did not understand that yet.")
        trace_id = uuid.uuid4().hex[:12]
        plan = self.adapter.declare_plan(
            goal=goal, steps=steps, user_email=user_email,
            prompt=prompt, trace_id=trace_id)
        return self._run_plan(plan, user_email, lang)

    def _run_plan(self, plan: PlanContext, user_email: str, lang: str) -> str:
        details: list[str] = []
        for step in plan.steps:
            outcome = self.adapter.execute(
                mcp=step["mcp"], action=step["action"],
                params=step.get("params", {}), plan=plan, user_email=user_email)
            decision = outcome.decision
            if decision.decision == DecisionType.ALLOWED:
                details.append(f"{step['action']}: {outcome.data}")
            elif decision.decision == DecisionType.HELD:
                held_id = approval_store.add_held(
                    trace_id=decision.trace_id, tool=decision.tool,
                    args=decision.args, reason=decision.reason)
                url = f"{self.base_url}/approve/{held_id}"
                return reply("held", lang, url=url)
            else:
                return reply("blocked", lang, reason=decision.reason)
        return reply("allowed", lang, detail="; ".join(details) if details else "ok")

    # -- held-action resume ----------------------------------------------
    def resume_held(self, held_id: int, user_email: str) -> str:
        """Resume a HELD action ONLY after approval is recorded, via ArmorIQ."""
        row = approval_store.get_held(held_id)
        if row is None:
            return f"unknown held action: {held_id}"
        if row["status"] != approval_store.STATUS_APPROVED:
            return f"held action {held_id} is {row['status']} — not executing."
        mcp, _, action = row["tool"].partition(".")
        trace_id = uuid.uuid4().hex[:12]
        plan = self.adapter.declare_plan(
            goal=f"approved retry of {row['tool']}",
            steps=[{"action": action, "mcp": mcp, "params": row["args"]}],
            user_email=user_email,
            prompt=f"family-approved retry of held action {held_id}",
            trace_id=trace_id)
        lang = detect_language(row["reason"])
        return self._run_plan(plan, user_email, lang)
