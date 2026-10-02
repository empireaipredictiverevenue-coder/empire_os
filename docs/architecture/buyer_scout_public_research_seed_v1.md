# Buyer Scout Public Research Seed — Architecture Delta V1

Date: 2026-10-02
Status: BOUNDED / OBSERVE-ONLY
Change class: Architecture delta
Owner: Buyer Acquisition Team / Market Intelligence

## Purpose
Search Fabric can return weak or irrelevant domains even when first-party public evidence identifies a real lead/call buyer or publisher network.
This delta lets externally observed first-party domains supplement Buyer Scout discovery without bypassing site probing, reconciliation, review readiness, or commercial evidence gates.

## Canonical placement
Existing owner remains `empire_os.buyer_acquisition_scout`.
No new buyer database, allocation path, outreach system, or settlement path is created.
Upstream input is a bounded runtime research-seed artifact with source URLs and provenance.
Downstream flow remains Scout -> reconciliation -> holding candidate -> review -> promotion.

## Truth and authority
Research seeds are OBSERVED PUBLIC RESEARCH only.
A seed does not prove buyer identity, capacity, territory, price, terms, budget, contact identity, or intent.
The scout must still probe first-party evidence and existing downstream gates remain authoritative.
Execution authority remains none; no outbound, allocation, terms, payment, revenue recognition, or funds movement.

## Interface
`run_buyer_scout(..., research_seed_records=...)` accepts explicit domain/URL research observations.
Seeds may provide target buyer pools and source provenance but cannot set verified commercial fields.
`refresh_buyer_scout` may load `runtime/buyer_acquisition/public_research_seeds.json` when no explicit seed list is supplied.

## Failure behaviour
Malformed seeds are skipped.
A seed with no valid first-party host is ignored.
Site probe failure produces no candidate.
Missing pricing/capacity/territory remains UNKNOWN.
Research-seed presence never authorizes persistence, promotion, outreach, or allocation.

## Verification
Focused tests must prove:
- weak Search Fabric results can be supplemented by a known first-party buyer domain;
- the seed is still site-probed;
- direct-buyer status comes from probed first-party evidence, not from the seed claim;
- pricing/capacity/terms remain unverified;
- outbound and execution authority remain false/none.

Rollback: remove research-seed loading; existing Search Fabric + canonical-seed behavior remains intact.
