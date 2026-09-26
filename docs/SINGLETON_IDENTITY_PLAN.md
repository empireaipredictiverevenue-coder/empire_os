# Singleton Evidence Identity Plan

Status: local/tested. One explicitly approved bounded production promotion has been completed; automatic or bulk promotion remains gated.

## Purpose

The bulk identity resolver deliberately leaves singleton prospects unresolved.
That is correct for weak singleton data, but it also blocks a prospect when
canonical acquisition provenance and an independently verified first-party site
provide multiple agreeing identity signals.

`empire_os.singleton_identity_plan` handles only that narrow case. It does not
relax the bulk resolver and performs no database, network, credential, or
outbound action.

## Fail-closed evidence contract

A singleton proposal is emitted only when all of the following agree:

- acquisition quality is accepted;
- acquisition source role is `identity_or_direct`;
- acquisition confidence is at least 90;
- normalized acquisition and prospect business names match exactly;
- normalized acquisition and prospect phones match exactly;
- acquisition website domain equals the verified first-party domain;
- the first-party identity guard accepted the site;
- the verified site independently corroborates the source phone.

Any missing or conflicting assertion raises an error rather than producing a
candidate.

## Output semantics

A successful result is an `evidence_resolved_candidate` with:

- a deterministic candidate entity UUID;
- explicit evidence assertions;
- association confidence and its concrete basis;
- `dry_run=true`;
- `writes_performed=0`;
- `promotion_ready=false`;
- `requires_explicit_production_approval=true`.

The association confidence describes deterministic agreement of the identity
evidence. It is not outcome-calibrated predictive confidence.

## Phase 3F proof candidate

Read-only production review identified All Star Roofing in Austin as the first
current opportunity that can satisfy this path:

- canonical acquisition source: Overpass / OpenStreetMap;
- acquisition evidence includes the published business website and phone;
- the first-party site verifier accepted the domain;
- the site phone matches the acquisition/prospect phone;
- evidence-aware qualification replay reaches the governed decision-confidence
  floor without inventing engagement evidence.

The explicitly approved bounded production activation created the deterministic All Star Roofing business entity, its one active prospect link, and one v2 qualification. Materializer rows, materializer runtime roles, outreach, buyer allocation, commercial terms, and payments remain unwritten/gated.
