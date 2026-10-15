# Empire Data Exchange V15 — Durable Official Observation Custody

Date: 2026-10-15
Branch: `feature/empire-data-exchange-20261014`
State: **FEATURE IMPLEMENTED / PREPARED DATABASE MIGRATION / NOT DEPLOYED**
Data: UK Planning Data brownfield-land, three fixed NW source entities only.
Canonical database: **EmpireDB PostgreSQL, not Supabase.**

## The gap closed in code

V14 had temporal change and evidence-review logic, but no durable canonical
custody of repeated government observations. A source queried twice within
minutes usually shows no change; those reads cannot substantiate a new planning
event, development start or buyer demand.

V15 implements a *single* canonical store and a bounded one-shot source
capture path, using only existing first-party Planning Data validators.

```
Existing official read-only GET (3 fixed public entity IDs)
     -> existing normalise_official_brownfield_entities
     -> existing build_construction_preview / OBSERVE validation
     -> 50-record bound, narrow field allowlist, 128KiB JSON limit
     -> single canonical EmpireDB append-only transaction
           - dedicated least-privilege custodian role
           - advisory transaction lock and immutable sequence
           - duplicate capture time+hash => NOOP
           - changed content at same observation time => HOLD
           - previous chain hash + SHA256 source/chain commitments
           - PostgreSQL append-only triggers and forced RLS
     -> read last <=16 canonical source observations
     -> independently validate record shapes and chain links
     -> existing V14 temporal Signal Board -> AGI research
     -> internal OBSERVE only (NO commercial export)
```

New files:
- `empire_os/data_exchange_observation_custody.py` — canonical bounded
  snapshots, chain planner, deterministic row verification, window audit.
- `empire_os/data_exchange_custody_transport.py` — dedicated EmpireDB
  reader/writer, serialised append, safe no-op, integrity checks and V14 board.
- `scripts/operate_data_exchange_observation_custody.py` — one-shot
  OBSERVE preview and separately founder-gated canonical capture/read.
- `docs/commercial/prepared_sql/PREPARED_ONLY_data_exchange_observation_custody_20261015.sql`
  — **UNNUMBERED and OUTSIDE the executable migration directory**,
  immutable protected table, triggers, isolated roles.
- `tests/test_data_exchange_observation_custody.py` and
  `tests/test_data_exchange_custody_operator.py`.

## Migration collision — DO NOT rename or deploy ad hoc

Multiple active EmpireOS worktrees already use the number `052` for
**different schemas** (company intelligence history and editorial exchange).
A Data Exchange `052` would be unsafe. This SQL remains an explicitly
UNNUMBERED prepared-only proposal until the release owner reserves the next
canonical migration number and compares against the real production migration
ledger. No existing 052 proposal is changed or applied.

The migration requires an independently provisioned NOLOGIN, NOINHERIT,
no-BYPASSRLS `empire_data_exchange_custodian` role. The dedicated runtime
LOGIN may receive membership only through separately reviewed admin steps.
The migration creates no LOGIN/password/membership, no broad app grants,
no data backfill and no function granting mail or payment authority.
`empiredb_app` must NOT receive this role.

The database trigger serialises appends, requires genesis/sequence continuity,
rejects future/stale/backward observations, bans unreviewed source JSON fields
and prevents UPDATE/DELETE/TRUNCATE. The app independently rebuilds the
government-source projection, but **neither Python nor SQL cryptographically
authenticates the upstream government API**. Local SHA256 is tamper-evidence
only when independently preserved, NOT proof of published source changes.

## Operator contract — one-shot, no timers

With no flags:

```bash
cd /srv/empire_os
PYTHONPATH=. ./.venv/bin/python -m scripts.operate_data_exchange_observation_custody
```

This makes up to three bounded official GETs and prints only OBSERVE metadata.
No files, DB, emails or export.

When the prepared migration is numbered, independently reviewed, approved,
applied and the dedicated runtime identity is correctly provisioned, a
specific founder-approved capture can use:

```bash
# Variables supplied by the authorised first-party service's protected environment:
# EMPIRE_DATA_EXCHANGE_CUSTODIAN_DSN: dedicated custodian LOGIN (never generic app)
# EMPIRE_DATA_EXCHANGE_CUSTODY_RELEASE=FOUNDER_APPROVED_OBSERVATION_APPEND_ONLY
PYTHONPATH=. ./.venv/bin/python -m scripts.operate_data_exchange_observation_custody \
  --append --approved-custody-only
```

Canonical read-only internal board:
```bash
PYTHONPATH=. ./.venv/bin/python -m scripts.operate_data_exchange_observation_custody --board
```

No independent CLI flag or environment variable bypasses the dedicated
Postgres role membership, forced RLS or DB append-only policy. Any uncertain
DB commit response must be investigated via an authenticated canonical
head read, NOT retried blindly.

## Truth semantics and acceptance

- Government entry-date is not Empire observation date. Neither is a
  construction start, permit grant, tender win, project contact or intent.
- One captured source snapshot is NOT a change. Need >=2 nonidentical
  capture times and actual differences to produce a V14 review event.
- If two current snapshots have same fields, result is **zero changes**.
  This is a valid, informative result, not a failed observation.
- A returned source record may be old or removed from the *sample*
  without proving a site was created or demolished.
- Independent OGL field exceptions, attribution, privacy, provenance,
  retention and rights review remain mandatory for distribution.
- Repository code and prepared migration do not create a paid product,
  model training licence, prospective customer interest, or revenue.
- Read window limited to 16. With more than 16 rows, the window can be
  verified internally but NOT claimed as anchored all the way to genesis
  or to independent off-DB custody.
- Dedicated runtime identity still needs independently approved
  production credentials. Never print passwords, DSNs or OAuth tokens.
- Database retention/revocation, external anchor and disaster recovery
  approval are release blockers; append-only table deliberately has no
  automatic destructive retention process.
- No schedulers/agents/timers are installed. Founder may later approve
  bounded event-driven or scheduled observations inside the existing
  EmpireOS governance, but that is NOT activated by this feature.

## Production activation acceptance

1. Canonical release owner resolves competing 052 migrations and reserves
   a unique number for this exact SQL hash after independent SQL review.
2. Confirm append triggers, RLS and only the dedicated role with an
   independent isolated PostgreSQL integration test; static/unit tests
   do NOT substitute for actual DB execution.
3. Review create/provision of the dedicated sender-independent custodial
   account and protected environment, no generic database privileges.
4. Founder expressly approves this bounded migration and custody activation.
5. Perform a single actual three-record capture with verified live origin,
   confirm DB head/receipt and no duplicates on repeat.
6. On a later real day, capture again and check official record comparison,
   evidence retention, true source changes, and stable no-change semantics.
7. Separately complete source field rights, customer entitlement and
   licence review before any customer access.

Current status: **engineering candidate, feature branch only**.
No production table, no canonical capture, no external export, no billing.
