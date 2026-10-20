# Empire AI: A2A Commercial Signal Intelligence V2 — tested research expansion
20 October 2026
Owner: empire.a2a.commercial_signal_miner.v1
Branch: feature/a2a-commercial-signal-mining-20261020

## Outcome and execution boundaries

Built and ran a deeper, deterministic research decision layer on existing EmpireOS
data. No synthetic customers, leads, sales or financial transactions are included
in outputs. Unit tests use local test fixtures only, not commercial records.

No production deployment, service registration, scheduled daemon, Meta/Instagram
account access, new crawler, database write, contact, public publishing, spend,
payment link, agent cryptographic registration or financial operation was made.
Other agents retain ownership over source collectors, Buyer Scout, Data Brokerage,
campaign release, Predictive Revenue, Finance OS and A2A identity.

## Built components

- empire_os/a2a_signal_decision_intelligence_v2.py
  - validates that incoming signal reports, campaign releases and product catalogue
    are read-only, correctly typed, and do not claim verified buyers, payments
    or externally authorised execution
  - rejects future/invalid timestamps, duplicated segment IDs, invented monetary
    fields or product licence promotion
  - tracks novelty and genuine changes to market research records over time
  - distinguishes source collection health from independent purchase evidence
  - applies a separate capped QUALITY TRIAGE SCORE, explicitly NOT a purchase
    probability or currency projection
  - identifies rights, product deliverability, explicit buying demand, geo and
    publishing blockers, and recommends existing-department research tasks
  - suppresses duplicate *new* research handoffs for unchanged research signals
  - does NOT suppress manual owner revalidation of stale data or contracts

- empire_os/a2a_opportunity_graph_v2.py
  - deterministic JSON graph: source reports -> market hypotheses -> geographies
    -> proposed data products -> owning departments -> draft campaigns
  - no real-world personal-identity nodes, buying committee claims or payment edges
  - does NOT pretend separate rows within one aggregate report are independent
    confirmation, and does NOT create an external Graphify/Neo4j database

- empire_os/a2a_evidence_history_v2.py
  - bounded worktree-local history of SHA-256 hashes from the real owner-provided
    source files
  - identical source bytes do not generate a second source-event record
  - retains max 90 source-version observations; no raw social conversations,
    customer contact details or financial credentials
  - report SHA-256 digests detect working-copy changes, not original-source
    signatures or source reuse rights

- scripts/run_a2a_commercial_intelligence_cycle_v2_20261020.py
  - reads current first-party, owner-issued runtime JSON snapshots
  - runs signal miner -> targeted campaigns -> NYC source/product preflight ->
    release review -> decision intelligence -> knowledge graph -> evidence history
  - prints concise status; --write-local writes files only under the isolated
    research worktree
  - does not run automatically or dispatch research tasks to other agents

## Real read-only source inputs

/srv/empire_os/runtime/community_intent/latest.json
/srv/empire_os/runtime/market_sweeps/revenue_gps_latest.json
/srv/empire_os/runtime/data_brokerage/internal_product_catalog_latest.json
/srv/empire_os/runtime/data_brokerage/nyc_dobnow_property_three_agency_latest.json
/srv/empire_os/runtime/data_brokerage/nyc_dobnow_property_three_agency_latest.provenance.json

The local research reports are stored under:
runtime/a2a_commercial_signal_mining/

Outputs added:
decision_intelligence_v2.json
opportunity_evidence_graph_v2.json
evidence_history_v2.json

The same cycle also refreshes source-reviewed signal/campaign, NYC preflight,
release, A2A handoff-plan and local agent-card reports.

## Actual current readback

- 15 business/market research candidates; zero independent verified new buyers.
- 5 targeted campaign drafts; 0 founder/owner-approved launches.
- 44 knowledge graph research nodes; 92 explanatory research links.
- 35 previously proposed research steps suppressed as NEW task reissues in a
  repeat run. Existing owner review obligations still apply.
