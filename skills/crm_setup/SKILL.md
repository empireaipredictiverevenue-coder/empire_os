---
name: crm_setup
description: Build + backfill the Empire OS CRM (crm_contacts, crm_deals) from live prospect/subscription data. Purges junk emails. Idempotent one-shot, runs INSIDE the container.
trigger:
  - "set up the CRM / backfill contacts"
  - "clean junk emails from CRM"
  - "build segmentation tables"
---

# SKILL: crm_setup

## What it does
Creates crm_contacts (segmentation: stage/status/tier/niche/metro/owner/tags) and
crm_deals (one per buyer seat: amount_usdc, stage, close_date). Backfills from
si_buyer_outreach + si_subscription, purges junk emails, infers stage from
outreach activity.

## When to run
- After schema changes to source tables.
- When junk emails detected in CRM.
- Periodically (e.g. nightly) to refresh segmentation from live data.
- INSIDE container: `python3 /root/empire_os/empire_os/agents/crm_setup.py`

## Steps
1. DROP IF EXISTS crm_contacts, crm_deals (clean re-run).
2. CREATE both tables.
3. Purge any pre-existing junk contacts (is_junk regex).
4. Backfill crm_contacts from si_buyer_outreach (skip junk: url-encoded,
   @sentry, @calendar.google, @example, invalid, owner-pending, @domain.com,
   no-reply, postmaster).
5. Backfill crm_deals from si_subscription (email via si_tenant.tenant_id;
   plan→tier; status→stage map).
6. Mark stage='contacted' where si_outbox has a sent founder_outreach email.
7. Print segment counts.

## Verification
- `SELECT COUNT(*) FROM crm_contacts` → ~697 real contacts (no junk).
- `SELECT COUNT(*) FROM crm_deals` → ~496 (matches subs).
- No @sentry/@calendar.google/url-encoded emails in crm_contacts.

## Pitfalls
- si_buyer_outreach has NO created_at — use last_touch_at.
- si_subscription has NO metro column — leave metro='' in deals.
- si_tenant keyed by tenant_id (NOT id) — join on tenant_id.
- si_subscription.tier is column `plan`, not `tier`.
- Always run in container; host DB is stale mirror.
- is_junk must catch url-encoded (%XX) AND domain placeholders.
