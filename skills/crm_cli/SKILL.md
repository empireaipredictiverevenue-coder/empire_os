---
name: crm_cli
description: CLI for the Empire OS CRM. Pipeline summary, stuck-deal finder, segmentation by niche/tier, single-contact view, and contact updates. Runs INSIDE the container.
trigger:
  - "crm summary / pipeline view"
  - "who's stuck in the funnel"
  - "show roofing buyers / segment by tier"
  - "update contact stage/owner"
---

# SKILL: crm_cli

## Usage (inside container)
  python3 /root/empire_os/empire_os/agents/crm_cli.py summary
  python3 /root/empire_os/empire_os/agents/crm_cli.py stuck --days 7
  python3 /root/empire_os/empire_os/agents/crm_cli.py segment --niche ROOFING
  python3 /root/empire_os/empire_os/agents/crm_cli.py segment --tier SILVER
  python3 /root/empire_os/empire_os/agents/crm_cli.py contact EMAIL
  python3 /root/empire_os/empire_os/agents/crm_cli.py update EMAIL --stage applied --owner agent1 --note "left voicemail"

## Commands
- summary: contacts by stage + tier; deals by stage with total USD; top niches.
- stuck: contacts in prospect/contacted with no update >N days; deals awaiting_payment >N days (uncollected revenue).
- segment: filter contacts by --niche / --tier.
- contact: full crm_contacts row + linked crm_deals.
- update: sets stage/status/owner/tier; appends note with date prefix.

## Verification
- `summary` prints 3 tables, no traceback.
- `stuck --days 1` shows uncollected deals (awaiting_payment) — these are the
  revenue-at-risk (496 deals = $297k at last backfill).

## Pitfalls
- `show()` builds column widths by scanning rows — fixed UnboundLocalError
  (don't use list-comprehension scoping over the same loop var `r`).
- Reads container DB only; run via incus exec if from host.
- update appends to notes (||'\n'||) — never clobbers prior notes.
- tier on contacts is often 'unknown' (prospect table lacks tier); deals carry
  it via `plan`. Don't expect contacts.tier to be populated.
