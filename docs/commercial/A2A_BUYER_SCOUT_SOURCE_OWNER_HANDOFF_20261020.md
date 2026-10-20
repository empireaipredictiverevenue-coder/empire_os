# A2A Commercial Signal Miner — Buyer Scout & Community Intent owner contract

Date: 20 October 2026
Branch: feature/a2a-commercial-signal-mining-20261020
A2A agent: empire.a2a.commercial_signal_miner.v1

## Why this build exists

The founder-directed targeting cycle already has three exact B2B research prompts:
1. Roofing companies buying leads / calls / appointments, Tampa FL
2. HVAC companies buying appointments and leads, Little Rock AR
3. Commercial construction data / permit intelligence buyers, NYC

This is designed to turn targets into verifiable commercial research using
existing source and buyer systems, instead of another agent inventing leads.

## Real owner data consumed

The new consumer reads:
- /srv/empire_os/runtime/community_intent/latest.json, using its existing
  permitted public-source atlas (handled by a previous target module)
- /srv/empire_os/runtime/buyer_acquisition/scout_latest.json, the canonical
  Buyer Scout owner's latest research output, using this new owner handoff

The new handoff does NOT invoke Buyer Scout discovery or modify its records.
It examines its current research summary and its evidence status to prevent
invented cross-references and duplicate outreach.

## What was implemented

- empire_os/a2a_target_owner_handoff_v1.py
  - enforces schema, observe-only execution, source freshness, total count and
    typed research-authority checks
  - strictly requires an exact niche AND city match, owner-verified identity,
    budget and commercial terms flags before counting even a potential
    canonical market overlap requiring owner readback
  - a match is never promoted to a qualified prospect or permission to contact
  - constructs two fixed, idempotently keyed *review requests* per target:
    community_intent: PERMITTED_SOURCE_TOPIC_REVIEW
    buyer_scout: CANONICAL_COMPANY_AND_BUYER_CAPACITY_REVIEW
  - includes only safe target dimensions, research queries, owner, source IDs,
    response acceptance criteria and a non-private aggregate Scout count
  - does not store or reproduce raw company names, emails, phones, domains,
    social authors, post content, personal identity data or financial details
  - refuses any source with externally enabled outreach, CRM writes or sales
    execution authority
  - if the Buyer Scout snapshot is missing/stale/invalid, emits a structured
    hold instead of falsely concluding zero buyers or stopping upstream research

- scripts/run_a2a_commercial_intelligence_cycle_v2_20261020.py
  - reads owner Scout snapshot read-only each hourly research tick
  - saves buyer_owner_research_handoffs_v1.json in the isolated worktree,
    separate from the existing owner's directories and records
  - prints prepared ticket count vs actually dispatched count explicitly

- tests/test_a2a_target_owner_handoff_v1_20261020.py
  - deterministic ID / deduplication, malformed source, stale snapshot,
    trust escalation, privacy leak and exact-niche/city matching tests

## Actual 20 Oct 2026 readback

The current Buyer Scout source has 9 observed candidate research rows.
No row establishes a sufficiently verified sector+city+buyer-capacity match to
the three founder targeting profiles in this preflight.

Therefore the real output is:
- 3 target profiles
- 6 PREPARED_NOT_DELIVERED research tickets
- 0 agent owner tasks dispatched
- 0 proven new buyers
- 0 outbound communications
- 0 canonical buyer records created
- 0 ad campaigns or payments

The local handoff records include 3 safe search phrases per target, but they
have NOT been executed against web/search providers by this branch. A public
social discussion is not evidence of a buyer's company identity or ability
to buy. A high research score is not a verified sale.

This source produces no direct raw prospect records and uses no new
web/search provider or paid API queries.

## Reproduce on EmpireOS

From /home/ubuntu/empire_worktrees/a2a_commercial_signal_mining_20261020:

PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  -m scripts.run_a2a_commercial_intelligence_cycle_v2_20261020 --write-local

Then view:
runtime/a2a_commercial_signal_mining/buyer_owner_research_handoffs_v1.json

## Owner-contract acceptance still needed for actual task execution

1. Community Intent/source owner accepts the bounded target-specific query
   contract and adds permitted niche-specific source records if lawful.
   Keep collection in the existing owner worker and preserve source policy.
2. Buyer Scout owner accepts the bounded target-specific query contract, reviews
   its existing canonical identity/dedupe state, and obtains company-verified
   buyer requirements before promoting anything.
3. A2A identity owner provisions production trust, signed per-agent scopes and
   persistent replay protection before any live inter-agent job dispatch.
4. Finance, advertising and email owners approve their own outbound actions.
   This research worker has no authority for them.

**No other department's files, production CRM records, source collectors,
public gateway or outbound timers were changed by this branch.**

Next implementation for the accepting owner:
- In the Buyer Scout owning branch, add a read-only ingestion of this
  source-review handoff with strict schema, signature, idempotency, TTL and
  canonical duplicate checks, then authorise a bounded research-only search.
- In the Community Intent owning branch, use the existing public RSS / licensed
  sources and record accepted target research results with provenance.
- Only once the owners deliver authenticated response receipts should this
  miner consider a target researched, rejected, or scheduled for follow-up.

The installed hourly timer keeps making read-only research reports from current
owner-issued snapshots. It does not dispatch into the owner queues yet.
