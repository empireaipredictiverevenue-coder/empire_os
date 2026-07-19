---
name: recovery_sequence
description: 3-touch USDC pay-link recovery on awaiting_payment buyer seats. Reconstructs each tenant's Solana Pay link from si_subscription, queues recovery emails via /v1/outbox/enqueue (Brevo), marks touch_N_sent idempotently. Runs daily via empire-recovery-sequence.timer inside the container. Highest-ROI revenue play (~$297k uncollected).
trigger:
  - "recover stuck deals / uncollected revenue"
  - "send recovery nudge to awaiting buyers"
  - scheduled: daily 09:00 via empire-recovery-sequence.timer (container)
---

# SKILL: recovery_sequence

## What it does
Finds crm_deals WHERE stage='awaiting_payment' and sends the next due touch
(T1 day0, T2 day3, T3 day7). Each touch emails the buyer their exact Solana
Pay link so they can fund the seat in USDC. Idempotent — each touch fires once.

## When to run
- Automatic: empire-recovery-sequence.timer (daily 09:00, container).
- Manual: `python3 /root/empire_os/empire_os/agents/recovery_sequence.py [--dry-run] [--max N]`
  (inside container).

## Steps
1. Load .env (SOLANA_VAULT_WALLET + DB path).
2. Query crm_deals awaiting_payment.
3. For each: compute age (days since created_at, naive parse). Find next
   unsent touch whose delay <= age.
4. get_pay_url(tenant_id): reconstruct `solana:<vault>?memo=<payment_ref>&amount=<usdc>`
   from si_subscription (payment_ref + price_cents/100).
5. queue_email → POST /v1/outbox/enqueue {to_email,subject,body,lane,lead_id,source}.
6. Mark touch_N_sent=1 in crm_deals.

## Verification
- dry-run: prints which deals → which touch, no sends.
- real: check `SELECT * FROM si_outbox WHERE source='recovery_sequence'`.
- crm_deals.touch_N_sent flips to 1.
- Brevo sends the email; buyer funds → si_subscription.status→active.

## Pitfalls
- Endpoint is `/v1/outbox/enqueue` (NOT /v1/outbox/queue — that path hangs).
  Payload keys: to_email, subject, body, lane, tier, lead_id, source.
- created_at is NAIVE (`2026-07-19 15:12:46`) — parse with strptime, not
  fromisoformat (tz mismatch → days_since returns 99).
- SOLANA_VAULT_WALLET must be loaded from .env (recovery script does this;
  standalone python without the loader gets empty vault → broken pay_url).
- Don't reconstruct pay_url via a hub call — derive from DB (no endpoint exists
  for /v1/buyers/paylink/{id}).
- Max 3 touches per deal. Never touches paid/active stages.
