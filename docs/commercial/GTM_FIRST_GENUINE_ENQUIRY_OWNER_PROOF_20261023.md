# GTM first genuine customer enquiry — CRM owner handoff
23 October 2026. Observe-only. No execution authority or new services.

## Verified boundaries
- Live GET-only checks passed for the commercial and Predictive Revenue first-party enquiry routes and the private CRM anonymous-access boundary. No test buyer was submitted.
- GTM's owner-authenticated exact customer count remains UNKNOWN, not zero.
- The existing privileged read-only scripts reconcile_founder_sales_handoff_aggregate_readonly.py and its source/tenant probes are the canonical authority for aggregate facts. A matched source and tenant count is not proof of one prospect's exact receipt lineage.

## New integration
- empire_os/gtm_sales_owner_reconciliation.py accepts only a fresh, root-owned, permission-sealed count-only receipt with the original owner's reconciliation status and strictly validated aggregate counters.
- scripts/publish_gtm_sales_owner_reconciliation.py uses the existing DB owner's read-only reconciliation run only after an authorised privileged one-shot invocation. It adds no SQL, database privileges, scheduler, CRM writer, payment service or sender.
- The only file that may be produced by that authorised operator is runtime/gtm_pipeline/owner_sales_reconciliation_latest.json with mode 0600 and root ownership. The ordinary GTM service reads it but NEVER invokes the privileged probes.
- Missing, stale or contradictory source data fails closed. Even nonzero source and tenant counts leave contact consent, exact lineage and Smart CRM delivery unverified.

## DBA-controlled one-shot (not performed here)
Only the authorised canonical EmpireDB / CRM owner, in its existing privileged workflow, may run the following command after its usual access approval:
cd /srv/empire_os
.venv/bin/python -m scripts.publish_gtm_sales_owner_reconciliation --review-only --write-owner-aggregate
Never run that command to bypass remote permission restrictions. It is not scheduled or triggered by this integration.

## Exact real-customer proof required
1. An actual visitor voluntarily submits /commercial or /predictive-revenue and grants purpose-specific response consent. No founder/self-test, seeded record, synthetic POST or inferred intent.
2. The original intake owner verifies the exact idempotent acquisition/source and consent receipt in EmpireDB against one real prospect.
3. The current tenant owner independently reads back that same original prospect through properly authenticated founder-tenant Smart CRM access, resolving entity binding, contact validity and suppression. Keep personal data in its source system.
4. The original empire_gtm_agent_v1 may then prepare a buyer-specific response for founder approval. No automatic outbound; contact requires live suppression and matching response-consent checks.
5. Only separate verified offer acceptance, fulfilment and settled payment can enter Economic Memory as realised revenue.

Media views, JEV hypotheses, search impressions, contractor candidates and brokerage research are not customer enquiries. No paid traffic, public release, payments, database writes or unauthorised outreach in this handoff.
