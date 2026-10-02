# Official License Identity Volume Architecture V1

Date: 2026-10-02
Owner: Buyer Identity / Revenue Acquisition
Mode: evidence acquisition only

## Diagram

official state open data
-> bounded periodic cache refresh
-> normalized active-license records
-> conservative company-name match
-> named licensed professional seed
-> existing first-party identity corroboration
-> existing person-bound email verification
-> existing buyer review gate
-> governed outbound

## Texas TDLR source

Texas publishes TDLR license-holder open data. Empire caches only the A/C
Contractor slice needed for home-services identity recovery. The cache is
derived evidence and may be rebuilt; the official source remains authoritative.

## Truth and authority

A license record proves only a public association between the named license
holder and listed business. It does not prove buyer authority, outreach
readiness, email ownership, commercial terms, capacity or intent.

The license principal remains a search seed. Existing identity recovery must
corroborate the same person on the first-party company site before promotion.
Existing contact verification and buyer-review gates remain mandatory.

## Runtime design

The full Texas A/C contractor slice is refreshed outside the per-buyer worker
and stored under runtime/license_identity. Per-buyer recovery reads the local
cache, so four parallel enrichment lanes do not each download the registry.

Fresh-cache failure keeps the last valid cache and fails closed if no cache
exists. No database write, outbound send, call, term acceptance, payment or
revenue recognition occurs in the cache refresh.

## Scaling objective

Convert Texas HVAC no_decision_maker cases into attributable owner/license
search seeds at zero paid-data cost while keeping personhood requirements
unchanged.

## Net-new market discovery

The same active-license cache also feeds a rotating research-only market lane.
Each Buyer Scout cycle selects a bounded slice of active, named A/C contractor
businesses, searches exact business + location, removes directory/social hosts,
and passes discovered domains into the existing first-party Buyer Scout probe.

Registry identity is retained only as a search seed. The scout still derives
business identity and people from the discovered first-party site before any
review or promotion path can proceed.
