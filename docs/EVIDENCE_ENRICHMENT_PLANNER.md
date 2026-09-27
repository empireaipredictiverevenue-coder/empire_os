# Evidence Enrichment Planner

## Purpose

Turn Lead Scoring v2 confidence gaps into the smallest bounded evidence-collection
plan without performing network work, mutating prospects, or triggering outreach.

The planner is deliberately separate from execution. A projected gain is an
upper bound only; missing evidence remains unknown until a source actually
returns and passes verification.

## Current confidence target

Lead Scoring v2 requires evidence confidence >= 0.50 before a quality band may
become a commercial decision tier.

For normal canonical prospects, observed business name/niche make market fit
observable, giving 0.50 quality-dimension coverage. The usual bottleneck is
therefore data completeness below 50.

## Current bounded capability

The first executable planner action is the existing
prospect_enrichment first-party site probe:

- Search Fabric may discover a likely direct business website;
- the identity guard must accept the site;
- same-site probing is bounded;
- public evidence may yield website, email, phone, address and social links;
- rejected/failed sites contribute no evidence;
- no prospect record is mutated by the enrichment module.

For completeness planning, only evidence fields actually consumed by the scorer
are credited. The site action can currently close missing website, email and
phone gaps. Address is counted as street evidence when it already exists on the
canonical prospect, matching the existing v1 canonical adapter semantics.

## Future evidence capabilities

The planner may describe but does not execute unavailable actions:

- decision-maker evidence: direct public/licensed named-person evidence;
- public registry/licensing evidence: licence and structured address fields.

Unavailable capabilities never count toward current reachability.

## Output contract

Each plan reports:

- current completeness and evidence confidence;
- missing evidence fields;
- ordered candidate actions;
- selected actions available today;
- maximum completeness gain per action;
- projected completeness/confidence upper bounds;
- whether the target could be reached if all selected evidence is actually found;
- an explicit projection_is_not_observation flag.

The plan never fabricates values or claims evidence will be found.

## Production use

This slice is planning-only. No batch web enrichment, prospect writes, v2
qualification writes, buyer allocation changes, or outreach are activated by
the planner.
