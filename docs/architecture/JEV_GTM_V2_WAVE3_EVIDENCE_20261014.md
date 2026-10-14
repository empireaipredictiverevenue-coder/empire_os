# JEV GTM V2 — Wave 3 First-Party Integration Evidence

Date: 2026-10-14
Worktree: `/home/ubuntu/empire_worktrees/jev_gtm_v2_20261014`
Branch: `feature/jev-gtm-v2-20261014`
Prior verified commit: `7c87fa71`
Mode: OBSERVE; no outbound, payment, fulfilment, schema migration, service restart or production feature activation.

## Existing production contracts inspected

- `empire_os.economic_signal_reader.read_economic_signals` is the existing trusted Economic Signal Fabric reader. It derives tenant identity through the authenticated `public.empire_current_tenant_id()` function and reads `public.empire_read_economic_signals(entity_id, as_of)`.
- Canonical source families are **revenue_leak, idle_asset, market_gap, idle_waste**. They are not synonyms for a buying request or commercial approval.
- Accepted evidence includes canonical tenant/entity/binding, source ID, observed timestamp, evidence references and original economic signal type. The canonical reader already checks scope, metadata, freshness and duplicate rows.
- `empire_os.revenue_crm_channel_evidence` remains the authority for channel consent/suppression and does not establish email clearance from the available suppression-hit-only reader.
- `tools/laya_node/server.mjs` serves local `/v1/systemone` via `@receptron/laya`; its installed package source explicitly implements Choice, Score (ordered rubric), and Noul (probability of true), even though Empire's Python adapter previously supported only Choice.

## Implemented

### Trusted economic-research bridge
`empire_os/jev_gtm_canonical_economic_bridge.py`

- Reuses existing authenticated economic reader, not a new database query or login.
- Verifies the active transaction is READ ONLY using `SHOW transaction_read_only` before canonical reader calls.
- Does not accept caller-provided tenant identity, infer a new entity binding from an empty source or inspect contacts or mailbox bodies.
- Preserves all four economic source semantics and bounded, dated provenance; rejects unsupported or cross-tenant evidence.
- Returns research evidence only with `commercial_prospect_verified=false`, `buyer_intent_verified=false`, `suppression_clearance_verified=false`, `outbound_approved=false`.
- A controlled unit-test cursor validates this code contract, **not a live EmpireDB reading**. A privileged live aggregate read was previously blocked by the remote tool; it was not bypassed.

### Founder read-only evidence projection
`empire_os/jev_gtm_founder_review.py`

- Produces a small no-PII status packet with per-family economic signal counts and a versioned fingerprint for later integration into the existing Founder Console.
- No new endpoint is published; any frontend route must reuse existing authenticated founder session and approved reader.
- Does not claim verified revenue, qualified buyers or contact clearance.

### All three native local Laya primitives
`empire_os/typed_decision_batch.py`, `empire_os/laya_http_provider.py`

- Choice: named classes, per-class distribution and model-reported confidence.
- Score: ordered levels, expected ordinal score, probability distribution and uncertainty. The native local scale is always **0 to n-1**; mismatched scales fail before model invocation.
- Noul: model probability of true. Treated as **raw model output, not calibrated probability of purchase**.
- Multi-question shared-state forward pass, schema validation, distribution normalization and score/distribution consistency; shadow only.
- Backward-compatible older single-Choice adapter remains unchanged.

A real, synthetic-only three-question inference against the installed local sidecar succeeded, returning:
- Choice: `software`, class probability `0.9887`.
- Score: `1.4708` on a 0–3 scale.
- Noul: `0.1091` for the question asking whether an explicit question exists in the text.
- Latency: `1780.126 ms`, one batch, `shadow_only=true`, `execution_authority=none`.

**Critical finding:** The Noul result looks poorly aligned with the synthetic example. The local model supports the primitive mechanically but is **not approved for buyer intent, unsubscribe, outreach or commercial routing** without independent task-specific calibration. Class probabilities, model confidence and likelihood of an actual purchase are different quantities.

## Tests and gates

Focused tests:
- `tests/test_jev_gtm_canonical_economic_bridge.py`
- `tests/test_jev_gtm_founder_review.py`
- `tests/test_laya_native_primitives_v2.py`
- Existing `tests/test_economic_signal_reader.py`, `tests/test_laya_http_batch_v2.py`, `tests/test_laya_http_provider.py`, `tests/test_jev_gtm_v2.py`

All tests use synthetic fixtures except the explicitly described local inference compatibility check. Neither fake DB cursors nor fictional buyer messages are production proof.

## Remaining activation requirements

1. Authorised, authenticated real EmpireDB reader invocation under a correctly scoped read-only session; live data counts not yet verified.
2. Exact tenant-bound buyer/contact/reply linkage reader through existing CRM security, distinct from Economic Signal Fabric. Do not treat an economic source as a buyer dataset.
3. Independent labels and model shadow comparisons, especially Noul calibration, Score ordinal quality and high-risk false negatives.
4. Actual founder-console route integration and final full release gauntlet, respecting other teams' changes.
5. First real commercial review packets and controlled promotion by existing founder/outbound policy; zero external actions automatically.

No new scheduler, DB role, subscription or duplicate runtime was created.
