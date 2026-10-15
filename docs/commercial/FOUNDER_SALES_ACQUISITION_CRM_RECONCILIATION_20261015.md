# EmpireOS — Canonical Sales Acquisition to Founder CRM: Evidence Reconciliation

Date: 15 October 2026 | Scope: EmpireDB read-only commercial + Predictive Revenue intake truth | Mode: OBSERVE

## Verification completed

1. Public /commercial and /predictive-revenue HTML and deployed JavaScript reference their corresponding existing /v1/checkout/*/interests APIs. Their public product catalogues returned 10 and 5 offers, respectively, in the earlier independently verified live GET-only canary. No site code was modified.
2. On 15 October, both live public POST routes were probed only with explicit contact_consent=false and a reserved .test address. BOTH returned 422 specific_contact_consent_required. Handler code rejects this before ingest_prospect_atomic, so no test buyer, tenant, prospect, payment or reply was created. This is a rejection-path check, NOT a successful genuine enquiry.
3. The real EmpireDB ingestion RPC is public.ingest_prospect_atomic from migration 003. It can create/resolve prospect_identity_claims, prospects and immutable prospect_acquisitions, but it does NOT insert a matching row in prospect_entity_links or tenant_business_entity_bindings.
4. The existing Founder CRM RLS projection is public.revenue_crm_prospects from migration 040. It requires exactly one active evidenced prospect_entity_links row to an entity with exactly one active, evidenced matching tenant_business_entity_bindings row. Both verified proofs are necessary for tenant-safe visibility; a website email+domain claim is insufficient.
5. The existing ubuntu-owned tenant-scoped read-only probe reports zero currently visible commercial and Predictive Revenue prospect rows. Without the global source count, zero does not prove no genuine acquisitions exist or that tenant binding is broken. The two stages therefore cannot be declared end-to-end proven.

## Changes prepared

- scripts/reconcile_founder_sales_handoff_aggregate_readonly.py: a one-shot, bounded composite observer using ONLY two pre-existing probes. It runs the global canonical acquisition probe under root's controlled postgres read-only subprocess and the tenant-scoped CRM probe under dedicated user ubuntu and its already approved restricted CRM reader. It rejects altered schema/unsafe statuses, discloses only aggregates and safe reason codes. No raw identities, PII, credentials, tenant identifiers, SQL driver errors or row data are exposed. It performs no writes.
- Added tests/test_reconcile_founder_sales_handoff_aggregate_readonly.py for zero actual enquiries, inconsistent/forged source evidence, missing entity identity, missing tenant binding, CRM projection gaps, source+CRM count non-proofs, malformed counts, root gating, fixed subprocess allowlists and no secret exposure.
- scripts/probe_canonical_sales_intake_aggregate_readonly.py: restored strict parity for BOTH inbound source types. For either source, count an evidence-consistent receipt only with exact source, buyer_stated=true, buyer_initiated_specific_response_consent, consent_to_contact=true, newsletter/ongoing marketing consent=false, and the correct specific original first-party URL. The previous ELSE TRUE erroneously accepted Predictive Revenue receipts with absent consent proof.
- Updated tests/test_canonical_sales_intake_aggregate_readonly.py to prevent the consent bypass from recurring.

## Operating statuses returned by the new aggregate-only operator

| Result | Interpretation | Permitted follow-up |
| --- | --- | --- |
| NO_CANONICAL_SALES_ACQUISITION_OBSERVED | Both observer sources queried; no matching canonical sales acquisitions yet | Await real opted-in enquiry; do not fabricate demand |
| CANONICAL_INTAKE_EVIDENCE_INCONSISTENT | Genuine source eligibility/consent cannot be proved for all rows | Private review of immutable source receipt, no new outbound |
| IDENTITY_LINK_GAP_DETECTED | At least one source acquisition lacks an active evidenced entity link | Verify person-company-domain identity before linking |
| TENANT_BINDING_GAP_DETECTED | Active entity exists but founder tenant scope is missing or ambiguous | Privileged evidence review, then separately approved binding |
| CRM_PROJECTION_GAP_DETECTED | Source receipts appear structurally qualified but founder-scoped CRM still shows no sales rows | Review restricted role, tenant mapping, RLS and projection |
| NONZERO_SOURCE_AND_CRM_REQUIRE_RECEIPT_MATCH | Both have nonzero counts; cannot assume same prospect | Exact immutable receipt-to-visible-tenant-prospect reconciliation required |
| HELD_* | Reader permissions/schema/count integrity unavailable | Stop and diagnose; never bypass tenant access |

## Invocation boundary

The release is installed in source control but NOT a new service or timer. Unprivileged runs show a held status rather than a false zero. Default invocation is non-executing. The one-time root-approved command below only invokes already-existing SELECT-only transactions:

    cd /srv/empire_os
    sudo -n ./.venv/bin/python -m scripts.reconcile_founder_sales_handoff_aggregate_readonly --review-only

No activation, migration, sender permission, source file edit, public site update, tenant binding, mock acquisition, email, consumer data export or payment is authorised by the operator.

## Required engineering bridge when a genuine acquisition is observed

Do not grant business/entity tenant scope based only on unverified website form values, arbitrary email text or a synthetic submission. Stage a founder-specific review with immutable source evidence, validate one canonical business entity against independent first-party evidence, then bind one owner-scoped entity with explicit source and founder authority. Finally use the existing tenant-restricted CRM view to verify receipt visibility. This preserves the owner-vs-third-party tenant boundary.

The structural code does not automatically bridge it today. Do not label 0 visible prospects as proof that the public intake is broken, or 1+ global source rows as permission to contact customers. The existing final README and company search packets are unrelated to this control and were not changed.
