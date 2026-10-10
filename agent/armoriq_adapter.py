"""Single wrapper around the ArmorIQ SDK.

This is the ONLY module in the codebase that may import ``armoriq_sdk``.
Everything else talks to ArmorIQ through :class:`ArmoriqAdapter`.

Verified SDK surface (https://docs.armoriq.ai, read 2026-10-10):
  - ``ArmorIQClient(api_key=...)`` (or ``ARMORIQ_API_KEY`` env)
  - ``client.for_user(email)`` — per-user scope for policy/audit attribution
  - ``client.capture_plan(llm, prompt, plan)`` with
    ``plan = {"goal": str, "steps": [{"action", "mcp", "params?", ...}]}``
  - ``client.get_intent_token(captured, policy?, validity_seconds?)``
  - ``client.invoke(mcp, action, token, params, ..., user_email=...)``
  - Failures RAISE: ``PolicyBlockedException`` (deny, do not retry),
    ``PolicyHoldException`` (needs human approval), ``IntentMismatchException``
    (action outside the declared plan), ``TokenExpiredException`` (re-mint),
    ``InvalidTokenException`` / ``MCPInvocationException``.

Hard rule: NEVER return a simulated allow/block. If the SDK or API key is
missing, fail closed (raise) — there is no code path that yields ALLOWED
without ArmorIQ.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agent.decisions import Decision, DecisionType

try:  # The SDK is a hard dependency in pyproject; guard anyway (fail closed).
    from armoriq_sdk import (
        ArmorIQClient,
        IntentMismatchException,
        InvalidTokenException,
        MCPInvocationException,
        PolicyBlockedException,
        PolicyHoldException,
        TokenExpiredException,
    )
    _SDK_AVAILABLE = True
    _SDK_IMPORT_ERROR: Exception | None = None
except Exception as exc:  # pragma: no cover — depends on install state
    ArmorIQClient = None  # type: ignore[assignment]
    IntentMismatchException = InvalidTokenException = Exception  # type: ignore
    MCPInvocationException = PolicyBlockedException = Exception  # type: ignore
    PolicyHoldException = TokenExpiredException = Exception  # type: ignore
    _SDK_AVAILABLE = False
    _SDK_IMPORT_ERROR = exc


@dataclass
class PlanContext:
    """A declared intent plan plus its minted token (opaque to callers)."""

    goal: str
    steps: list[dict[str, Any]]
    captured: Any = None
    token: Any = None
    trace_id: str = ""


@dataclass
class ExecutionOutcome:
    decision: Decision
    data: Any = None
    held_info: dict[str, Any] = field(default_factory=dict)


class ArmoriqNotConfiguredError(RuntimeError):
    """Raised when ArmorIQ cannot be reached — fail closed, never simulate."""


class ArmoriqAdapter:
    """All ArmorIQ interaction goes through here. Nothing else imports the SDK."""

    def __init__(
        self,
        api_key: str | None = None,
        llm: str | None = None,
        decision_log: str | os.PathLike | None = None,
    ) -> None:
        self.api_key = api_key or os.environ.get("ARMORIQ_API_KEY", "")
        self.llm = llm or os.environ.get("LLM_MODEL", "kavalan-text-1")
        self.log_path = Path(
            decision_log or os.environ.get("KAVALAN_DECISION_LOG", "logs/decisions.jsonl")
        )
        self._client: Any = None

    # -- lifecycle ------------------------------------------------------
    def _require_client(self) -> Any:
        if not _SDK_AVAILABLE:
            raise ArmoriqNotConfiguredError(
                f"armoriq-sdk is not importable ({_SDK_IMPORT_ERROR}); "
                "install it and set ARMORIQ_API_KEY. Refusing to decide locally."
            )
        if not self.api_key:
            raise ArmoriqNotConfiguredError(
                "ARMORIQ_API_KEY is not set. Refusing to decide locally."
            )
        if self._client is None:
            self._client = ArmorIQClient(api_key=self.api_key)
        return self._client

    # -- plan -----------------------------------------------------------
    def declare_plan(
        self,
        *,
        goal: str,
        steps: list[dict[str, Any]],
        user_email: str,
        prompt: str = "",
        validity_seconds: float = 300.0,
        policy: dict[str, Any] | None = None,
        trace_id: str = "",
    ) -> PlanContext:
        """Capture a plan and mint its intent token. One plan per user request."""
        client = self._require_client()
        plan = {"goal": goal, "steps": steps}
        captured = client.capture_plan(
            llm=self.llm, prompt=prompt or goal, plan=plan
        )
        if policy is None:
            token = client.get_intent_token(
                captured, validity_seconds=validity_seconds
            )
        else:
            token = client.get_intent_token(
                captured, policy=policy, validity_seconds=validity_seconds
            )
        _ = user_email  # per-request attribution is passed on invoke(); sessions
        # TODO(armoriq-docs): confirm whether raw-SDK flows should use
        # client.for_user(email).start_session()/start_plan()/check() instead
        # of capture_plan/get_intent_token directly (see OPEN_QUESTIONS.md Q1).
        return PlanContext(goal=goal, steps=steps, captured=captured,
                           token=token, trace_id=trace_id)

    # -- execute --------------------------------------------------------
    def execute(
        self,
        *,
        mcp: str,
        action: str,
        params: dict[str, Any],
        plan: PlanContext,
        user_email: str,
    ) -> ExecutionOutcome:
        """Invoke one planned tool through ArmorIQ; map SDK signals to Decision.

        TODO(armoriq-docs): confirm the hold/resume protocol — currently a
        PolicyHoldException maps to HELD carrying delegation context, and
        resume means re-invoke (fresh token) after the approval is recorded
        (see OPEN_QUESTIONS.md Q2).
        """
        client = self._require_client()
        try:
            result = client.invoke(
                mcp, action, plan.token, params, user_email=user_email
            )
        except PolicyHoldException as exc:  # type: ignore[misc]
            outcome = ExecutionOutcome(
                decision=Decision(
                    DecisionType.HELD, f"{mcp}.{action}", params,
                    reason=f"held for family approval: {exc}",
                    trace_id=plan.trace_id),
                held_info={"delegation_context": getattr(exc, "delegation_context", ""),
                           "metadata": getattr(exc, "metadata", {})},
            )
        except PolicyBlockedException as exc:  # type: ignore[misc]
            outcome = ExecutionOutcome(
                decision=Decision(
                    DecisionType.BLOCKED, f"{mcp}.{action}", params,
                    reason=f"blocked by policy: {exc}",
                    trace_id=plan.trace_id),
            )
        except IntentMismatchException as exc:  # type: ignore[misc]
            # Tool call outside the declared plan — fail closed.
            outcome = ExecutionOutcome(
                decision=Decision(
                    DecisionType.BLOCKED, f"{mcp}.{action}", params,
                    reason=f"outside declared plan (intent mismatch): {exc}",
                    trace_id=plan.trace_id),
            )
        except TokenExpiredException:
            # Re-mint once on the same captured plan, then retry once.
            token = client.get_intent_token(plan.captured)
            plan.token = token
            return self.execute(mcp=mcp, action=action, params=params,
                                plan=plan, user_email=user_email)
        except (InvalidTokenException, MCPInvocationException) as exc:  # type: ignore[misc]
            outcome = ExecutionOutcome(
                decision=Decision(
                    DecisionType.BLOCKED, f"{mcp}.{action}", params,
                    reason=f"invocation failed closed: {type(exc).__name__}: {exc}",
                    trace_id=plan.trace_id),
            )
        else:
            data = result.get("result", result) if isinstance(result, dict) else result
            outcome = ExecutionOutcome(
                decision=Decision(
                    DecisionType.ALLOWED, f"{mcp}.{action}", params,
                    reason="allowed by ArmorIQ; tool executed",
                    trace_id=plan.trace_id),
                data=data,
            )
        self.log_decision(outcome.decision)
        return outcome

    # -- audit ----------------------------------------------------------
    def log_decision(self, decision: Decision) -> None:
        """Append one JSONL row (timestamp, tool, args, decision, reason, trace id)."""
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(decision.to_log_row(), ensure_ascii=False) + "\n")
