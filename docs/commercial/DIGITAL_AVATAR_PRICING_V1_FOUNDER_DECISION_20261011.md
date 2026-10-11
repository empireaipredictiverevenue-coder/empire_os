# Empire Digital Avatar — Founder Pricing V1 decision reconciliation

**Decision occurred:** 2 October 2026, 22:29:17 UTC, earlier founder conversation.
**Recorded for EmpireOS:** 11 October 2026.
**Approval evidence reference:** `founder_approval:2026-10-02:digital_avatar_pricing_v1`
**Decision status:** **FOUNDER APPROVED — PRICE AND PACKAGING POLICY ONLY.**

The founder explicitly approved the exact Digital Avatar pricing/economics ladder on 2 October. This decision already existed before this engineering review. This document captures the prior founder decision; it is **not a new approval request or permission to charge customers**.

| Product | Monthly (USD) | Implementation fee | Avatars | Verified meetings/month | Proposed concurrency | Verified meeting overage |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Digital Avatar Copilot | $1,500 | $1,500 | 1 | 40 | 1 | $35 |
| Digital Avatar Workforce | $5,000 | $5,000 | 5 | 150 | 3 | $30 |
| Digital Avatar White-Label Workforce | $12,500 | $15,000 | 15 | 400 | 10 | $25 |

Founder policy also approves the *price-policy target* of 75% margin and minimum margin guardrail of 70%, and a **quote-led** enterprise recurring minimum of **$15,000/month**. Margin, acquisition cost and fulfilment cost are **not observed or independently verified**: the original model's cost ceilings are policy estimates, not real cost evidence.

This approval **permits the governed preparation/proposal of canonical product identities and PENDING versions**, scoped to price only. It does not enable any product to be sold or grant any data-base write without the separate exact governed DB activation/apply path.

## Explicit exclusions, retained without change

- No verified canonical Digital Avatar product, no catalogue version verification and no activation.
- No `binding_terms_ready`, customer acceptance, signed contract, tenant entitlement or checkout.
- No payment requests, USDT transfers, recognised revenue, advertisement, outbound, live meeting or avatar speech authority.
- No assertion of verified compute/inference/TTS/render/operations cost, meeting-duration distribution, concurrency capacity or validated margin.
- EmpireDB is the canonical first-party database, **not Supabase**.
- No reset/rebuild of Digital Avatar systems or repeated founder-pricing approval request.

## One-hit engineering consequence

The old unchecked line `FOUNDER APPROVAL REQUIRED: exact Digital Avatar pricing/economics ladder` is **administratively stale as to founder price decision**, but it lives in `docs/MASTER_REMAINING_CHECKLIST.md`, a shared file currently modified by another agent. Do **not** overwrite the file. Formal checklist closure still requires existing exact verification and checkpoint policy.

Reuse `empire_os.digital_avatar_pricing_economics_proposal.AvatarPricingPolicyProposal.as_founder_approved_price_candidate` for the price basis and the existing `empire_os.digital_avatar_commercial_packaging` identity registry. `empire_os.digital_avatar_approved_catalog_preview` creates three strictly dry-run payloads for the *existing* first-party EmpireDB identity/version RPC shapes; **no RPC is invoked**. Costs and margins are UNKNOWN in the proposed version payload; original policy ceiling values never masquerade as actual expenditure.

As of the catalogue snapshot inspected on 11 October 2026, it contained **86 products** and **zero Digital Avatar product identities**. Do not automatically submit proposals on that basis; revalidate live EmpireDB identities and acquire the separate governed write approval before any `register_commercial_product_identity` or `propose_commercial_product_version` call. If duplicates appear, fail closed and inspect the canonical product record rather than proposing another version.

Source policy contract: `docs/DIGITAL_AVATAR_PRICING_ECONOMICS_PROPOSAL_V1.md`; package contract: `docs/DIGITAL_AVATAR_COMMERCIAL_PACKAGING_DELTA_V1.md`.
**Next genuine engineering work:** independent observed meeting duration, real first-party fulfilment cost and concurrency capacity. No new pricing exercise.


## 11 October engineering acceptance

- Existing first-party catalog snapshot: **86** products, **0** matching canonical Avatar identity codes, as observed through read-only catalog snapshot.
- Existing package/pricing modules and existing EmpireDB `register_commercial_product_identity` / `propose_commercial_product_version` RPC payload schemas reused; **no RPC invoked**.
- The three price-only **DRY_RUN** candidates have exact prices, setup fees, avatars, meeting allowances, concurrency and overage; the pending version payloads carry **UNKNOWN** fulfilment/acquisition cost and **UNKNOWN** actual margin. Enterprise minimum is a quote-led policy, not a fourth product.
- The proposal preview is materialized only by an explicit one-shot command to `runtime/commercial_proposals/digital_avatar_approved_price_v1.json` (existing first-party runtime, no extra service). Other destination paths, duplicate product identities, catalog overwrite, unexpected changes and unapproved price references fail closed.
- The existing completion reconciliation recognises the exact previous price decision from the immutable preview and labels the old founder-gate row `FOUNDER_PRICE_POLICY_APPROVED_FORMAL_CLOSURE_PENDING`, **without marking the checklist DONE**. Other founder approval gates remain held. Pricing approval cannot count as a payment, cost verification or product verification.
- Regression proof: **333 passed** across Avatar, catalogue, price proposal and completion-monitor contracts (one existing Starlette/anyio deprecation warning). Strict-type admission retest **91 passed**; no failures.
- The canonical `docs/MASTER_REMAINING_CHECKLIST.md` is modified by another concurrent agent. Do not overwrite, reorder or check its approval row here; formal checklist mutation must meet its own independent closure gate.

**Do not repeat the founder approval exercise.** The next genuine work is real runtime cost/duration/concurrency proof and, separately, governed EmpireDB version proposals following an exact separate write gate.
