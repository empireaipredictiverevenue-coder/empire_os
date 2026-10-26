# TAM Revenue Portfolio V2 — Leads Exchange integrated read-only

**Owner:** existing TAM Market Intelligence department.
**Status:** isolated code release; production promotion not yet performed.
**Date:** 26 October 2026.

## Purpose
Make existing TAM Intelligence recognise the whole Empire AI commercial ecosystem, including both sides of the Leads Exchange, without creating a new database, parallel CRM, agent or timer. The upgrade is implemented as a read-only projection from already saved, canonical EmpireDB-backed receipts.

## Owned change
- `empire_os/tam_revenue_portfolio.py`: 16 product families, separate commercial buyer/seller roles and guarded market coverage evidence.
- `empire_os/tam_market_runtime.py --portfolio`: integrate read-only portfolio inspection into the **existing** TAM entry point. It does not connect to EmpireDB or change the normal `--refresh` / `--preflight` behaviour.
- `tests/test_tam_revenue_portfolio.py`: deduplication, provenance, blocked-seat, price, source and authority regression checks.

## Canonical read inputs
1. `runtime/tam_market_intelligence/latest.json` (TAM 043/044 restricted source observation; may be stale, not a verified country-market census).
2. `runtime/commercial_exchange/latest.json` (qualification-driven supply, buyer seats, state and remaining capacity).
3. `runtime/revenue_exchange/latest.json` (verified-price independent reconciliation gate).

New output is aggregate-only JSON to stdout:
```
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  -m empire_os.tam_market_runtime --portfolio --repo-root /srv/empire_os
```
The command is read-only and requires no new credentials or database role. It does not expose prospect names, contacts, buyer identifiers or source URLs.

## Commercial interpretation and limits
- The Leads Exchange has **two markets**: paying buyers and publishers/suppliers, alongside inventory prospects and governed buyer seats.
- Inventory rows, unique prospect ids, buyer ids, buyer seats, active capacity and reconciled exchange markets are distinct quantities. They must not be summed into a company TAM.
- A blocked buyer seat is not an active buyer. An observed price is not a verified payable rate.
- Company employee count, turnover, named decision-maker, verified email, lead intent, available customer count, market population, revenue potential and realized income remain **unknown** until source-backed feeds provide them.
- Product families overlap: a contractor may buy software, purchase leads and sell services. One legal company must be counted once at the company layer.
- Market totals require independently sourced denominators with country, sector, date, methodology, legal/company-unit definition and lineage; counts from a company's internal acquisition roster do not qualify.

## Pilot evidence reviewed, 26 October
- Saved TAM evidence snapshot from 10 October is stale and contained 8 observed canonical source companies in US roofing, not a population estimate.
- Canonical Commercial Exchange showed 184 distinct prospects in 184 inventory rows: 97 qualified overflow, 87 blocked, 0 active buyer seats out of 1,057 observed seats, 0 verified market price observations.
- Revenue Exchange had 0 observed markets.
- The observational results **do not demonstrate additional customer acquisition, fulfilled leads or revenue**.

## Next owner handoff
1. Fold the scoped source-only commit into the existing TAM owner release channel without overwriting concurrent owners' dirty files.
2. Preserve the current 043/044 privileged read boundary. Do not invoke the protected one-shot market refresh without separate scoped authority.
3. Add first-party verified company/contact/size/turnover evidence and independent government market denominators to the established TAM + CRM + exchange read contract; avoid counting establishments as unique companies.
4. Show the aggregate view in Founder Console under the existing TAM owner in a coordinated frontend release, after tenant read authority and snapshot freshness checks.
5. Address the commercial owners' blocked seat and pricing evidence separately. This implementation creates no buyer activation, outbound, payment or settlement authorization.

## 26 October source-backed Leads Exchange market-gap extension
Added `leads_exchange_market_gaps` to the existing `--portfolio` output. It groups qualified inventory by **exact** niche and metro only, deduplicates prospect ids within each market, and compares against already observed buyer seats in the same niche/metro. The market join is a **research signal**, never an allocation-eligibility or buyer-capacity authorization. It identifies missing geographical evidence rather than inferring territory coverage. Output includes bounded top 25 markets, complete niche summaries, source observed seat blocker reasons, and no buyer/contact names.

Readback against saved production evidence (2026-10-26): 97 distinct overflow prospects across 63 niche/metro markets, all 63 without active same-market seats; 950 of 1,057 buyer seats have no usable metro; blocker reasons 874 inactive, 156 not commercially activated and 27 test-identity held. Sector distributions: roofing 38 in 18 markets; HVAC 17 in 12; plumbing 17 in 11; landscaping 8 in 6; electrical 6 in 6; painting 6 in 5; carpentry 3 in 3; pest control 2 in 2. No buyer capacity, price or revenue is inferred. The TAM roster snapshot remains stale (from October 10) and does not provide company-population denominators.

Test outcome: 105 focused TAM regression tests PASS in the isolated worktree. The separate main production branch and frontend/dashboard remain unchanged.

## 26 October — historical 32,899 prospect cohort recovery

The retained September 27 EmpireDB migration archive was audited locally, aggregate-only. It contains 32,899 unique prospect IDs from June–September. Their sorted ID digest exactly matches the separately verified migration evidence: `998bea32ad0fa1539e65d0ebb88b119078289db87db3ca1b06d8b9f9bc27ead2`. This proves the archived cohort identity, not the October live census.

There are 4,285 historically qualified records, 3,109 with v2 scoring, 29,790 without v2, 12,301 historically identity-linked, and 20,598 without a historical active identity link. Exactly 160 archived IDs intersect today's 184 selected Commercial Exchange prospects. Historical contact-field presence does not imply current verification or outbound rights.

The specific backfill defect: production v2 qualification only checks the newest `limit*4` records, so it may find zero pending while thousands of older records remain. A separate, oldest-first page selector and durable private cursor are staged in this isolated branch. The existing v2 scorer is reused, without changing the 0.50 evidence floor or buyer/outbound/payment authority. The backfill is opt-in (bounded to 25 per run) and is not enabled by the existing scheduled service.

The TAM portfolio now supports an optional historical dump aggregate read, keeping the historical cohort distinct from current Exchange/Market GPS. Full production activation requires the existing Qualification owner to promote its source delta through the permitted release path, verify the first small scoring batch, and then continue measured cursor progress; the TAM owner can separately release the read-only presentation code. Neither release changes blocked buyer seats or independently unverified prices.
