# Open questions about ArmorIQ docs

Read so far (2026-10-10/11): docs home, `platform/getting-started`,
`sdk/installation`, `sdk` overview, `sdk/client-initialization`,
`sdk/core-methods` + `capture-plan` / `get-intent-token` /
`policy-specification` / `invoke`, `sdk/mcp-directory` + `mcp-format`,
`sdk/configuration`, `sdk/error-handling`, `platform/policies` +
`policy-builder` + `enforcement`, `platform/mcp-servers` + `add-server`,
`platform/agents` + `add-agent`, `cookbook/adk-agent`, `armorpay` overview.
Plus installed `armoriq-sdk 0.6.10` source (`client.py`, `session.py`,
`models.py`). Dashboard at `platform.armoriq.ai` could not be inspected
(requires login).

Code places that depend on the answers below are marked `TODO(armoriq-docs)`.

## Resolved / mostly resolved

1. **Session API surface — RESOLVED (raw path chosen).** Verified in
   `client.py`: `client.for_user(email)` → scope; `scoped.start_session(
   SessionOptions(mode="sdk"))`; `session.start_plan([...])` /
   `session.check(tool, args)` / `session.await_approval(delegation_id,
   timeout, interval)` (async). For Kavalan's hand-rolled loop the raw
   `capture_plan → get_intent_token → invoke` path (all signatures verified
   against the installed SDK) is sufficient; sessions are not required.
2. **Hold/resume protocol — PARTLY RESOLVED.** `invoke()` raises
   `PolicyHoldException` carrying `delegation_context`; `await_approval()`
   is `async`. Resume = re-`invoke` after approval (possibly fresh token —
   default TTL is 60 s). Our sync adapter will need `asyncio` handling for
   `await_approval`; exact `delegation_context` shape still to be observed
   live.
3. **MCP onboarding + reachability — RESOLVED (tunnel needed).**
   `invoke()` POSTs to `{proxy}/invoke`; the **proxy executes the tool on
   the registered MCP URL server-side**. MCP format = JSON-RPC over HTTP,
   SSE framing, three methods (`initialize`, `tools/list`, `tools/call`),
   protocol `2024-11-05`, **public HTTPS URL required** — `localhost` will
   not work. Our FastMCP (mcp 1.x) `streamable-http` serves exactly `/mcp`,
   matching the cookbook ("URL with `/mcp` on the end"). Hence `make
   tunnel` (cloudflared → `:8001`). REMAINING: whether the proxy speaks
   stateful streamable-HTTP (session IDs) or needs stateless/JSON mode —
   to be observed live; FastMCP settings (`stateless_http`,
   `json_response`) give us knobs.
4. **Agent registration/binding — MOSTLY RESOLVED.** Binding is via
   `agent_id` in the token payload (`ArmorIQClient(agent_id=…)` or
   `AGENT_ID` env). Dashboard: Agents → Add Agent, name it
   `kavalan-guardian`. REMAINING: the wizard also asks for the agent's URL
   + framework (A2A/MCP auto-detect) — our agent is a CLI with no URL; may
   need the tunnel URL or a manual-config bypass.
5. **Threshold / hold / block policy authoring — OPEN (beats 2–3).** The
   generic Policy Builder only shows agent↔MCP edges, allowed-tools
   whitelists, IP/time/rate limits and priorities — no amount thresholds,
   no hold/block actions. ArmorPay has thresholds/velocity/recipient
   validation but targets its own pre-configured agent types (AP/Finance/
   Payroll). How (if at all) a custom agent expresses "hold transfer >
   Rs 5,000" / "always block share_otp" is unverified. For beat 1
   (ALLOWED) an allowed-tools policy is sufficient.
6. **Dashboard deep links + trace API — OPEN.** Paths seen in SDK errors:
   `platform.armoriq.ai/dashboard/api-keys`; cookbook references an
   **Approvals** section and **Observability**. Exact URLs + any trace API
   still to be confirmed in the live dashboard.
7. **`armoriq.yaml` + CLI — OPEN, low priority.** Raw-SDK construction
   works; `from_config()` not needed for Phase 2.
8. **SDK Observability setup — OPEN.** Assumed automatic via proxy; confirm
   traces appear without extra code.

## New questions from SDK-source reading (2026-10-11)

9. **Stateful vs stateless MCP transport.** Does the proxy handle
   streamable-HTTP session IDs, or must we serve stateless/JSON
   (`stateless_http=True`, `json_response=True`)? Observe the first live
   `invoke`; failure mode will tell us.
10. **Default-allow vs fail-closed contradiction.** `policies/enforcement`
    says "if no policy matches, access is allowed by default", while the
    cookbook says unconfigured calls fail with `no_matching_policy`. Our
    beat-1 policy will be explicit either way — but note the actual
    behavior observed and report it.
11. **Agent-wizard URL requirement.** Can a URL-less CLI agent be
    registered by name only, or must we supply a URL (tunnel?) and pick a
    framework?
12. **MCP auth for tunneled servers.** Wizard offers Auth Method (API
    Key); SDK sends per-MCP creds via `ARMORIQ_MCP_CREDENTIALS` /
    `X-Armoriq-MCP-Auth`. Start with auth "none" if allowed (sandbox);
    cookbook warns a public no-auth MCP is directly callable — acceptable
    for fake-ledger demo, revisit before any real data.