- latest community-source audit indicates Reddit retrieval works, LinkedIn
  public-source retrieval is degraded/circuit open.
- the Data Brokerage product catalogue is now older than the default 48-hour
  freshness threshold. Its four products remain unreleased and without
  authenticated customer-delivery licences.
- NYC general-contractor market's research ordering score is 80 but capped
  quality-adjusted triage score is 45. **This is NOT a 45% probability.**
- Existing NYC DOB report links 36 event records to a founder-directed derived
  report and matching digest, not to 36 commercial leads.
- no authenticated conversion labels, actual paid appointment, settled payments
  or source-rights grants learned in this cycle.

Regression: 61 tests passed in the extended source/negotiation/A2A/market suite,
with one third-party deprecation warning (Starlette/AnyIO).

## Run / verify

cd /home/ubuntu/empire_worktrees/a2a_commercial_signal_mining_20261020

PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
 -m scripts.run_a2a_commercial_intelligence_cycle_v2_20261020 --write-local

PYTHONPATH=. /srv/empire_os/.venv/bin/python -B -m pytest -q \
 tests/test_a2a_evidence_history_v2_20261020.py \
 tests/test_a2a_signal_decision_intelligence_v2_20261020.py \
 tests/test_a2a_nyc_commercial_evidence_gate_20261020.py \
 tests/test_a2a_data_campaign_release_review_20261020.py \
 tests/test_a2a_commercial_signal_miner_20261020.py \
 tests/test_a2a_data_campaign_workflow_20261020.py \
 tests/test_a2a_discovery.py \
 tests/test_a2a_commerce_intent.py \
 tests/test_a2a_negotiation.py \
 tests/test_a2a_handoff.py

## Next commercial expansion priorities (NOT YET IMPLEMENTED)

1. Product rights: Data Brokerage independently sign off per NYC source/dataset
   field, attribution, permitted commercial use, customer sample and delivery.
2. Buyer verification: Buyer Scout inspect canonical first-party company
   records, evidence of actual NYC data-buying need, buyer budget/capacity and
   suppress existing outreach duplication. No automatic outreach from this branch.
3. Verified revenue feedback: after actual customer agreement and payment,
   allow Finance OS/canonical owners to provide authenticated outcome labels.
   Only then consider learning conversion rates or monetary ROI.
4. Source quality: owner repairs LinkedIn public retrieval or replaces it with
   documented permitted source; never use private Group scraping or counterfeit
   source success.
5. Source breadth: property/permit licences, local business official sites,
   demand analytics, event-driven weather/project data, first-party CRM,
   customer support and consent-based Meta business data. Build separate
   licensed-source adapters, no invented data.
6. Graph enrichment: verified canonical company IDs, documented supplier-buyer
   edges, geography and recency, dedupe across channels; no speculative people
   identity matching.
7. Test campaigns: original first-party organic campaigns tied to a truly
   deliverable data product and actual buyer cohort; controlled opt-in,
   conversion/ROI instrumentation, no campaign before founder release.
8. A2A execution: once approved, register a signed Ed25519 agent identity and
   the existing role owners' typed contracts before remote dispatch or money.
9. Finance: approved hosted checkout, invoice, settlement and reconciliation
   under Finance OS; no real bank/card details placed into language prompts.
10. Feedback and exploration: rank not only strong signals but missing proof
    whose collection would unlock the highest-value legal/operational question.

## Known limitations / caution

All current signal scores are deterministic REVIEW HEURISTICS, not calibrated
probabilities, AI model weights, verified purchasing demand or revenue predictions.
A community thread never identifies a consented buyer by itself. A high NYC
construction score can coexist with zero paying customers. A digest match to a
locally generated evidence receipt is NOT cryptographic proof from source agencies.
This package operates as an offline analysis cycle, not a production agent
continuously performing social data collection, sending messages or buying goods.
