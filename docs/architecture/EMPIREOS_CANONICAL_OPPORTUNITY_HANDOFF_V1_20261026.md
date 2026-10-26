# EmpireOS — Exact-Record Opportunity Handoff V1

**26 October 2026 | Release candidate, read-only and no direct database activation**

## Objective
Continue the **original** EmpireOS/EmpireDB architecture and join upstream Scout/JEV/Opportunity Factory research to the downstream Smart CRM, buyer intake, fulfilment, order/settlement and Economic Memory *without inventing an identity link*. The previous cohesion view (PR #114) monitors nine whole-system source snapshots but aggregates cannot verify that a real customer received one exact opportunity. This increment makes each real Opportunity Factory candidate individually reviewable within the existing revenue-completion supervisor.

## Verified source and schema facts
- Existing Factory production file: `runtime/opportunity_factory/intake_latest.json`, batch schema `empire.opportunity_factory_intake_batch.v1`.
- Factory rows use `opportunity_key` as a **research identifier**, have source families/URLs in `evidence_refs`, and may include `opportunity_id` and `tenant_id`. Those latter fields currently were NULL across the observed live batch and `factory_ready_count=0`.
- Canonical opportunity DB table: `public.gtm_opportunities(id UUID)` (EmpireDB migration 002). This is not the same thing as an inferred research key.
- Tenant scope is held in `public.tenant_business_entity_bindings(tenant_id,entity_id,binding_kind,evidence_ref,...)` (EmpireDB migration 037). A table row establishes an allowed tenant relationship, *not* authority to send, charge or fulfil; resolution requires the existing trusted context and reader.
- The existing `empire_os.economic_signal_tenant_binding.resolve_tenant_entity_binding` is an actual read-only canonical resolver. This increment does **not** call it for a non-existent factory `entity_id`, fabricate that ID, or apply held Predictive Revenue custody migrations (070–073).

## New original-chain feature
- `empire_os/opportunity_canonical_handoff_review.py`: a bounded, read-only per-candidate review. Validates a complete, non-executing, time-current source batch, exact opportunity keys, source ref shapes and distinct keys, Factory counts, identity fields, and refuses revenue promotion.
- Outputs deterministic `research_review:<hash>` for idempotent *review only*, NOT a canonical GTM opportunity ID. Existing Factory records missing authenticated tenant/entity/DB row receipts cannot progress.
- Maps every candidate to an original owner/action: **OpportunityFactory → COMPLETE_REAL_FACTORY_VALIDATION**, or (once Factory itself reports ready) **CanonicalIdentity / SmartCRM → VERIFY_EXISTING_EMPIREDB_GTM_ENTITY_TENANT_LINK**. Self-reported UUIDs never resolve buyer authority.
- The original `revenue_completion_supervisor.build_snapshot()` now contains `canonical_opportunity_handoffs`. The existing `scripts/run_revenue_completion_supervisor.py` shows the record count and exact next handoff task in its existing service output. No new timer, daemon, database or agent.

## Live readback and next real evidence
At initial production-read-only inspection, one Factory snapshot contained **19** distinct research keys with zero `factory_ready`, zero `opportunity_id`, zero `tenant_id`. All 19 are correctly held for real Factory validation or later canonical DB lookup. These are *research counts, not consented leads, customers or sales*.

The later release must verify one actual source-row receipt (not merely `canonical:prospect_acquisitions`), identify exactly which authorised business entity and tenant it belongs to through the existing verified EmpireDB relationship, and verify one exact `gtm_opportunities.id`. Only then can the original buyer-approved commercial and financial gates be evaluated. Never synthesize an opportunity table row as a shortcut.

## Operational gates
- `EMPIRE_MODE=OBSERVE`, original snapshot cadence, no SQL writes, no network calls, no outbound, no contract, no payment, no financial recognition or model weight change.
- Production root is concurrently edited by other agents. Apply only tested, exact-file diffs through the protected production release process, with rollback and post-release original service smoke tests.
- PRs #111 (Buyer Evidence Brain) and #114 (cross-system cohesion) are separate review candidates. Do not claim either is already deployed or that this per-record feature completes their remaining stages.
