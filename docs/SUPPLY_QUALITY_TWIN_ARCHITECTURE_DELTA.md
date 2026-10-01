# Supply Quality Twin Architecture Delta

Date: 2026-10-01
Status: IMPLEMENTATION IN PROGRESS

## Diagram

Source / provenance evidence
+ candidate identity quality
+ delivery evidence
+ buyer acceptance/rejection
+ verified revenue/cost outcomes
-> Supply Quality Twin
-> operator / Predictive Revenue context

The Twin is a read model. It does not canonicalize prospects, allocate leads,
change source policy, spend money, or recognize revenue.

## Canonical boundary

Existing components remain authoritative for their own dimensions:
- candidate_quality.py: identity/canonicalization gate;
- source_health_observer.py: source availability and probe health;
- fulfilment/commercial outcome evidence: delivery and buyer outcomes;
- revenue truth / Revenue OS feedback: verified economic outcomes.

New owner:
- supply_quality_twin.py

## Identity

One Twin is keyed by:
- source_key;
- product_key;
- market_key.

Each observation has a unique observation_key and supply_id.

## Attribution

A supply item may have multiple source keys.

Commercial outcome credit is counted for a Twin only when:
- the Twin source is the sole source; or
- an explicit attributed_source_key names that source.

Multi-source supply without explicit attribution is preserved but not credited
to any source's commercial quality or economics.

Duplicate observation_key values count once.

## Dimensions

The Twin reports separately:
1. source availability evidence;
2. identity acceptance evidence;
3. delivery evidence;
4. buyer acceptance evidence;
5. verified revenue / cost / realized GP.

It does not combine them into an uncalibrated probability or quality score.

## Unknown semantics

Missing buyer outcome stays unknown.
Missing cost keeps realized GP unknown.
No source-health observation does not mean unhealthy.
Identity acceptance does not imply buyer acceptance.

Recognized revenue and observed cost are accepted only when each carries its own
dedicated evidence reference. Generic observation evidence cannot silently
establish accounting truth or realized cost.

## Positive example

A source supplies 20 unique businesses, 17 pass identity quality, 12 are
delivered, 9 are buyer-accepted, and 5 have verified commercial outcomes with
complete cost evidence. The Twin exposes those denominators separately.

## Negative examples

- One prospect found through OSM and search is not counted twice.
- A healthy Overpass endpoint with no commercial outcomes is not labelled high
  commercial quality.
- Recognized revenue with missing observed cost does not produce a fake GP.
- A rejected candidate does not automatically imply poor source economics.

## Verification

- idempotent replay;
- multi-source outcomes do not double count;
- missing cost preserves unknown GP;
- healthy source != commercial quality;
- identity acceptance != buyer acceptance;
- no execution or revenue-recognition authority;
- candidate quality/source health/revenue feedback regressions remain green.

## Authority

OBSERVE only. No canonical writes, acquisition policy mutation, allocation,
outbound, spend, terms, payment, settlement, revenue recognition, migration or
deployment authority.

## 2026-10-01 verification

Implemented:
- replayable source/product/market Twin;
- separate availability, identity, delivery, buyer outcome and economics dimensions;
- explicit multi-source attribution;
- dedicated evidence refs for recognized revenue and observed cost;
- unknown GP when cost evidence is incomplete;
- zero execution/revenue-recognition authority.

Verification:
- Supply Twin + candidate quality + source health + revenue feedback: 29 passed;
- diff check passed;
- no live Supply Quality Twin projection or attributed outcome stream is
  currently claimed from production runtime.

Status:
ENGINEERING COMPLETE / DETERMINISTIC VERIFICATION PASSED /
LIVE ATTRIBUTED OUTCOME PROJECTION PENDING REAL EVIDENCE.
