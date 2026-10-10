"""Decision types. Values are produced ONLY by the ArmorIQ adapter —
no other module may invent them."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
import time
import uuid


class DecisionType(str, Enum):
    ALLOWED = "ALLOWED"
    HELD = "HELD"
    BLOCKED = "BLOCKED"


@dataclass
class Decision:
    decision: DecisionType
    tool: str
    args: dict[str, Any] = field(default_factory=dict)
    reason: str = ""
    trace_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    timestamp: float = field(default_factory=time.time)

    def to_log_row(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "tool": self.tool,
            "args": self.args,
            "decision": self.decision.value,
            "reason": self.reason,
            "trace_id": self.trace_id,
        }
