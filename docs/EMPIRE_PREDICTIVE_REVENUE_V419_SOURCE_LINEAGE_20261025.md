# Empire AI Predictive Revenue V4.19 — original GTM source-lineage audit (HELD)

**25 October 2026 | One EmpireOS, one canonical EmpireDB PostgreSQL, one Smart CRM. Not trading.**

## What was upgraded

V4.18 established a tenant-*claimed* opportunity population and a bounded research CVR/eCAC. A SHA256 source digest and an attached tenant assignment do **not** prove that the original event was lawfully acquired, independently attributed to a tenant, duplicate-free or a member of a complete inbound cohort.

V4.19 adds a bounded provenance/completeness cross-check **without creating a second opportunity table, ingesting more scraped data, or changing production observers**:

1. **PREPARED migration 071:** `migrations/empiredb/071_predictive_revenue_source_lineage_audit_held.sql`. Adds one read-only SECURITY DEFINER function to original EmpireDB (not applied in production). Requires existing owner/migration roles, the original `gtm_opportunities`, V4.18 tenant custody table and reader, and the same original trusted `empire_current_tenant_id()`. It is accessible only via the existing NOLOGIN restricted reader capability, subject to the dedicated `session_user` login check. All direct underlying GTM/custody SELECT privileges remain denied.
2. **Source-lineage adapter:** `empire_os/predictive_revenue_v419_lineage_audit.py` checks original Ed25519 signed CRM active tenant membership and V4.12 research-only twin; opens the original restricted PostgreSQL connection as `REPEATABLE READ, READ ONLY` with 4-second timeout; reads original V4.18 custody aggregate and V4.19 GTM metadata aggregate in **the same database snapshot**, rejecting different row counts, foreign tenants, contradictory counts, forged authority flags and unverified currencies.
3. **Real PG18 rehearsal:** `scripts/rehearse_predictive_revenue_v419_lineage_20261025.{sh,py}` builds a disposable 18 cluster with original migrations 067–071 installed **inside the fixture only**, controlled signed CRM and SCRAM reader login, and tests source metadata, incomplete fields, tenant crossover, role ACLs and no direct table access.
4. **Negative acceptance tests:** `tests/test_predictive_revenue_v419_lineage_audit_20261025.py` exercises mock-connector non-promotion, forged missingness/counts, false rights approvals, empty results, bad currency, bad CRM, failed credentials, time-window limits and actual PostgreSQL.

## What the reader reports

- Number of tenant-*claimed* custody opportunities in a half-open <=31-day window, and number matched to original GTM rows.
- Missing/blank original `source_channel`, `niche`, `opportunity_type` counts. Original table values remain authoritative; the reader does not change source taxonomy or invent one of the four target sector mappings.
- Delayed custody records registered >24 hours after original GTM creation (a **review indicator**, not necessarily fraud).
- Zero-cost custody **claims** (organic acquisition can legitimately cost zero), distinct source/owner digest counts (multiple opportunities can share one valid licensed batch document; reuse alone is **not deduplication proof**) and number of distinct original channel/niche/type labels.
- Number of V4.18 opportunities lacking any lifecycle state from a **single consistent PostgreSQL snapshot**.

No order/customer IDs, email addresses, raw source documents, source records, provider credentials or unrestricted GTM lists are exported. The hard 5,000-record and 31-day bounds remain.

## Production and commercial authority

The original `gtm_opportunities`, `fulfilment_orders` and Smart CRM remain canonical. V4.18 claimed ownership is still **not independently corroborated** by this audit. Existing V4.10/V4.11 source rights remain HELD and migration 066 is not production activated. Thus V4.19 always returns **source rights verified=false, upstream opportunity intake complete=false, cost invoices verified=false, customer CVR/eCAC verified=false, customer cash revenue=null, source ingestion/outbound/paid traffic/funds=OFF**.

Even if all currently stored GTM rows have source fields, this only proves completeness of *those records*, never that all incoming calls, clicks, form submissions, permitted public data or third-party referrals entered EmpireDB. Nor can it show whether a vendor's collection rights include re-sale, email contact or other use.

The V4.18 30/60/90 scenario factors remain illustrative, not calibrated cash forecasts. **No live DB migration, settlement, payment, email, campaign or autonomous learning was activated.**

## Verification and next gate

Isolated PG18 sample: seven in-window claims, seven matching original GTM rows, one missing source channel, one missing niche, one missing opportunity type, one delayed custody record, zero zero-cost claims, one common source digest and one common owner digest; previous V4.18 mixed opportunity statuses remain valid. All are artificial fixture rows.

**Next:** obtain independently authorised source-register receipts and end-to-end ingestion reconciliations for every supported niche and channel; reconcile actual carrier/organic costs to immutable invoices and tenant rights; then design a rights-verified *full* opportunity denominator, eventually pairing accepted orders with final cash/refunds for true historic CVR/eCAC and V4.14 time-to-cash calibration. Separate owner approval is required to execute production DDL 066–071.

**V3.6 production observer unchanged. V4.9 live OBSERVE unchanged. One EmpireOS. One EmpireDB. One Smart CRM.**
