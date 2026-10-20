# Empire AI Exchange — native seat settlement and per-lead delivery receipt review

20 October 2026. Isolated worktree: exchange_fulfilment_mrr_review_20261020.
Branch: feature/exchange-fulfilment-mrr-review-20261020.

## Exact existing EmpireDB contracts inspected
- Native migration 015: public.bsc_payment_requests, public.bsc_payment_evidence. Payment request joins buyer_id and fulfilment_order_id; evidence uniquely joins request_id and fulfilment_order_id. Direct BSC chain id 56, verified USDT token 0x55d398326f99059ff775485246999027b3197955, 12 confirmations minimum, payment request approval, terms SHA256, unique transaction hash and recorded settlement.
- Native migration 002: public.fulfilment_orders with buyer_id, state, price_cents, commercial_payload. A monthly Exchange membership must be explicitly tagged in its accepted terms/payload; a one-time product order cannot activate the seat.
- Legacy migration 000: buyer_subscriptions is joined to old strike_packs and has Stripe-era customer/subscription identifiers; active legacy rows are not native Exchange seat entitlements or collected membership revenue.
- Current Phase 4 Exchange memberships: Starter $99/mo, Growth $249/mo, Pro $499/mo and Enterprise $999/mo USD. Source is founder-approved non-binding catalogue; the public /buy flow records buyer-stated interest only.

## Added independently testable source/evidence contracts

1. empire_os/exchange_seat_payment_receipt_review_v1.py
   - Validates one order, payment request, independently recorded BSC payment evidence and operator quote, if supplied by a separately authorised source.
   - Requires matching buyer, order, request and terms fingerprints; specific plan, USD monthly price, quantity one, billing period, operator-approved request, direct BSC USDT finality, payer, treasury, payment amount/token units and finance-approved quote/FX evidence.
   - BSC approval or a transfer hash is not a subscription. Never assumes recurring token auto-debit or that USD == USDT without recorded finance quote.
   - Even structurally consistent caller-supplied data remains NOT AUTHENTICATED: zero seat activation, verified subscriptions, recognised MRR, delivery or payment writes. Full native RLS, independent chain verification, contract authenticity, invoice and uniqueness/replay checks require the existing authorised finance/checkout owner.
   - Never emits buyer IDs, wallets, payment transaction IDs or terms text.

2. empire_os/exchange_lead_delivery_receipt_review_v1.py
   - Validates one candidate entitlement, permitted consumer/business inventory, idempotent allocation and authenticated buyer delivery/acceptance acknowledgement.
   - Requires exact buyer/entitlement/inventory/route joins, current seat period, product corridor and channel limits, capacity, independent source/consent/transfer rights and opt-out checks, canonical duplicate and suppression clearance, booking/exclusivity rules, ACK, accepted event and agreed price/dispute conditions.
   - Research observations, old permit company names, public professional emails, unconsented consumer contacts and revoked records cannot enter a delivery candidate.
   - Source rights and consumer consent are NEVER optional in a lower-cost buyer-qualified lead package.
   - Even a structurally consistent reviewer-supplied ACK never produces a real delivery/accepted billable event, customer invoice, subscription MRR or recognized usage revenue.
   - No personal information emitted and no outbound or CRM/DB writes.

## Revenue and fulfilment separation

Membership renewal invoice/settlement → authenticated and tenant-bound seat entitlement and approved corridor access → conditional inventory eligibility → idempotent allocation with capacity decrement → authenticated delivery + ACK → acceptance/rejection/dispute → usage settlement and reconciled revenue.

SaaS membership MRR must come from *authentic period-bound subscription and finance ledgers*, not catalogue list price, buyer seat counts, "active" legacy rows or BSC request proposals.
Lead-event usage revenue remains a separate reconciled event, not extra MRR.
No lead volume guaranteed by seat membership unless explicitly contracted and demonstrably feasible.

## Observed actual production blockers

20 October read-only canonical Exchange snapshot: 175 research selection rows (84 evidence-held, 91 without accepting buyer capacity), 1,057 buyer-seat records all evidence-blocked, 0 verified active buyer capacity, 0 allocation candidates, 0 allocations. A2A owner queue: 7 company-website review tasks, 2 source-policy holds and 7 historical permit-name hypotheses, NOT paying buyers or saleable leads.

## Work still assigned to native owners

- Checkout/finance owner: restricted read-only *source* adapter for native fulfilment_orders, bsc_payment_requests and bsc_payment_evidence with buyer/tenant RLS, independent chain-finality and FX, contract and period checks. Never pass raw confidential payment data through public website or GitHub.
- Tenant/Exchange owner: separate native Exchange seat subscription and corridor-entitlement journal, idempotent activation/expiry/renewal and Stripe-free USDT-on-BSC monthly settlement. Review migrations/ownership before a DB schema proposal. DO NOT migrate or activate automatically.
- Lead fulfillment owner: canonical consent/provenance ledger, reservation uniqueness, capacity controls, permitted destination authenticated delivery, ACK and dispute/rejection windows. Actual dispatch requires separate authority.
- A2A research owner: preserve public research as research; buyer qualification, source-rights verification and canonical company identity/dedupe before proposing buyer seats. Continue Brave API transient-only with existing schedule hold.
- Commercial owner: customer-facing terms, zero-guarantee membership disclosure, plan/usage price separation, invoice and cancellation policy.

## Validation

PYTHONPATH=. /srv/empire_os/.venv/bin/python -B -m pytest -q \
  tests/test_exchange_seat_payment_receipt_review_v1_20261020.py \
  tests/test_exchange_lead_delivery_receipt_review_v1_20261020.py \
  tests/test_exchange_self_serve_fulfilment_review_v1_20261020.py \
  tests/test_exchange_a2a_research_bridge_v1_20261020.py \
  tests/test_lead_exchange_live_inventory_20261019.py \
  tests/test_exchange_self_serve.py \
  tests/test_phase4_exchange_mrr_products.py \
  tests/test_commercial_exchange_contract.py

Expected: 92 focused tests passed on the isolated branch, one upstream anyio deprecation warning.

**NOT DONE:** independently authenticated real row retrieval, production schema/tenant authority, actual subscription payment, real lead contact, buyer acceptance, deployment or recognized revenue. These two modules are *offline join-contract reviews* and deliberately cannot turn synthetic or self-asserted data into fulfilment authority.
