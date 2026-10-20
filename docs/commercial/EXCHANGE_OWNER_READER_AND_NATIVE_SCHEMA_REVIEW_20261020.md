# Empire AI Exchange — native owner Finance reader + sealed schema proposal

20 October 2026. Isolated branch feature/exchange-fulfilment-mrr-review-20261020.

## Actual addition

1. `empire_os/exchange_native_seat_owner_reader_v1.py` is a narrow, SELECT-only integration adapter over an **injected pre-authorised owner source**. It performs, at most, four bounded exact-row lookups: buyer by UUID; fulfilment order by UUID; BSC payment request by exact order; BSC evidence by exact request. Every read uses an explicit, minimal column list and LIMIT 2 to detect duplicate rows.
2. It rejects wrong canonical backend, absent/invalid IDs, mismatched tenant and buyer identity, non-activated buyer, missing/duplicate request/evidence, invalid payment joins and source/driver failures. It never emits names, emails, wallets or transaction hashes.
3. It passes the four internal rows to the existing BSC USD-priced seat verification contract, with a separate finance quote. A matching result means only **cross-record shape consistency, not authenticated paid MRR**. The module has no live database connection of its own; a caller cannot acquire access by setting read_intent_approved. Independent role, tenant RLS and payment authority must come from the owner transport. These are NOT proved here.
4. `docs/commercial/sql/EXCHANGE_NATIVE_SEAT_TABLES_REVIEW_ONLY_NOT_APPROVED.sql` is a future schema **design artifact outside migrations/**. It proposes native Exchange memberships separate from historical strike-pack/Stripe subscriptions, and per-month invoice/payment receipt journal. Uniqueness includes membership+period, invoice order, BSC payment request and evidence. Defaults remain proposed/pending. Both proposed tables have RLS ENABLE+FORCE, zero policies and zero app grants, with a postcheck that rejects unexpected ACL/policy/RLS state.
5. No SQL in this change was applied or experimentally executed on production. A static source test validates the draft boundaries; this is not a live PostgreSQL schema proof. The draft needs fresh catalog reconciliation (including any later migrations outside this branch), chosen migration ID, DBA review, backup, role preflight, RLS and real tenant controls before any deployment.

## Why this release is still held

- A generic configured EmpireDB data gateway is not proof of the *dedicated financial owner role* or correct tenant scoping. The existing `read_direct_bsc_buyer_status` capability was designed for a separate limited buyer-status use and is NOT a monthly subscription entitlement grant.
- Stripe-era `buyer_subscriptions` still refers to `strike_packs`. It must not be reused for Exchange subscription recognition.
- A payment request's existence or 12-confirmation witness alone is not proof of a contractually accepted, unique, finance-reconciled recurring customer payment. The USD price requires accepted, independently reviewed USDT quotation/FX evidence.
- A confirmed payment does not by itself prove currently permitted corridor entitlements, eligible inventory, consumer consent, destination acknowledgements, accepted lead usage or recognized revenue.
- No real subscriber, payment, lead delivery, USDT fund movement, customer contact, or revenue was observed/created through this adapter.

## Existing owner next step

Finance/DBA owner must add a narrowly scoped read-only identity and authentically retrieve native rows via a separately approved service, verify real financial settlement and FX records under issuer/RLS evidence, and deliver a minimum disclosure review to existing entitlement owner. CRM/Exchange owner then designs single-writer atomic period activation and expiry with unique idempotent reversal/renewal events. This branch does not grant or deploy those authorities.

## Testing

Run focused Exchange test suite in:
`/home/ubuntu/empire_worktrees/exchange_fulfilment_mrr_review_20261020`

The new synthetic owner-reader tests validate exact columns/filters, four bounded reads, wrong tenant and buyer, duplicates, injected backend error redaction, noncommercial orders and no contact or wallet details in output.
The proposed SQL tests are static checks, not evidence of PostgreSQL syntax or live-role correctness.

A2A and Buyer Scout continue on existing schedules. The global scheduled Buyer Scout holds `UnsetEnvironment=BRAVE_API_KEY` to protect credits and rights; nothing in this branch changes it.
