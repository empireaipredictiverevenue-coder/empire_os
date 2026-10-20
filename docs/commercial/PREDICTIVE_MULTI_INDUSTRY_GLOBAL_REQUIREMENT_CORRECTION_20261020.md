# EmpireOS Predictive Commercial Requirements — Multi-Industry, Multi-Market Correction

**Date:** 20 October 2026
**Owner:** Existing Predictive Intelligence/Cloud integration agent
**Release state:** OBSERVE-only; version-pinned read-only release, *not* a deployed multi-industry marketing/sales execution worker.

## Product meaning

The original founder Tampa/roofing/20-leads brief is an **illustration, not a live or default market**. The engine is intended to accept commercial requirements from any authorised customer, industry and region and coordinate existing owners of Buyer Scout, A2A, Lead Supply, Marketing, Procurement, Finance, Quant and Cloud. No inferred customer order, default territory, synthetic current lead inventory or material RFQ.

### Corrected command contract

```bash
# No input = no invented market; prompts downstream to supply original intake
~/.local/bin/empire-predictive-observe commercial

# Demonstration-only Tampa case (explicitly labelled unverified founder example)
~/.local/bin/empire-predictive-observe commercial-example

# A customer/founder source-reviewed exact JSON requirement for ANY supported market
~/.local/bin/empire-predictive-observe commercial-intake /approved/path/request.json
```

The original script `scripts.review_predictive_commercial_requirements_20261020` accepts `--requirement-intake` from an original reviewed file, or `--example-tampa-roofing`, never both. Without either, returns `COMMERCIAL_REQUIREMENT_INPUT_REQUIRED`, `default_market=null`, `default_industry=null`. No default customer target. No market-specific source snapshots are read or A2A tickets prepared without an explicit requirement.

The exact input keys remain the existing `INPUT_FIELDS` in `empire_os/predictive_commercial_requirements.py`. This is an **unverified commercial draft**, not an auto-authenticated contract even if tenant/company hashes are filled. All company, consent, Finance, capacity and payment proofs require existing independent source owners.

### Implemented sector/country research matrix

- **Physical products/services:** roofing, HVAC, solar, construction and owner-specified physical services. Material category requirements vary by industry. Sourcing is preliminary only until original measurements/specifications/quotations/approval.
- **Non-physical commercial services:** agencies, insurance, data brokerage, professional services and software. **No fabricated roofing bill of materials** and no forced physical supplier RFQ. Licence/data permissions and other relevant owners remain independent.
- **Illustrative tested markets:** Phoenix HVAC, Texas solar, NYC construction, California insurance, London agency, Toronto professional services, Sydney software, Berlin data brokerage and India general services. Geography, target counts and material scopes come from the explicit input, not a hard-coded example.
- **Typed country/currency support:** source declarations currently accept US/USD, GB/GBP, CA/CAD, AU/AUD, NZ/NZD, European EUR jurisdictions (DE, FR, IE, NL, ES, IT, BE, AT, PT), IN/INR, ZA/ZAR, SG/SGD and AE/AED. These are validation constraints, **not evidence that any local market actually has approved inventory, laws, tax rates or exchange rates**. Other jurisdictions require source owner contract extension, not invented jurisdiction rules.

### Safe original research joins

`predictive_commercial_supply_readiness.review_lead_readiness_runtime` now accepts **industry, country, region and city** from the same validated requirement. The original Lead Supply aggregate reports *global sector research counts* only; these remain specifically labelled `source_target_industry_research_records_not_leads`. If a sector bucket is absent, count stays **null**, even when other source buckets are present. Zero global immediately sellable inventory remains only a source-snapshot claim, not proof of no actual local demand.

`plan_commercial_fulfilment` rejects mismatching research metadata across industry/market instead of joining unrelated records. It never infers a committed buyer, consent, exclusive lead, original RFQ, paid settlement, capacity or conversion probability from a research counter.

New fields `verified_target_market_available_inventory`, `verified_target_market_eligible_leads`, `source_target_industry_research_records_not_leads` and their plan/Cloud equivalents separate genuine cross-market readiness from old Tampa-shaped field names. Legacy Tampa/roofing names remain null for other industries and are **compatibility only**, not the primary API.

A cloud modelled hypothesis remains **a hypothetical research scenario**, not a confirmed fulfilled lead, client contract or spending mandate. Original producer permissions, canonical inventory source, source-event times, ZIP/postcode validity, data-rights/consent, invoice custody, buyer price terms, forecast registration and cross-tenant dedupe still need independent owner evidence.

### Deployment and rollback

The next commit is packaged using existing `scripts/prepare_predictive_readonly_release_20261020.sh` into a **new immutable commit-qualified sidecar release**, with source checksums and an allowlisted launcher supporting `commercial`, `commercial-example`, `commercial-intake FILE` and the existing Finance, Cloud research, gap, BLS and owner review profiles.

No production checkout mutation, service restart, cron, A2A dispatch, material purchase, marketing budget, CRM write, buyer contact or Quant training. Prior pinned releases remain intact; shortcut replacement, if done, is backed up or can be reset to the previous verified release. All the source owner worktrees and their uncommitted files remain unchanged.

## Acceptance criteria

- No-input operator never silently opens Tampa; status is `COMMERCIAL_REQUIREMENT_INPUT_REQUIRED`.
- Explicit example remains an example, not a customer purchase.
- Source intake drives canonical industry/location/quantity and source-sector research counts.
- Cross-industry research sources cannot masquerade as locally qualified/consented leads.
- Physical sectors receive relevant material research categories; nonphysical service sectors do not trigger supplier procurement.
- Wrong geography, false payments, quote forgery, wrong currency, replayed lead identity, unapproved spend and original forecast claims fail closed.
- Eight prepared source-owner tickets remain **unsent** with deterministic keys and no durable replay guarantee.
- Tests across existing Cloud, Buyer Graph, Lead Smart and procurement contracts remain green.

**Product north star:** authenticated commercial instruction → original source discovery → validated demand and deliverable inventory → expected, cash- and capacity-constrained economics → approved execution → original verified payments/fulfilment → Quant/Cloud calibration and allocation. Until independently authenticated, keep probabilities and gross-profit numbers null.
