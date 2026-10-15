# Empire Data Exchange V15 — Bounded One-Step Production Activation

Release base: production branch `agent/data-cloud-wave4`, tested integration
commit `3d7913b9`. This document accompanies the separately committed,
privileged production operator.

**Only user-approved scope:** first-party canonical OBSERVE custody of three
fixed public UK Planning Data brownfield records in existing EmpireDB.

## State of the release

The production repository already contains V15 code; the source preview
returned three official records and 68 focused tests passed from
`/srv/empire_os`. This is **passive production code only**, not proof of
database activation.

The one-shot operator:
`scripts/deploy_data_exchange_custody_v15.py`

It cannot be executed by the unprivileged Remote Commander service identity
and deliberately refuses to do so. An authorised system administrator must
run the ONE bounded root operation below in the established EmpireOS shell.

## Approved operator invocation

```bash
sudo -n bash -c '
set -e
cd /srv/empire_os
./.venv/bin/python -m scripts.deploy_data_exchange_custody_v15 \
  --apply --approved-data-exchange-v15-observe-only
'
```

This is not an outbound, billing, CRM or publishing release. The flag is an
operator acknowledgement of the founder's already-recorded approval. No
repetitive secondary founder approval is required.

## Guaranteed boundaries

Before mutation, the operator checks:

- Requires genuine root identity and runs only from `/srv/empire_os`.
- Validates exact reviewed SQL SHA256
  `d0288b5d69e29da2759e4ba64d67f7399fd5271eb5fefb959a4986a3a2996769`
  and the committed file object from `3d7913b9`.
- Obtains a release lock and confirms local PostgreSQL 18 canonical
  `empiredb`, current data directory and non-recovery state.
- Confirms the configured application DSN resolves to that same instance.
- Refuses any preexisting Data Exchange custody table, role or service.
- Refuses a missing canonical database configuration or insufficient free
  disk space for a FULL protected pre-release pg_dump and role backup.

For an eligible fresh release:

- Creates a dedicated `empire_data_exchange_custodian` NOLOGIN / NOINHERIT /
  NO-BYPASSRLS role and restricted `empire_data_exchange_custody_login`
  LOGIN. The login's strong random secret is never printed.
- Applies the **exact reviewed schema in the SAME transaction** as role
  creation (verified with a disposable PostgreSQL 18 gauntlet).
- Stores local runtime DSN as root-owned 0600
  `/etc/empire/data-exchange-custody.env`, separately from Empire's
  existing app/outbound/payment secrets.
- Installs static on-demand `empire-data-exchange-custody-capture.service`
  as the existing unprivileged Ubuntu runtime user.
- Starts the service exactly ONCE to fetch the three fixed public entity
  IDs through Empire's existing allowlisted HTTPS GET normalizer.
- Verifies precisely ONE genesis record with all three public source IDs
  persisted and a locally recomputed SHA256 chain.
- Saves a root-only release receipt next to the pre-release backup.

Never schedules a timer, installs a public API, grants generic DB app access,
contacts buyers, sends email, moves funds, claims verified construction
starts or clears licensing.

## On failure

The operator prints JSON with `status=HOLD` and a redacted reason code.
Some failures after the schema transaction may leave the table and roles
safely installed WITHOUT a successful observation capture; these MUST be
reconciled via DB inspection, not retried automatically. The operator
fails if it detects existing table/role/service state.

Success must explicitly read:
`"status":"PRODUCTION_OBSERVE_CUSTODY_ACTIVE"`,
`"canonical_rows":1`, `"backup_verified":true`,
`"customer_delivery_enabled":false`, `"timer_installed":false`.

One row = ONE snapshot, **not a detected construction change**. A subsequent
genuine later observation is required for the V14 signal comparison. Source
field-level OGL exceptions, independent source provenance and commercial
customer distribution remain separately held, irrespective of this release.

## Verification evidence obtained before deployment

On isolated PostgreSQL 18, the actual role-creation/schema SQL transaction
and running Python transport successfully executed two appends, an exact
duplicate no-op, full chain readback, and V14 signal-board reconstruction.
Forged URLs, private-contact fields, incomplete rows and UPDATE/DELETE/
TRUNCATE were rejected by the database.

**Do not report schema activation or durable custody until the root operator
runs and returns the readback receipt.**
