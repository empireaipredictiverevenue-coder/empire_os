# EmpireOS All Products Live Smoke Report — 2026-10-02

Status: OBSERVE / CAMPAIGNS PAUSED PENDING PRODUCT PROOF

## Whole-product universe

- Canonical commercial catalog rows: 86
- Commercially VERIFIED + active + binding-ready: 26
- Active but commercially pending: 9
- Inactive recovered MRR: 51
- Digital Avatar proposal-only products: 3

Final combined automated/product-family/product-code gauntlet:
- 211 passed
- RC=0

Product-code catalog auditor:
- every canonical row classified
- duplicate/malformed codes fail closed
- catalog verification no longer auto-unlocks campaigns
- live-smoke evidence is required per exact product code

## Live-smoke PASS — 9 canonical products

The production Search Intelligence service on 127.0.0.1:8771 reported READY
for every canonical non-solar search product below. The service is OBSERVE /
non-mutating; product pricing is not inferred from the search runtime.

- authority_intelligence
- competitor_search_gap
- content_protection
- geo_ai_visibility
- local_search_grid
- search_growth_command
- search_opportunity_map
- serp_intelligence_api
- technical_search_audit

Evidence surface:
- GET /v1/search/health -> HTTP 200
- GET /v1/search/products -> HTTP 200
- GET /v1/search/products/readiness -> HTTP 200
- canonical product contracts above all report status=READY

These nine are technically/live-smoke ready for governed enquiry/demo campaign
claims, but NOT self-serve checkout claims.

## Live-smoke BLOCKED — 17 commercially verified products

### Solar Opportunity Maps — 13 localized SKUs

Current runtime contains two artifact_ready=true UK solar map artifacts.

However the live founder source-intelligence endpoint currently reports:
- country_code=GB
- market_anchor_count=45
- latest_proof.available=false
- verified_source_proof=false
- canonical_write_observed=false
- commercial_outcome_observed=false
- recognized_revenue_observed=false

Therefore even solar_opportunity_map_gb remains smoke-blocked under the stricter
proof standard.

The other 12 localized solar SKUs have not yet been individually generated and
production-smoked for their country:
AU, BE, CA, DE, ES, FR, IE, IT, NL, NZ, PT, US.

### private_capital_rollup

Current production snapshot exists and is fail-closed but has:
- canonical_fact_count=0
- canonical_signal_count=0
- private_capital_segment_count=0
- segment_membership_count=0
- evidence_state=UNKNOWN
- latest_observed_at=null

Therefore product fulfilment proof is not yet sufficient.

### permit_intelligence

Founder data-product contract returns HTTP 200 and defines the correct evidence
requirements/delivery modes, but the current test did not establish a live
product-specific observed-permit fulfilment packet through the customer/demo read
surface. Remains smoke-blocked.

### property_intelligence

Founder data-product contract returns HTTP 200 and defines the correct evidence
requirements/delivery modes, but the current test did not establish a live
product-specific canonical-property fulfilment packet through the customer/demo
read surface. Remains smoke-blocked.

### managed_service — Empire Opportunity Intelligence Pilot

Predictive Revenue live demo is healthy and uses real read-only system state:
- radar_candidate_count=22
- research_observation_count=2
- factory_ready_count=0
- factory_blocked_count=22
- prediction_state=EVIDENCE_INCOMPLETE
- quant decision packets available=0 / unavailable=22

Therefore the system is correctly refusing to treat current opportunity
observations as fulfilment-ready product output.

## Commercially pending — 9 products

Correctly active but campaign-blocked:
- predictive_revenue_diagnostic
- predictive_revenue_command_center
- predictive_revenue_intelligence_os
- predictive_revenue_autonomous_os
- predictive_revenue_private_strategic
- exchange_seat_starter
- exchange_seat_growth
- exchange_seat_pro
- exchange_seat_enterprise

Predictive Revenue product read API is live, but binding_terms_ready=false.
Commercial Exchange/Revenue OS/Capital routers are not mounted as live API
services in the tested production surface; no campaign readiness is inferred.

## Recovered MRR — 51 products

All 51 remain inactive, non-public and campaign-blocked. Historical product
identity/pricing is not sufficient for current commercial activation.

## Digital Avatar — 3 proposal-only products

- digital_avatar_copilot
- digital_avatar_workforce
- digital_avatar_white_label_workforce

