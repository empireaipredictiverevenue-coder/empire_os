# CRM Agent — Skill Spec

Used by `crm_cli.py` (inside empire-hub). Turns raw revenue tables into a
segmented, manageable pipeline. Operational contract.

## Commands
- `summary` — counts by stage / tier / niche + deal pipeline ($ USDC)
- `stuck [days]` — contacts not updated in N days (default 7) AND not
  active/churned. The daily worklist.
- `segment --tier X --niche Y --status Z` — filtered contact list
- `backfill` — populate crm_contacts + crm_deals from si_buyer_outreach +
  si_subscription (idempotent: INSERT OR IGNORE)
- `note <email> <txt>` / `tag <email> <tag>` / `stage <email> <s>` — annotate

## Schema (created on first run)
- crm_contacts(id, email UNIQUE, name, company, niche, metro, tier, stage,
  status, owner, tags, notes, created_at, updated_at)
- crm_deals(id, contact_email, tenant_id, subscription_id, amount_usdc, stage,
  close_date, created_at)

## Stage mapping (backfill)
si_subscription.status → crm_contacts.stage:
  awaiting_payment → applied
  active           → active
  cancelled        → churned
  (else)           → applied

## Verification
```bash
incus exec empire-hub -- python3 -m empire_os.agents.crm_cli backfill
incus exec empire-hub -- python3 -m empire_os.agents.crm_cli summary
# expect: applied ~495, $296k pipeline; prospect ~226
incus exec empire-hub -- python3 -m empire_os.agents.crm_cli stuck 7
# expect: list (empty right after backfill is correct)
```

## Pitfalls (do NOT repeat)
- **si_subscription has NO `metro` / `tier` columns.** Real cols: plan, niche,
  status, price_cents, per_lead_cents, payment_ref. Use `plan` for tier.
- **si_tenant keyed by `tenant_id`, not `id`.** Look up email via
  `SELECT email FROM si_tenant WHERE tenant_id=?`.
- **Seats without a real email** → fallback contact email `seat:<sub_id>` so
  the deal still links. Don't crash on NULL email.
- **Backfill must be idempotent** — INSERT OR IGNORE + UPDATE, never DELETE,
  so re-running doesn't dupe or wipe operator notes.
- **Source tables are read-only from CRM** — never UPDATE si_*. Operator edits
  go to crm_contacts only.
