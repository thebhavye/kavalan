# Architecture

## Flow

```
                    ┌──────────────┐
 mic / phone ──STT──▶              │   1. build plan {goal, steps[]} from user text
 (stub: ElevenLabs)│     AGENT     │   2. adapter.capture_plan(llm, prompt, plan)
 TEXT mode first   │  (agent/)     │   3. adapter.get_intent_token(captured, policy?, validity)
                    └──────┬───────┘   4. per step: adapter.invoke(mcp, action, token, params, user_email)
                           │                       ├── success ──────────▶ ALLOWED → tool runs
                           │                       ├── PolicyHoldException → HELD → approval store + URL
                           │                       ├── PolicyBlockedException / IntentMismatchException
                           │                       │                       → BLOCKED → never runs
                           ▼                       └── every outcome → logs/decisions.jsonl + dashboard trace
 ┌────────────────────────────────────────────────────────────────────────┐
 │ APPROVAL SERVICE (approval/, FastAPI)                                  │
 │ HELD action → row in approval.db → family member opens                 │
 │ {APPROVAL_BASE_URL}/approve/{id} on phone → Approve/Reject →           │
 │ agent resumes ONLY after approval is recorded, then re-submits         │
 │ through ArmorIQ (fresh token; never executes on local state alone).    │
 └────────────────────────────────────────────────────────────────────────┘

 MCP SERVERS (mcp_servers/, FastMCP from the official MCP Python SDK)
 ├── payments:  pay_bill, transfer_money, list_payees, get_balance, share_otp (*)
 └── pharmacy:  reorder_medicine, book_doctor_visit, list_prescriptions
                      │
                      ▼
              SQLite sandbox ledger (mcp_servers/common/db.py)
              fake money only — no real UPI / bank / customer data.

 (*) share_otp exists ONLY as a honeypot tool the agent can be tricked into
     calling. It performs no real action even if executed; ArmorIQ policy
     must always deny it.
```

## Enforcement points (all inside `agent/armoriq_adapter.py`)

The adapter is the **only** module that imports `armoriq_sdk` (verified names
from https://docs.armoriq.ai — see `docs/OPEN_QUESTIONS.md` for the rest):

- `ArmorIQClient(api_key=…)` — one key per process (`ARMORIQ_API_KEY`).
- `client.for_user(email)` — per-user scope; policy/audit attributed per email.
- `client.capture_plan(llm, prompt, plan)` — plan shape
  `{goal: str, steps: [{action, mcp, params?, description?, metadata?}]}`.
  MCP names must **exactly** match dashboard registration.
- `client.get_intent_token(captured, policy?, validity_seconds?)` — inline
  `policy` is `{allow: [...globs], deny: [...globs], …}` and only further
  constrains one token; stored dashboard policies apply automatically.
- `client.invoke(mcp, action, token, params, …, user_email=…)` — verified
  against the plan at the proxy **before** the tool runs.

Failures **raise**, they do not return flags: `PolicyBlockedException`
(deny — do not retry), `PolicyHoldException` (wait for human, then retry),
`IntentMismatchException` (action outside the declared plan — fail closed),
`TokenExpiredException` (re-mint). The adapter translates these into the
`Decision` enum (`agent/decisions.py`) and logs each to JSONL.

## Key invariants

1. The agent **declares a plan per user request** before executing anything;
   tool calls outside that plan fail via ArmorIQ (`IntentMismatchException`).
2. MCP servers hold **no permission logic** — they don't know who is asking.
3. The app **fails closed**: no API key / no SDK / no matching policy ⇒ the
   adapter raises instead of deciding. There is deliberately no code path
   that returns ALLOWED without ArmorIQ.
4. Untrusted text (scammer call transcript, forwarded WhatsApp message) is
   wrapped as data (`agent/untrusted_input.py`) and fed to the agent so the
   injection demo exercises the real pipeline: the model may be persuaded,
   but ArmorIQ still blocks.

## Processes (scaffold)

| Process | Command | Notes |
|---|---|---|
| payments MCP | `make run-mcp` | stdio transport (scaffold) |
| pharmacy MCP | `make run-mcp-pharmacy` | stdio transport (scaffold) |
| approval web | `make run-approval` | FastAPI on `:8000` |
| agent CLI | `make run-agent` | TEXT mode; voice is stubbed |

TODO(armoriq-docs): confirm whether production MCP servers must sit behind
the ArmorIQ proxy at public HTTPS URLs, and the exact MCP onboarding format
(see `docs/OPEN_QUESTIONS.md` Q3).