Pricing V1 is founder-approved, but the products remain off-catalog pending:
- fulfilment-cost evidence
- duration/capacity benchmark
- governed product/version proposal
- independent catalog verification
- binding terms
- product testing / real meeting proof

No Digital Avatar campaign activation yet.

## Self-serve checkout truth

Production checkout service on 127.0.0.1:8098:
- GET /v1/catalog -> HTTP 200
- product count=0
- unavailable includes competitor_search_gap, search_opportunity_map,
  solar_opportunity_map_us, technical_search_audit
- settlement rail correctly reports USDT / BSC / chain 56
- actual_revenue=false

Therefore no campaign may claim instant/self-serve purchase today.

## Campaign gate

Current strictly proven campaign-ready product codes: 9.

All other canonical products and all three Digital Avatar proposals remain
campaign-blocked until their exact product code receives live-smoke evidence.

No outbound campaign send has been performed.

## Irreversible-action evidence

- outbound_send_performed=false
- checkout_created=false
- payment_request_created=false
- funds_moved=false
- binding_terms_mutated=false
- live_meeting_join_performed=false
- revenue_recognized=false
- execution_authority=none


## Stage-2 refinement — vertical runtimes and Solar exact-SKU gate

### Permit Intelligence

Real production runtime evidence:
- source_store=runtime/acquisition/signal_inbox.json
- signal_count=6657
- resolved_count=6104
- unresolved_count=553
- source=permits_nyc
- market=NYC
- latest_seen_at=2026-10-02T21:11:31.216107+00:00
- evidence_state=EVIDENCE_AVAILABLE
- execution_authority=none
- actual_revenue=false

The deeper Permit product integration projected 6495 provenance-backed permit
opportunities. Buyer demand/delivery remains unverified and live_delivery=false.

ENGINE/EVIDENCE SMOKE: PASS.
FOUNDER READ-ROUTE DEPLOYMENT: PENDING service restart.
CAMPAIGN LIVE-SMOKE: BLOCKED until the new read route is live-verified and
customer delivery truth is accepted as sufficient for the chosen campaign claim.

### Property Intelligence

Real production runtime evidence:
- permit_signal_count=6657
- resolved_permit_count=6104
- physical_observation_count=1
- evidence_count=6658
- evidence_state=EVIDENCE_AVAILABLE
- latest_permit_seen_at=2026-10-02T21:11:31.216107+00:00
- execution_authority=none
- actual_revenue=false

ENGINE/EVIDENCE SMOKE: PASS.
FOUNDER READ-ROUTE DEPLOYMENT: PENDING service restart.
CAMPAIGN LIVE-SMOKE: BLOCKED until live read verification.

### Private Capital

Current production runtime:
- snapshot_available=true
- evidence_state=UNKNOWN
- canonical_signal_count=0
- canonical_fact_count=0
- segment_membership_count=0
- evidence_count=0
- latest_observed_at=null

ENGINE FAIL-CLOSED BEHAVIOUR: PASS.
PRODUCT LIVE-SMOKE: BLOCKED pending real canonical private-capital evidence.

### Solar exact-SKU matrix

All 13 localized SKUs are now automatically classified.

Solar-specific source contracts currently exist for:
- GB -> gb_recc_solar
- AU -> au_saa_solar
- IE -> ie_seai_solar
- DE -> de_mastr
- FR -> fr_france_renov_rge

General identity-only / solar-source research required:
- CA
- NZ
- ES
- IT
- NL
- BE
- PT

No Source Intelligence country pack:
- US

GB currently has two exact-product artifact_ready=true Solar Opportunity Map
artifacts for solar_opportunity_map_gb. However:
- retained canonical acquisition provenance for those artifact prospect IDs was
  not found in prospect_acquisitions;
- Founder source-intelligence latest proof reports verified_source_proof=false.

Therefore GB remains campaign-blocked under the exact-SKU proof rule.

No Solar SKU currently satisfies all of:
1. exact localized product code;
2. solar-specific live source;
3. exact-product ready artifact;
4. retained source provenance.

Solar focused pre-market regression: 9 passed.

### Current strict campaign state

Current actually live campaign-ready product count remains **9**:
- authority_intelligence
- competitor_search_gap
- content_protection
- geo_ai_visibility
- local_search_grid
- search_growth_command
- search_opportunity_map
- serp_intelligence_api
- technical_search_audit

Permit and Property are next in line after Founder read-service deployment/live
verification. No campaign has been sent.
