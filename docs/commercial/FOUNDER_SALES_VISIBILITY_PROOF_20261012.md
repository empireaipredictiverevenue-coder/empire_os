# Empire AI — genuine website enquiry to founder CRM visibility
**12 October 2026 | PRODUCTION-TRUTH-FIRST | OBSERVE ONLY**

## Why this was checked

Empire AI’s live `/commercial`, `/predictive-revenue` and `/buy` pages, the checkout service and the existing Revenue CRM are already deployed. Public offer/catalogue availability must not be mistaken for a received customer lead, a founder-visible sales opportunity or verified revenue. We are not making any fake form submission to produce a convincing-looking success.

## Current production evidence

- Public origin GET for commercial, predictive revenue and buy pages returned HTTP 200; catalogue APIs returned 200 and ten founder-led offers, five Predictive Revenue deployments, and the previously verified standalone intelligence and Exchange catalogues.
- Self-serve checkout and founder CRM services were active. CRM `GET /health` returned 200, and unauthenticated `GET /v1/revenue-crm/prospects` correctly returned **401**. No login override or cross-tenant data was exposed.
- Existing private CRM three-login verifier was run successfully as Ubuntu: `python -m scripts.diagnose_crm_committed_login_sessions --read-only`. All three sessions, founder-tenant resolver and denial of direct raw role-binding table reads returned **PASS**, with no database writes and no credential changes.
- One exact pre-existing-credentials, dedicated-login, tenant-scoped read-only query against `public.revenue_crm_prospects`, restricted to the trusted `public.empire_current_tenant_id()`, returned **zero total rows** as of 12 October. This is a claim only about what this dedicated founder tenant is currently permitted to view. It does **NOT** establish that the global `public.prospects` store contains no records or that the website received no enquiry.
- New `scripts/probe_founder_sales_visibility_readonly.py` wraps that same approach in one **aggregate-only** diagnostic, with an 8-second PostgreSQL statement timeout and strict 0600 private temporary passfile handling. It writes no source database data and emits no tenant IDs, prospect IDs, emails, domains, passwords, original records, or raw database errors.
- The one-hit tool returned `status=NO_TENANT_VISIBLE_SALES_PROSPECTS`, `visible_commercial_sales_prospects=0`, `visible_predictive_revenue_prospects=0`, `visible_total_prospects=0`, `canonical_global_intake_count_proven=false`, `website_to_founder_visibility_proven=false`. No prospect insertion, contact, payment or DB migration occurred.

Exact safe rerun:
`cd /srv/empire_os && PYTHONDONTWRITEBYTECODE=1 ./.venv/bin/python -m scripts.probe_founder_sales_visibility_readonly`

## Contract-level visibility gap — distinguish facts from diagnosis

**Website-side contracts verified in source:** `empire_os/first_party_sales_interest.py` and `empire_os/predictive_revenue_self_serve.py` call the canonical `/rest/v1/rpc/ingest_prospect_atomic`. They record an idempotent prospect/acquisition with a contact source and lead evidence. `migrations/empiredb/003_prospect_acquisition_ledger.sql` creates or reuses a prospect and writes identity/acquisition evidence. This ingestion contract does **not** itself create the CRM's documented tenant/business-entity visibility bindings.

**Founder CRM tenant policy verified in source:** `migrations/empiredb/040_revenue_crm_tenant_reader_views.sql` defines `empire_crm_prospect_authorized(p_prospect_id)`. It requires exactly one active, evidenced `prospect_entity_links` -> `tenant_business_entity_bindings` match for the trusted tenant, with permitted binding kind and current validity dates. The CRM view uses that policy, and the dedicated reader cannot bypass or browse the global binding tables.

**What remains unproved:** the full live canonical intake source count, whether any genuine on-site interest was submitted, whether a specific genuine enquiry was linked to the correct verified business entity/tenant, and whether the founder can see that specific acquisition with consent and requested solution. This is an **incomplete receipt-to-founder proof**, not yet proof of discarded data or a broken database transaction.

**Do not 'repair' with:** cross-tenant `SELECT` grants, all-global CRM prospect visibility, blind prospect-to-founder assignments, fabricated evidence links, anonymous test buyers in production, automatically approved consents, undisclosed lead source-sharing, outbound sends or payment activation.

## Shortest governed closure path

1. Use the existing authorised canonical EmpireDB reader (NOT the unprivileged CRM role) for a separate **read-only aggregate/provenance query** that counts genuine first-party `commercial_sales` and `self_serve_predictive_revenue` acquisitions. Verify the owner of that data and current source fields first; print counts/source state only. The dedicated CRM reader intentionally cannot access the raw source.
2. If real buyer-created acquisition IDs exist, review their actual business identity and required tenant binding with the founder using authorised private tools. Establish an exact one-to-one evidence trail before proposing any link mutation. A shared prospect identity or unverified domain is not enough.
3. Only after exact binding approval, use the existing `prospect_entity_links` and `tenant_business_entity_bindings` contract; no new CRM or parallel inbox. Any write/permission change is separately founder-gated and requires backup, proof, single change, scoped tests, readback and reversal plan.
4. Verify the actual authenticated founder CRM view and its next action for the **same genuine** consented enquiry; then manually review a specific reply/proposal. No automated contact, duplicate send or amount of recognised revenue inferred from the proof.
5. Maintain independently that the public gateway's later Predictive Revenue origin/rate-limit code commit `11f67279` is **not runtime-loaded** (service started earlier at 10:45:49 UTC). Deploy/restart only under explicit separate authority and verify legitimate first-party POSTs with mocks before accepting production status. Existing payment and Lead Smart call gates remain OFF.

## Engineering verification

New `tests/test_founder_sales_visibility_probe.py` covers zero and positive count results, non-disclosure of secrets/driver output, private temporary-passfile cleanup, strict expected SQL `READ ONLY`/tenant filter, malformed aggregates, and no side effects. With the existing CRM transport/authenticated-router tests, **53 passed** on 12 October 2026.

**Status:** `FOUNDER_SALES_ENQUIRY_TO_CRM=UNVERIFIED`. `CRM_DEDICATED_READ_AUTH=VERIFIED`. `FOUNDER_TENANT_VISIBLE_SALES=0`. `OUTBOUND/PAYMENT/DATABASE_WRITE=NONE`.
