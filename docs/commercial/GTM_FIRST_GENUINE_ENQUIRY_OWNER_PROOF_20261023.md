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

## 23 October 2026 — gap resolved using existing authorised Ops source

The original root-operated `empire-ops-control.service` (no new service) produced its existing `first_sale_conversion_readiness` read-only EmpireDB aggregate. Its observation on 23 October at 11:45 UTC verified `NO_CANONICAL_FIRST_PARTY_SALES_ENQUIRIES`: commercial acquisition rows **0**, Predictive Revenue acquisition rows **0**, total canonical sales acquisitions **0**. This counts precisely the two original first-party sales sources, NOT separate research, brokerage, job matching or enquiry tables. The independent tenant-scoped Smart CRM read-only login also returned zero visible sales prospects. Thus the present first-sale gap is **lack of a recorded genuine customer submission in these two sources**, not a demonstrated missing founder-tenant link. Future nonzero source rows would require exact event/tenant proof.

`empire_os/gtm_ops_first_sale_source.py` reuses only the existing Ops Control root-owned snapshot. The existing GTM observer records this as `canonical_sales_source_ops` with source-specific counts and a verified-zero status; the separate `owner_sales_reconciliation` remains a held privileged-operator check until an actual owner creates its receipt. This adds no SQL, new credentials, new watchers, anonymous POSTs or person-specific data. Root-owned snapshot, freshness, read-only mode, schemas, audit flags, source arithmetic, provenance consistency and zero execution permissions are checked; stale or contradictory data returns UNKNOWN, never zero. Test fixtures cover zero, nonzero, stale, invalid authority and inconsistent counts.

Existing public entrypoints `/commercial`, `/predictive-revenue` and `/privacy` returned HTTPS 200 and homepage `/buy` CTAs link to the commercial forms; GET-only first-party intake and anonymous CRM-denial canaries passed. The remaining work is original organic acquisition and authentic visitor self-submission, followed by exact source/consent and tenant CRM readback, founder-reviewed response and paid outcome if one occurs. No forms were submitted; no outreach, production payment activation, CRM writes or fictional buyers.
