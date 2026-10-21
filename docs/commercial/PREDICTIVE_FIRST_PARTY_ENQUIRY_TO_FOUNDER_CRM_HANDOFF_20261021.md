# EmpireOS — first-party buyer enquiry → Founder CRM handoff

21 October 2026. Live original-owner schema and code inspection plus strictly READ-ONLY observations. No fake prospect submitted, no buyer contacted, no new role, no payment or DB mutation.

## Actual path

The existing public `/commercial` and `/predictive-revenue` forms call POST endpoints in `empire_os/public_gateway.py`. Those gateway handlers enforce same-origin, content type, bounded request body and limiter, then forward the visitor's opted-in payload to existing checkout handlers. The checkout handlers call `ingest_prospect_atomic`, storing canonical `public.prospects` and append-only `public.prospect_acquisitions` entries (including source and specific response consent evidence). The source reported a successful insert if its atomic RPC returned a prospect ID; this is **not** proof the founder CRM projected it.

The existing `public.revenue_crm_prospects` view is an RLS-protected projection of `public.prospects` governed by `public.empire_crm_prospect_authorized`. That predicate requires an active, independently evidenced `prospect_entity_links` → `tenant_business_entity_bindings` chain for the **actual session tenant**. Neither public checkout handler invents a tenant binding, by design. A genuine first-party acquisition can therefore exist but still be invisible in the founder CRM until original owner identity/tenant reconciliation. **Do not auto-link a buyer to the founder tenant from self-asserted email, company domain or public form input.**

## Engineering completed

1. Existing `scripts/reconcile_founder_sales_handoff_aggregate_readonly.py` now marks zero-data source-consent and tenant-scope completeness as `null`, not fictitious `true`. It explicitly flags CRM sales prospects without matching canonical first-party acquisition counts and rejects mismatched source/tenant status labels or unexpectedly elevated original probe authority. It still never asserts an exact buyer-to-CRM receipt from aggregate counts.
2. New `empire_os/predictive_existing_sales_path_review.py` and `scripts/review_predictive_sales_path_20261021.py` combine the existing GET-only public form canary with the **existing authenticated Ubuntu founder CRM aggregate reader**, returning only two counts and a structured sales-path decision. No underlying customer rows or IDs are read or returned.
3. The existing immutable `empire-predictive-observe` release launcher adds `sales-path` to run this on demand, with checkable source hashes and a release canary. It reports whether forms load and a restricted CRM sales cohort is visible. It intentionally reports `canonical_acquisition_count_checked=false` and `founder_crm_delivery_verified=false` until original source receipts can be reconciled.

## What is still needed to convert a buyer

- Obtain a genuine opted-in company enquiry via the two already deployed pages (no synthetic production POST).
- Have the *original source owner* run `scripts/reconcile_founder_sales_handoff_aggregate_readonly.py --review-only` under its own privileged, audited deployment. The shared source files are not currently safe to execute as root via our feature-branch launcher, and its source probe was observed to be group-writable. A pinned root-owned custody fix is needed before reusing that privileged runner.
- If canonical source records exist without exactly one trustworthy company/tenant binding, manually review the real source and identity evidence under existing original-CRM authority, then project to founder CRM. A global acquisition count cannot grant tenant scope.
- Preserve exact prospect/acquisition/CRM linkage; then verify buyer terms, order, fulfilment, settlement and pre-outcome original forecast registry. No amount of synthetic catalogue or form traffic is accepted as sales or model learning.

Live check before this change: two public form routes and their catalogues passed; the existing founder CRM reader reported zero commercial and zero Predictive Revenue prospects. This means public web surfaces are responsive, but no customer delivery is proven.
