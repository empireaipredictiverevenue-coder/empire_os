# Exchange Seats + A2A — minimal production-base integration

**20 October 2026 — branch `feature/exchange-seat-a2a-minimal-release-20261020`**

## Why this branch exists

The original Exchange development worktree branch was approximately 765 commits ahead of `origin/agent/data-cloud-wave4` at integration time and included thousands of unrelated files. That is **not** a suitable direct production merge.

This isolated branch starts from the existing `origin/agent/data-cloud-wave4` reference and cherry-picks only the five audited Exchange commits:

- `5d8ecfa10`: self-serve membership, fulfilment and A2A research-only operator review
- `388c2e83d`: native BSC seat/lead delivery receipt consistency reviews
- `b45b719c4`: calendar-anchored renewals and private finance owner review
- `70c0343b2`: bounded owner-side native Finance read adapter and sealed SQL table proposal
- `ea0d1dc74`: composite tenant/buyer invoice FK and read-only catalog preflight

It brings over `empire_os/lead_exchange_live_inventory.py` as a **single** necessary production-base-missing dependency, with a small standalone synthetic snapshot fixture and tests. It does not import unrelated founder API endpoints or reproduce older lead-intelligence branches.

## Integration proofs

Focused clean-base tests: 130 passed before the additional isolated lead-inventory dependency tests. Read-only operator ran from this clean branch and found:

- current canonical Exchange selection: 175 review rows
- verified active capacity: 0
- A2A first-party company research-owner tasks: 7
- no lead delivery admission; recognized MRR: 0.

A2A company research is NOT consumer-lead inventory and does not permit contact or resale. Brave results are not persisted. The upstream scheduled canonical buyer scout's `UnsetEnvironment=BRAVE_API_KEY` is preserved, not modified.

## IMPORTANT release gate

**Source review, not live financial deployment.**

- No production database migration was applied.
- `docs/commercial/sql/EXCHANGE_NATIVE_SEAT_TABLES_REVIEW_ONLY_NOT_APPROVED.sql` is a prepared-only draft outside the migrations directory.
- Remote privilege policy denies actual DBA preflight via sudo; role/RLS and finance payment proof remain unauthenticated.
- The existing buyer-interest form remains non-binding. No paid seat is being activated.
- No physical BSC fund movement, customer subscription charge, customer data delivery, true MRR or usage revenue was created.
- No change to the public checkout, live `/srv/empire_os`, cloud infrastructure, accounts, systemd units or mailbox.

## Next owner-controlled actions

1. Review this narrow PR against the current mainline version and reconcile any intervening checkout/canonical schema changes; run the full affected application+API test suite.
2. Existing authorised DBA alone: execute the approved **read-only** catalog preflight, not the schema draft, and verify exact role inheritance, RLS and tenant identity separately.
3. Define and independently authorize a native Exchange monthly entitlement and invoice-event writer with transaction-wide idempotency, approved contract and verified BSC per-month settlement; apply no rights from input booleans.
4. Govern entitlement expiry/cancellation/refund and lead delivery separately. No monthly USDT auto-debit assumption. Do not credit buyer-seat counts or list price as recurring revenue.
5. A2A/Buyer Scout continues first-party research under the existing safe timers; commercial promotion requires independent buyer demand and canonical identity/capacity checks.

No production merge/restart/finance switch under this release-integration exercise without a separately approved plan.
