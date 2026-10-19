# EmpireOS — Exact-Market Buyer Linkage (first-party evidence bridge)

19 October 2026. Owner branch: feature/predictive-decision-control-20261018.

## Why this improvement matters

Our first-party commercial desk task (commit daf98679) identified the
highest-priority genuine evidence requirement but did not safely connect
that market-research candidate to the existing canonical buyer projection.

A *buyer record* can only be considered a market-overlap candidate when
its niche AND exact configured metro agree with the same specific Radar
opportunity. A public permit/tender or matching niche alone cannot
establish a buyer conversation, validated buybox, buying authority, company
contract or revenue.

This adds one restricted read-only market correlation adapter. It does not
create a new CRM reader, data lake, buyer allocator, queue or agent.

## Scientific/data-quality controls

- Reuses `review_one_commercial_evidence_request` and the existing four-
  source pathway join: Radar → Factory → blocker router → Quant Brain.
  Any invalid/future/stale/tenant-scoped source or changed opportunity
  receipt is held before buyer comparison.
- The prepared evidence-request fingerprint now includes an opaque digest
  of the original niche+metro source identity, not raw contact or buyer
  data. If an opportunity's market location changes, its research request
  and eventual deterministic ASTRA work ID change.
- Uses exact case/whitespace-normalised niche and metro string equality.
  No partial matching, AI geocoding, name guessing or UK/US equivalence.
  Missing/invalid markets cannot match.
- Rejects buyer records carrying tenant scope in a founder-global preview
  (tenant-specific evidence needs its owning authenticated reader).
- Reuses `buyer_specific_buybox_review.review_buyer_buybox_candidates`
  to measure same-record configuration and historical evidence gaps;
  even all nine completed preparation fields do NOT authenticate exact
  product/postcode, current buying consent, terms or settlement.
- Source rows capped at 10,000 and returned candidates at eight; buyer
  names, addresses, endpoint contact details and raw IDs are not shown.
- Counts are three separate denominators: canonical records observed,
  same-niche records and exact-niche-plus-metro records. This is a
  SOURCE MATCH COUNT, not a lead count, buyer conversion rate or qualified
  customer population.
- If the canonical gateway is unavailable, exact market counts are NULL
  and status is CANONICAL_BUYER_GATEWAY_UNAVAILABLE. Unknown never becomes
  0; malformed source rows likewise hold rather than produce a false zero.
- No payment, outbound email, CRM mutation, private tenant exposure,
  model weight update, inferred probability or Economic Memory outcome.

## Actual observed production snapshot

- Four read-only source snapshots: 11 market-research opportunities, zero
  complete Quant economics packets, first prioritised buyer-intent gap
  in the Little Rock, Arkansas roofing market.
- Existing Workspace solar outreach snapshot concerns six UK solar threads
  with zero inbound header candidates as of its observed time. It cannot
  be used as proof for Arkansas roofing or another unlinked opportunity.
- Existing aggregate buyer-capacity snapshot previously reported 1,057
  buyer records, one reviewed, zero verified commercial terms, zero
  verified delivery, zero fully activated.
- A live restricted buyer-projection read via the **existing** EmpireDB
  `fetch_all_buyers` returned `DataGatewayUnavailable` from the current
  developer agent session. We therefore do NOT claim any exact
  Little Rock match count, nor claim there are zero such buyers.
  We have not changed service credentials or DB permissions to bypass it.

## Safe manual commands (feature branch)

```bash
cd /home/ubuntu/empire_agents/predictive_decision_control_20261018

# Read only existing source-pathway snapshots, NO buyer DB call:
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  -m scripts.review_first_party_buyer_evidence_20261019

# Explicit optional bounded canonical BUYER QUERY; read-only, no CRM writes:
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  -m scripts.review_first_party_buyer_evidence_20261019 \
  --inspect-existing-buyer-projection
```

The existing queueing flag is mutually exclusive with the buyer-inspection
flag, so this review cannot accidentally enqueue an ASTRA task while
inspecting buyer records.

## What the next owner must do

1. Coordinate deployment of the base ASTRA/Founder Console commits and
   this exact-market adapter. Do not overwrite other agents' live files.
2. Give the existing canonical buyer **read-only** service the authorised
   execution context and verify source freshness and permitted tenant scope.
   Do NOT create a second privileged reader or broaden DB grants casually.
3. Check an exact-market candidate, then find a genuine canonical CRM
   inbound request or written buyer terms for the same organisation, product,
   market, coverage, buying decision and time window through the owning
   tenant-specific authenticated private view.
4. Confirm real price, delivery cost and capacity before constructing Quant
   inputs. Any probabilities require historical terminal outcomes and
   prequential calibration, not a completeness score.
5. Only afterwards register original prospective predictions before future
   outcomes and reconcile real settlement/fulfilment to Economic Memory.

All work here remains feature-branch only: no production deployment,
query success claim, outbound, payments or DB mutations.
