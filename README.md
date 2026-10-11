# Kavalan — voice guardian for elderly parents

Kavalan is a Flow State 2026 (ArmorIQ) hackathon scaffold. An AI agent
(Hindi / Tamil / English) pays bills, reorders medicines and books doctor
visits through **sandbox MCP servers**. Every tool call is governed by
**ArmorIQ** — runtime intent/policy enforcement for AI agents — with three
demonstrable outcomes, all enforced for real, never hardcoded:

| # | Beats | Outcome |
|---|-------|---------|
| 1 | "Bijli ka bill bhar do" — usual electricity bill, registered payee, under limit | **ALLOWED** |
| 2 | "Beta ko Rs 40,000 bhej do" — above threshold | **HELD**, then approved from the approval page |
| 3 | Scammer text / forwarded WhatsApp message tricks the agent into sharing an OTP | **BLOCKED** |

## Architecture sketch

```
voice (STT, stub) ──> agent ──> intent plan ──> ArmorIQ ──> MCP tool ──> SQLite sandbox ledger
  (TEXT mode first)   (agent/)   (capture_plan +     (capture/get token/   (mcp_servers/)
                                  intent token)       invoke; allow/hold/
                                                      block raised, never
                                                      returned as flags)
                                                 │
                                                 ▼
                                    approval service (approval/)
                                    family member approves HELD actions
                                    from their phone; agent resumes and
                                    re-submits through ArmorIQ
```

Every decision is logged to `logs/decisions.jsonl` (timestamp, tool, args,
decision, reason, trace id) and must also appear in the ArmorIQ dashboard
trace at `platform.armoriq.ai`. See `docs/ARCHITECTURE.md`.

**Hard rules (enforced by construction):**

1. All ArmorIQ SDK calls live in **one** module: `agent/armoriq_adapter.py`.
   Nothing else imports `armoriq_sdk`.
2. No simulated allow/block results anywhere. Decisions come from ArmorIQ
   exceptions / proxy enforcement. Tests may mock the **adapter**, never the
   SDK, and the app code path always goes through the adapter.
3. Sandbox only: fake SQLite ledger, no real UPI, bank or customer data.
4. Secrets only via `.env` (never committed). See `.env.example`.

## Setup

Requires Python 3.11+ and (preferably) `uv`.

```sh
cp .env.example .env        # fill in ARMORIQ_API_KEY from platform.armoriq.ai
make setup                  # uv sync (falls back to pip + venv)
make seed                   # seed payees, balance, prescriptions
make test                   # run the test suite
```

Manual equivalents on Windows without `make`:

```powershell
uv sync
uv run python scripts/seed.py
uv run pytest -q
```

## Run

```sh
make run-mcp          # payments MCP server (stdio)
make run-mcp-pharmacy # pharmacy MCP server (stdio)
make run-approval     # approval web service on :8000
make run-agent        # agent CLI, TEXT mode
make demo             # 3 scripted scenarios through the REAL pipeline
```

## Live ArmorIQ run (public tunnel for the MCP)

The ArmorIQ proxy executes tools on your MCP server-side, so it must reach
your MCP over a **public HTTPS URL** — `localhost` does not work. For local
development, expose the payments MCP (streamable-http on `:8001`, path
`/mcp`) with:

```sh
make tunnel           # cloudflared quick tunnel, no account needed
```

Copy the printed `https://<random>.trycloudflare.com` URL and register
`<url>/mcp` as the MCP URL in the ArmorIQ dashboard (MCP Servers → Add
Server). Restart the tunnel if the URL changes — the dashboard registration
must match exactly. (Alternative: `ngrok http 8001`, needs an authtoken.)

## ArmorIQ setup (dashboard)

1. Sign up at `platform.armoriq.ai`, generate an API key (`ak_live_…` /
   `ak_test_…`), put it in `.env` as `ARMORIQ_API_KEY`.
2. Register the MCP servers with the **exact** names in `.env`
   (`kavalan-payments`, `kavalan-pharmacy`).
3. Register the agent (`kavalan-guardian`).
4. Create the allow / hold / block policies in **Policies** (see
   `policy/kavalan_policy.yaml` — a human-readable mirror; the dashboard is
   canonical). Until a policy matches, ArmorIQ fails closed
   (`no_matching_policy`).
5. Approve HELD actions under **Approvals** (or the local
   `APPROVAL_BASE_URL` page, which the agent polls); observe everything under
   **Observability**.

Open doc questions are tracked in `docs/OPEN_QUESTIONS.md` and marked
`TODO(armoriq-docs)` in code.

## Demo script

See `docs/DEMO_SCRIPT.md` (90-second beats). Placeholder: beats 1–4 as listed
above, ending on the ArmorIQ dashboard traces.

## Layout

```
agent/          LLM loop, ArmorIQ adapter (only SDK touchpoint), language hooks
mcp_servers/    payments + pharmacy tools (FastMCP), SQLite sandbox ledger
approval/       FastAPI hold/approve service for family members
policy/         human-readable policy mirror (dashboard is canonical)
scripts/        seed + scripted demo scenarios (real pipeline)
tests/          tools, policy cases (adapter mocked), approval flow
docs/           architecture, policy, demo script, open ArmorIQ questions
```
