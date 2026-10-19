# Empire AI — Buyer Scout Economic Intelligence / First-Payer Gap Board
**19 October 2026 — Lead Revenue Fabric owner. Continuation of buyer Scout business awareness.**

## Why this module exists

The existing Scout is already capable of collecting first-party buyer-role clues,
scoring discovery and preserving evidence, while the Commercial Relationship
Registry owns contact history and partner-pilot activation gates. What was missing
was a **single deterministic, bounded economic next-task view**.

Do not equate:
- a public agency website with a direct payer;
- an intermediary/publisher partnership pitch with own-funds purchasing;
- a two-way email conversation with an authorised buyer specification;
- a marketing KPI or capacity proxy with an actual daily approved cap;
- a stated payout with an agreed payable event or collected revenue;
- a synthetic lead or modelled expected value with fulfilled/paid inventory.

## Verified read-only checkpoint, 19 October

- Canonical Scout latest: **3** B2B research candidates.
- Existing founder-reviewed target queue: **25** businesses.
- Commercial relationship history: **259** recorded relationships.
- **4** existing partner-pilot conversations; all 4 indicate two-way
  thread evidence but have **0/9** verified activation gates.
- Specifically **4 missing verified buyboxes**, **4 missing payable
  events/terms**, **4 missing target geography** and **4 missing
  founder traffic authorisation**.
- Global Gmail snapshot `gmail_snapshot_fresh=false`. Historical per-pilot
  `mailbox_snapshot_fresh=true` is not proof of current live reply.
- The buyer economics **review confirms zero activated paid pilots** and
  does not authenticate daily cap, payment amount or purchasing budget.

The existing `empire_os/buyer_specification_readiness.py` already
defines 9 precise partner gates. This module **reuses those exact gates**;
it does not define a competing readiness/activation standard.

## Implemented source files

1. `empire_os/buyer_scout_economic_intelligence.py`: strict read-only
   9-gate pilot and Scout business gap board; validates relationship
   snapshot identity with the separate commercial-awareness evidence
   version; no contact PII, raw email text, person name, price, thread ID
   or data export.
2. `scripts/review_buyer_scout_economics_20261019.py --read-only`:
   aggregate/current economic review from the existing Scout, founder
   qualification actions and relationship registry.
3. `scripts/run_resilient_buyer_scout_20261019.py`:
   add **nonblocking, aggregate-only economic gap counts** to the
   existing owned fallback cycle. If evidence is malformed or stale,
   emits `HOLD_ECONOMIC_REVIEW_SOURCE`, never silently approves buyers.
   No new probing, search, permissions or timers.
4. Synthetic tests: source staleness, duplicate pilot keys, invalid or
   partially satisfied gates, false buyer economics, partner deferral,
   historic inbound requirements, intermediary roles, PII exclusion,
   suppression and fallback failure isolation.

## The actual business questions to resolve, in this order

1. **Buyer role:** Who spends their OWN money acquiring the lead/call/
   appointment? Differentiate direct buyer, broker, marketplace,
   affiliate publisher and service provider. Never infer role from
   website marketing copy alone.
2. **Specific buybox:** What niche, territory, product, exclusivity
   requirement, lead age, source origin, homeowner/business eligibility,
   consent basis, permitted hours and lead-quality threshold?
3. **Payable event and terms:** Is this pay-per-click, pay-per-lead,
   pay-per-call, pay-per-qualified-call, pay-per-appointment or
   performance/retainer? What evidence triggers payment, with currency,
   billing period, payment timetable, returns/refunds and dispute terms?
   Historical claimed prices are never binding without owner validation.
4. **True funded capacity:** How many units per day/week/month, for
   which corridor, with which daily cap and delivery acceptance path?
   Confirm budget availability/credit approval from the buyer owner.
5. **Activation mechanics:** Independent source/use approval, landing
   compliance, tracking, buyer-specific routing, contract, privacy,
   suppression, dispute rules and founder activation are *separate*.
6. **Why now:** Genuine demand, active intake constraints, geo/niche
   expansions, approved pilot criteria and payer authority; public
   "accepting affiliates" does not count.
7. **Trust and relationship memory:** Check existing thread history and
   bounce/suppression before any founder-approved follow-up. A company
   should not receive duplicate first-introduction emails.

## Business-outcome hierarchy

`RESEARCH_CANDIDATE` → `IDENTITY_VERIFIED` →
`BUYER_ROLE_AUTHENTICATED` → `BUYBOX_AND_PAYABLE_TERMS_VERIFIED` →
`FUNDED_CAPACITY_VERIFIED` → `PILOT_CONTRACT_AND_ROUTING_APPROVED` →
`FOUNDER_LIVE_ACTIVATION` → `FULFILLED_ACCEPTED_DELIVERY` →
`INVOICE_COLLECTED`.

All stages are independent facts; counts in one stage must never be
silently promoted to another. This module does NOT perform promotion.

## Existing ownership and risk controls

- Canonical DB: **EmpireDB PostgreSQL**.
- Primary Scout, Buyer Network, CRM, contract, buyer specification,
  Lead Smart and Predictive Intelligence files are owned by other
  agents; **do not edit those modules here**.
- No uncontrolled prospect/consumer collection. No cold messaging,
  SMS, new timer, public paid search, funds, routing, terms/contract,
  traffic or database writes.
- Output prioritisation is **evidence research urgency** rather than
  measured buyer conversion probability.
- No direct cross-source company merge by name or suggested domain;
  exact-domain research and CRM-proven identity relationships only.

## To run the private current gap board

```bash
cd /home/ubuntu/empire_worktrees/lead_revenue_fabric_unified_20261019
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  -m scripts.review_buyer_scout_economics_20261019 --read-only
```

The result can inform a founder's existing conversation owner about
missing buyer data, **not** grant authority to send or run traffic.

## Deployment truth / release gate

A commit in the Lead Revenue Fabric worktree alone does not upgrade
the live fallback. Release only from an immutable clean pinned commit,
verify exact known cron line and backup/rollback, and observe one
scheduled cycle with `buyer_economic_gap_observation` but no added
search/contacts/DB writes. The original
`empire-buyer-acquisition-scout.service` must stay unchanged.
