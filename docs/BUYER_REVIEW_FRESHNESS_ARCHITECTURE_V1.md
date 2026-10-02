# Buyer Review Freshness Architecture V1

## Revenue problem

Re-verified buyers could be trapped behind old buyer-review rows because review
proposal idempotency used a permanent v1 key. GTM also processed pending reviews
oldest-first and treated all historical approved contacts as duplicate blockers.

The combined effect was a stale-review starvation loop:
fresh enrichment -> old idempotent review returned -> no fresh review event ->
GTM spends its bounded review slots on stale rows -> no new adaptive intent.

## Canonical flow

buyer enrichment
-> person-bound verified contact
-> check for same prospect/email review within last 7 days
-> reuse fresh review OR propose daily-bounded re-verification review
-> GTM reads pending reviews newest-first, last 7 days only
-> only fresh approved reviews block duplicate auto-review
-> adaptive copy selection
-> existing governed outbound approval/send

## Freshness contract

- A pending or approved review is fresh for 7 days from proposed_at or reviewed_at.
- Existing fresh review is reused and reported as existing_fresh.
- No second canonical review is proposed for the same fresh prospect/email.
- If only stale reviews exist, a new proposal receives a daily-bounded
  reverified YYYY-MM-DD v2 idempotency key.
- Re-running within the same UTC day remains idempotent.
- Historical review rows are preserved; no destructive cleanup is required.

## GTM scheduling

- Pending review query is proposed_at descending.
- Pending review auto-review eligibility is bounded to the last 7 days.
- Approved duplicate-contact blocking is bounded to reviews reviewed within the
  last 7 days.
- Old reviews remain auditable but cannot starve the bounded GTM work window.

## Authority

This changes review freshness and queue ordering only. It does not weaken
personhood, MX/contact verification, suppression, daily send caps, outbound
standing authority, commercial terms, payment authority, or revenue recognition.

## Failure semantics

If no verified person-bound contact exists, no review is created.
If the review API cannot prove a fresh existing row or accept a new proposal,
the buyer remains in the durable enrichment workflow.
