# Open questions about ArmorIQ docs

Read so far (2026-10-10): docs home, `platform/getting-started`,
`sdk/installation`, `sdk` overview, `sdk/client-initialization`,
`sdk/core-methods` + `capture-plan` / `get-intent-token` /
`policy-specification` / `invoke`, `sdk/mcp-directory`, `sdk/configuration`,
`sdk/error-handling`, `platform/policies`, `cookbook/adk-agent`.
Dashboard at `platform.armoriq.ai` could not be inspected (requires login).

Code places that depend on the answers below are marked `TODO(armoriq-docs)`.

1. **Session API surface (Python, raw SDK).** `client-initialization` shows
   `scope = client.for_user(email)` then `session = scope.start_session()`
   with `session.start_plan([...])` / `session.check(...)`, and
   `error-handling` mentions `await_approval` (sessions) and
   `invoke_with_policy`/`invokeWithPolicy` (polling). Signatures, return
   types and which one a non-framework (hand-rolled loop) agent should use
   are not on the fetched pages. → affects `agent/armoriq_adapter.py`.
2. **Hold/resume protocol.** After `PolicyHoldException`, where is the hold
   approved — dashboard **Approvals** only, or an API we should poll from the
   approval service? What identifies the hold (`delegation_context` shape)?
   Does resume mean plain re-`invoke` (possibly with a fresh token, given
   the 60 s default TTL), or a dedicated confirm call? → affects
   `approval/` + adapter resume path.
3. **MCP onboarding format for proxy-routed tools.** `mcp-directory` covers
   registering name + HTTPS URL; the cookbook deploys the MCP publicly and
   the agent calls it directly with enforcement at the agent layer. For
   Kavalan, must our FastMCP servers be publicly reachable, or does
   `invoke()` proxy to them (and if so, what is the exact
   [MCP Format Requirements](https://docs.armoriq.ai/sdk/mcp-directory/mcp-format)
   page content — tools/list over StreamableHTTP, auth/credentials shape)?
4. **Agent registration for raw-SDK users.** The cookbook registers agent
   name `ops-copilot` via dashboard and passes `agentName` to the ADK
   adapter; the raw `ArmorIQClient` constructor takes no `agent_id`
   (deprecated). How is the agent name bound for raw-SDK usage
   (`armoriq.yaml` identity? dashboard convention?) so policies scope
   correctly? → affects `.env` (`ARMORIQ_AGENT_NAME`) + `armoriq.yaml` plans.
5. **Threshold / allowlist policy authoring.** How are "amount > Rs 5,000",
   "registered vs new payee", and "non-allowlisted account" expressed in
   Policy Builder / Policy Studio / OPA Engine — and can thresholds read
   tool params beyond the scanned `amount/value/total/price/cost` names?
   (Cookbook warns custom amount field names are invisible.)
6. **Dashboard deep links + trace API.** Exact paths for Observability /
   Approvals / Policies, and whether traces can be queried programmatically
   for the demo's "show dashboard traces" beat.
7. **`armoriq.yaml` + CLI for this project.** Should we commit an
   `armoriq.yaml` (via `armoriq init`) and use `from_config()`? Schema shows
   required `identity.user_id`/`agent_id` which conflicts with the newer
   `for_user(email)` model — which wins?
8. **SDK Observability setup.** What (if any) code is needed so our runs
   appear in dashboard traces — automatic via proxy, or explicit
   observability SDK calls?
