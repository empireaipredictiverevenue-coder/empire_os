# Lead Scoring v2 — Evidence-Aware Qualification

## Why v2 exists

Production inspection showed that v1 qualification systematically treated
missing evidence as zero. Across the 466 prospects with both active canonical
identity and a v1 qualification:

- 359 were cold and 107 dead;
- 0 were warm or hot;
- average v1 score was 37.06;
- average market-fit score was 76.82;
- engagement-potential and enrichment-quality were exactly 0 for all 466.

Those zeros are not reliable negative observations. Legacy/canonical ingestion
paths can default absent lead/buy-signal values to 0 or 50, and v1 also injected
missing omega/enrichment values as zero.

## v2 contract

v2 separates:

1. quality score — calculated only from observed dimensions;
2. evidence confidence — conservative sufficiency of the observed evidence;
3. decision tier — commercial interpretation gated by confidence.

Unknown dimensions remain null rather than silently becoming zero.

Quality dimensions:
- market fit;
- business presence;
- engagement potential;
- enrichment quality.

Data completeness is evidence sufficiency rather than direct commercial quality.
Known directory and social-profile URLs are not counted as first-party website
presence or website completeness. They remain discovery/provenance evidence until
a first-party business site is independently identified and verified.

A quality band may be hot/warm/cold/dead, but when evidence confidence is below
0.50 the decision tier is insufficient_evidence.

## Production replay

A read-only replay of the same 466 identity+qualification prospects, treating
engagement/enrichment as unknown rather than zero, produced:

- average underlying quality: 61.90;
- average evidence confidence: 0.3028;
- 466 insufficient_evidence;
- 0 hot/warm/cold/dead decisions.

Interpretation: v1 was materially depressing quality, but the current evidence
is still too sparse for governed commercial selection. The next step is
targeted enrichment, not looser thresholds.

## Storage

The staged v2 schema extension:

- adds evidence_confidence;
- adds observed/unknown dimension arrays;
- permits nullable quality/dimension fields where evidence is unknown;
- preserves all existing v1 rows;
- relies on the existing unique key
  (prospect_id, scoring_engine, scoring_version) so v1 and v2 coexist.

No v1 consumer is switched by this slice. Buyer allocation remains pinned to v1
until v2 has been validated on real enriched evidence.

## Canonical address normalization

Canonical prospects store published address evidence in the address field, while
the legacy completeness scorer names its equivalent field street. v2 preserves
the existing canonical adapter behavior by counting address as street evidence
when an explicit street field is absent. No address components are inferred.

## Targeted enrichment planning

The evidence-enrichment planner uses the v2 completeness/confidence result as its
single source of truth. It prioritizes the existing bounded first-party site
probe for missing website/email/phone evidence and keeps unavailable registry or
decision-maker adapters out of current reachability calculations.

## Production gate

The v2 migration, v2 qualification writes and any consumer cutover remain gated.
