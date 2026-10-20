# Empire AI — Seats, Lanes, Corridors + A2A: Fulfilment/MRR Foundation

20 October 2026. Isolated review worktree; no production deployment.

## Commercial product boundaries

- Seats: recurring buyer memberships. The existing founder-approved nonbinding catalogue offers Starter $99, Growth $249, Pro $499 and Enterprise $999 per month in USD.
- Lanes: industry / sector market families.
- Corridors: territory, demand type and delivery-route requirements. A seat does not imply any volume guarantee or exclusive rights without accepted contractual terms.
- Usage: individual lead delivery, acceptance, disputes and separately evidenced transaction revenue, additional to the recurring membership model.
- A2A: first-party public company-site research, not individual person enquiries and not automatically saleable Exchange stock. No source research should inflate buyer capacity, paid entitlement, billed usage or MRR.

## Fresh observed sources at build time

Canonical EmpireDB Commercial Exchange read-only projection, 20 October at approximately 18:28 UTC:

- Selected inventory rows: 175; evidence held: 84; no capacity overflow: 91.
- Existing buyer-seat records: 1057; verified capacity seats: 0.
- Allocation candidates: 0; allocated: 0.
- These are bounded selection/seat counts, not paid subscribers, deliverable leads or settled revenue.

Existing Buyer Scout A2A owner queue (isolated workspace):

- 7 first-party company website review tasks (3 Tampa roofing, 3 Little Rock HVAC, 1 NYC general contractors).
- 2 held sites, 7 historical permit-name hypotheses.
- These are not verified lead buyers; no canonical EmpireDB company-match reads, no accepted purchasing contracts, no consumer enquiries or commercial fulfillment proven.
- Queue alone does not prove freshness; the original collector timestamps/receipt hashes still require source-owner review.

## Isolated code / tests

- empire_os/exchange_self_serve_fulfilment_review_v1.py: combines only existing canonical Exchange summary and optional nonbinding interest receipt. Keeps subscription entitlement and per-lead fulfilment as separate lifecycles and maintains independent gate checklists.
- empire_os/exchange_a2a_research_signal_bridge_v1.py: aggregate-only A2A data with strict authority/duplicate validation. No private domains/emails, contact or sellable-lead claims emitted.
- scripts/review_exchange_self_serve_fulfilment_mrr_20261020.py: bounded, no-write operator report reading current snapshot and optional A2A owner queue; no payment provider, public API, actual database or outbound access.
- Tests: false payments, fake seats, unsupported plan delivery mode, source duplicates, held source promotions and no PII leak.

Safe combined read-only run:

    cd /home/ubuntu/empire_worktrees/exchange_fulfilment_mrr_review_20261020
    PYTHONPATH=. /srv/empire_os/.venv/bin/python -B -m scripts.review_exchange_self_serve_fulfilment_mrr_20261020 --read-only --a2a-owner-queue /home/ubuntu/empire_worktrees/resilient_buyer_scout_business_release_996946a3/runtime/buyer_acquisition/a2a_source_verification_queue_latest.json

## Next precise owner deliverables

1. Existing checkout/Finance owner: authentic buyer identity, accepted terms, monthly USDT on BSC invoice and independent settlement, cancellation and renewal/expiry; never reuse legacy SQLite MRR billing.
2. Existing CRM/Exchange owner: tenant-safe entitlement and approved corridor access, reviewed buyer identity and verified capacity. No assumption that the current 1057 blocked seats are active subscribers.
3. Existing fulfillment owner: source/person consent and rights, territory match, canonical dedup and suppression, idempotent allocation, authenticated delivery and ACK, rejection/dispute/expiry and actual usage settlement.
4. Existing A2A/Buyer Scout owner: preserve current Brave metering and no persistent Search API results without rights; verify live purchase intent/capacity from independently reviewed first-party evidence; do not elevate website research into a personal lead.
5. Release owner: isolated integration/QA, real receipt checks and rollback before requesting separate founder approvals for production billing, plan activation and lead delivery.

Status: read-only foundation, tests and operator report. No payment, contract, tenant entitlement, revenue or delivery was verified or activated by this work.
