# Empire Data Exchange V18 — Canonical Field Rights Evidence Docket

Date: 2026-10-15. Mode: **OBSERVE / review preparation only**.
No new database, runtime, timer, source adapter, revenue estimate, outreach,
customer export, legal sign-off, or third-party model.

## Why this is ready before tomorrow's capture

V15 has one canonical source observation. Existing source-rights preflight
required two snapshots because it reuses historical dossier comparison.
Legal source-field review can **begin from a single genuine observation**
without claiming source change or opening the 24-hour custody write gate.

V18 builds a reproducible rights evidence docket using the existing V15
canonical hash verifier and V14 rights lineage vocabulary. It can be
requested through the EXISTING protected V16 inspector:

```bash
sudo -n bash -c '
cd /srv/empire_os
./.venv/bin/python -m scripts.inspect_data_exchange_v16_live \
  --read-only --rights-docket
'
```

Optional `--scientific-review` and `--recheck-official` can be combined
for one **read-only** inspection of the same canonical history.

## Grounded public licensing evidence

- Official dataset: https://www.planning.data.gov.uk/dataset/brownfield-land
- Open Government Licence v3:
  https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/
- Dataset page states: Open Government Licence v3.0.
- Dataset attribution: © Crown copyright and database right 2026.
- The OGL allows commercial reuse of the INFORMATION COVERED, subject
  to conditions including attribution, personal-data exclusions,
  third-party IP rights, and non-endorsement.
- A dataset-wide licence is NOT an independently reviewed receipt that
  every individual field, derived signal and external delivery format
  is cleared. The docket therefore leaves every such sign-off OPEN.

## Pinned field-by-field source mapping

| Product field | Source or calculation | Current status |
|---|---|---|
| source_record_id | Official entity ID | Field rights not independently reviewed |
| source_url | Normalized Planning Data entity permalink | Field rights not independently reviewed |
| source_entry_date | `entry-date` | Field rights not independently reviewed |
| planning_permission_status | `planning-permission-status` | Field rights not independently reviewed |
| site_area_hectares | `hectares` | Field rights not independently reviewed |
| source_observed_at | Empire fetch timestamp | Not government publication time |
| observed_history_change | Empire derived comparison | Needs two genuine observations |

The custody source projection does not ingest address, contact,
ownership-person, free-text description, email or telephone fields.

## Before any customer-facing release

Independently review actual field-specific rights, publisher attribution,
all applicable exceptions, retention/correction, source revision
provenance, data minimisation, commercial representations and explicit
founder release approval. This is an evidence task register, not a
licensing decision or legal advice.

**Current state:** one true V15 observation, one protected EmpireDB,
three fixed pilot IDs; V18 dossier prepared, no customer distribution,
no paid buyer validation, no revenue.
