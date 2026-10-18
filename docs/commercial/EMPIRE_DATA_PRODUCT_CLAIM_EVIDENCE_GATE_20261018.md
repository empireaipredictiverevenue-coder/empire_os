# EmpireOS — evidence-bound intelligence data-product report preflight

**18 October 2026 | Canonical EmpireDB / existing private Data Brokerage catalogue / founder data-product contracts | OBSERVE**

## What was genuinely added

The Empire AI data-product catalogue already had product names, categories, delivery modes, required evidence fields and a no-price/no-entitlement policy. The Data Brokerage internal catalogue already held source-licensing and outbound restrictions. **Neither contract by itself proved an individual published statement.**

This milestone adds a source-bound report-preview check without a new service, external route, tenant grant, DB table, sender or queue:

- `empire_os/data_product_claim_gate.py`: `review_data_product_claims(product_key, requested_claims, repo_root)` accepts **only** a bounded list of exact `statement_id`, official DOB `bin` and `dob_bbl`; a caller may not supply marketing copy, buyers, addresses, source links or claim-release flags. Unknown or repeated statements, wrong product vertical or unsupported property reference cause **whole-report HOLD**, not a partially accepted report.
- For an internal preview it requires a fresh 48-hour (`property_claim_receipt_runtime.validated_claims`) four-property evidence packet and confirms the packet's source full-day report SHA-256 against the **actual unchanged private source report** and matching provenance receipt. This is integrity and consistency, **not publisher-signed proof**.
- The allowed output text is rendered *from the evidence packet*, not supplied by the user. It carries exact statement ID, official DOB BIN/BBL, official dataset IDs/URLs, each selected response SHA-256 or local underlying DOB report digest, observation time, evidence grade and **`not_proven` limitations**.
- Supported NYC public-record kinds: observed permit event; matching OTI/DCP building-tax-lot references; OTI/DOB lot-reference conflict; matching DOB NOW Certificate of Occupancy with an OTI discrepancy still unresolved; PLUTO recorded E2/E9 building class using DOF legend; and PLUTO reported storage-area field. These are government-publication statements only, not current operating businesses, owners, paid customers, construction starts, buyer intent or revenue.
- Mapped: `nyc_permit_project_verification`, `property_intelligence_monitor` and narrower `permit_intelligence_feed`. Unrelated Empire AI products stay **HOLD** for these proofs.
- `empire_os/data_brokerage_product_catalog.py`: the existing four-product internal catalogue now records validated `claim_evidence_contract` per product and validates the status, counts and release restrictions. The NYC permit product can show **four** internally reviewed property-reference pairs, including **two** warehouse-classified pairs, only with valid protected evidence. Others have no linked receipt. The source scope digest includes the contract, but is **not an external authentication signature**.
- The historical private catalogue snapshot from earlier on 18 October remains readable as **legacy, internal, no-commercial-authority inventory**. Its old scope hash and original no-export/no-buyer/no-payment gates are still checked. A mixed old/new partial snapshot fails; **newly generated catalogue snapshots must contain the complete evidence contract**. The old snapshot cannot be construed as claim verification.
- `scripts/preview_data_brokerage_products.py`: existing private catalogue reader passes the project root into this proof read-model and reports claim-preflight status; its original protected-inspection requirement for materialization remains intact.
- `empire_os/intelligence_data_products.py`: each product in the read-only Founder catalogue now declares source-proof required, customer claim release not ready, and unverified claim output disabled. This is contract metadata, not a universal API interception layer.
- `scripts/preview_product_claims_readonly.py`: optional on-demand founder review for *one* exact official-source claim. Requires `--read-only`, no file writes or sender.
- `tests/test_data_product_claim_gate_20261018.py`: proof-chain mismatch, unsupported statements, forged/free-form marketing, duplicate and oversized claim collections, wrong product mapping, whole-request HOLD, local CLI and legacy catalogue regressions.

## Exact on-demand private preview on canonical EmpireOS

```bash
cd /srv/empire_os
./.venv/bin/python -B -m scripts.preview_product_claims_readonly \
  --read-only --product nyc_permit_project_verification \
  --statement DOF_PUBLISHED_WAREHOUSE_BUILDING_CLASS \
  --bin 4436582 --bbl 4000290016
```

Expected only **PRIVATE_SOURCE_BOUND_CLAIM_PREVIEW_ONLY** when protected source receipts remain current and consistent, producing NYC PLUTO's E2 building-class source statement and exact response hash. It returns `customer_distribution_authorized=false`. Requests for `ACTIVE_WAREHOUSE_OPERATIONS`, `VERIFIED_REVENUE`, `BUYER_INTENT`, arbitrary marketing copy or an uncorroborated CO claim return **HOLD**.

### Supported source claim is NOT permission to distribute

Every customer release must separately satisfy source-specific reuse rights, field licence, privacy, attribution, authorised buyer delivery, and settlement checks. Source-specific public data rights and permitted redistribution have not been independently signed off. The two warehouse-class references establish a source-defined classification only, not independent proof of active warehouse operations, tenants or sales prospects.

The DOB NOW scheduled permit ingestion flag remains **UNSET**. No new timer, cost, email, website publication, public SaaS endpoint, customer activation, EmpireDB write or money movement.

## Open gap

This is a **working internal claim-level guard connected to the private brokerage catalogue and founder product metadata**. It does **not yet intercept every live API, generated report, SaaS dashboard or third-party feed**. Other domains need domain-specific source adapters and explicit release-path integration; a claim about another sector cannot reuse a NYC property receipt. Audit the existing external product and report routes next, prioritising actual revenue-facing endpoints and preserving existing project ownership.
