# Buyer Recovery Prerequisite Router V1

## Goal
Make deferred buyer enrichment state actionable instead of repeatedly recycling the same unresolved work.

## Contract
Each queued or redeferred buyer records the next evidence prerequisite implied by its current blocker.
Site/network failures use progressively longer bounded cooldowns after repeated failed attempts.
Near-sendable contact evidence remains governed by the existing hot-lane logic.

Network cooldown:
- attempt 4+: 6 hours
- attempt 8+: 24 hours
- attempt 16+: 7 days
- attempt 32+: 30 days

A cooldown is not resolution and does not fabricate evidence.
The record remains durable and becomes eligible again after its bounded retry time.

## Safety
No new queue.
No database migration.
No evidence threshold changes.
No outbound, payment, commercial-terms, or revenue authority.
