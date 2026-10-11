# Policy (plain language)

Canonical enforcement lives in the **ArmorIQ dashboard (Policies)** — this
file and `policy/kavalan_policy.yaml` are the human-readable mirror used for
review and the hackathon demo. Until a policy matches, ArmorIQ **fails
closed** (`no_matching_policy`).

## Defaults (config, not hardcoded logic)

- `AUTO_ALLOW_BILL_LIMIT_INR = 5_000`
- `HOLD_TRANSFER_ABOVE_INR = 5_000`
- `APPROVAL_WAIT_SECONDS = 60`

## Rules

1. **ALLOW — usual bills.** `pay_bill` to a **registered** payee with
   `amount <= Rs 5,000` runs immediately. Example: monthly TNEB electricity
   bill of ~Rs 1,200.
2. **HOLD — big or new.** Any `transfer_money` with `amount > Rs 5,000`, or
   **any** transfer/bill to a **new (unregistered) payee**, pauses until a
   family member approves via the approval page. On approval the agent
   resumes and **re-submits through ArmorIQ**; on rejection or timeout the
   action is refused (timeout is a refusal, never an allow).
3. **BLOCK — never.** `share_otp` / `share_credentials` (OTP/PIN/CVV sharing)
   is always denied, and `transfer_money` to a **non-allowlisted** account is
   denied — including when triggered by scammer words or a forwarded WhatsApp
   message (prompt injection). Blocked actions **never run**; do not retry.
4. **BLOCK — outside the plan.** Any tool call not in the declared intent
   plan for the current request fails via ArmorIQ plan verification, even if
   some policy would otherwise allow that tool.

## Notes for the dashboard author

- Scope rules to the exact registered MCP names (`kavalan-payments`,
  `kavalan-pharmacy`) and tool names; a name mismatch silently means no
  policy applies.
- Threshold policies read the **amount** argument — keep the field named
  `amount` (ArmorIQ scans `amount/value/total/price/cost`; e.g. a field named
  `total_cents` would be invisible to thresholds). Tool `amount` params are
  whole **rupees**; the sandbox ledger converts to paise internally.
- **Upgrade warning — thresholds are in rupees.** Write limits as
  `amount > 5000`, not `500000`. Any dashboard policy authored against the
  earlier paise-based scaffold must be edited to rupees **before** running
  this agent version: a stale `amount > 500000` rule would let a ₹40,000
  transfer through without a hold. Editing `policy/kavalan_policy.yaml`
  does not change the dashboard — update the policy there, then confirm
  with beat 2 (`Beta ko Rs 40,000 bhej do` must come back HELD).
- Cover **every** money-moving tool (`pay_bill` AND `transfer_money`); the
  model will otherwise reach for the uncovered sibling.
- Per-user limits differ by role (e.g. tier-1 family helper vs. account
  owner) — policy is looked up per `user_email`.
