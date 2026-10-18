# Empire AI — Historical Google Workspace Sends / Canonical Evidence Release

**18 October 2026 | Private proof custody completed; EmpireDB migration STAGED, NOT APPLIED**

## Why this release exists

The private, authenticated Workspace Gmail monitor confirms exactly six genuine
UK solar outreach messages were sent. Each of their six threads has only its
original sent message at the latest authenticated provider scan. The Founder
Console's canonical, restricted EmpireDB observer checked both exact Gmail
thread metadata and exact original recipient addresses across
`public.outbound_intents`: **0 visible matching intents for all six**. These
two independent read-only checks do not imply a Gmail send failed; they show
a historical Gmail-to-canonical-ledger admission gap. RLS limits the claim
to what the existing restricted reader can see.

It would be incorrect to INSERT new `public.outbound_intents` with status
`sent` or invent historical approvals, prospects, buyers, tenant mappings,
or recognised payments. These externally sent messages never passed
EmpireOS's canonical original-intent approval workflow.

## Completed now — private external-SENT proof (no database mutation)

- Existing six-thread metadata snapshot is 0600 and refreshed by the
  existing five-minute `empire-buyer-acquisition-team.timer`.
- The new bounded `empire_os/workspace_solar_historical_manifest.py`
  validates all six exact sent anchors and source freshness, and builds
  deterministic `sha256` receipt digests over original provider message,
  Gmail thread, actual provider timestamp, account scope and original
  recipient fingerprint. No subject, body, Gmail OAuth token, raw RFC ID,
  unredacted recipient address or customer contact is retained.
- `scripts/prepare_workspace_solar_historical_evidence_20261018.py`
  writes a **single immutable-in-practice, non-overwriting** private evidence
  file only when explicitly invoked with `--write-private-evidence-only`.
  It refuses altered, incomplete or stale snapshots, symlinks, file mode
  drift and conflicting duplicate receipts.
- Real proof custody was independently created and replay-verified at
  `/srv/empire_os/runtime/buyer_network_intelligence/workspace_solar_historical_evidence_20261018.json`.
  File mode is **0600**, owner **ubuntu**; six actual receipts captured.
  Running the same command again returned
  `EXISTING_IDENTICAL_EVIDENCE_CUSTODY`, never an overwrite.
- No messages were sent, no CRM/database/customer/payment row was created,
  and no external account or extra timer was provisioned.

## Staged only — EmpireDB 052 historical-receipt extension

`migrations/empiredb/052_workspace_historical_send_receipts_observe_only.sql`
is **prepared but unapplied**. It creates
`public.workspace_historical_sent_receipts` solely for externally observed
historical sent evidence, separate from `public.outbound_intents`. It
enforces unique provider-message and Gmail-thread keys, original sender
mailbox class, recipient SHA-256, source timestamps, evidence digest and
`linkage_state='UNBOUND_EXTERNAL_SENT_OBSERVED'`. Database checks forbid
retrospective approvals, CRM binding or revenue truth. An immutable trigger
rejects UPDATE and DELETE; forced RLS grants SELECT only to the existing
`empire_closer_observer` role. No new database login, role, RPC or sender
permission is added.

`scripts/import_workspace_historical_sent_receipts_20261018.py` is a
privileged, idempotent one-shot **evidence-only** importer. It verifies the
exact private manifest against a fresh authenticated source before opening
the DB. In the explicitly authorised branch it starts as root to read the
existing 0600 file, permanently drops to OS user `postgres` to use peer
authentication, and opens a time-bounded serializable transaction on
`empiredb`. It verifies the new table's forced RLS and immutable trigger,
compares all existing matching evidence, inserts only genuinely missing
receipts, verifies exact six-row readback and commits. Any contradiction
fails the entire transaction. It never writes `outbound_intents`,
`outbound_replies`, CRM, tenant, suppression, payments or email.

## Operator commands — staged, no DB activation automatically approved

Read-only preflight is safe to rerun:

```bash
cd /srv/empire_os
./.venv/bin/python -B -m scripts.prepare_workspace_solar_historical_evidence_20261018 --preview
./.venv/bin/python -B -m scripts.import_workspace_historical_sent_receipts_20261018 --preflight
```

**Do not execute the following until the founder explicitly approves
DB migration 052 and the historical-evidence insert**, and the privileged
DBA confirms current schema/role compatibility and recovery status:

```bash
cd /srv/empire_os
sudo -u postgres psql -X -v ON_ERROR_STOP=1 -d empiredb \
  -f migrations/empiredb/052_workspace_historical_send_receipts_observe_only.sql
sudo ./.venv/bin/python -B -m scripts.import_workspace_historical_sent_receipts_20261018 \
  --apply-founder-approved-historical-receipts-only
```

Those actions mutate only the dedicated historical proof table. They do
not create or backfill canonical sent intents. Do not use these commands
under a generic agent deploy, CI pipeline, cron or server startup. Keep the
existing backup/PITR recovery evidence verified before privileged DDL.

## Verified against isolated PostgreSQL 18 (not production)

A reproducible integration test is now included at
`scripts/verify_workspace_historical_scratch_postgres_20261018.py`.
It creates a temporary Unix-socket-only PostgreSQL 18 cluster under
`/tmp`, creates a dummy database named `empiredb` inside that cluster,
and uses strictly local socket connection strings. It does **not** use the
production PostgreSQL listener, credentials, cluster, customer database
or production service configuration.

The real migration 052 ran successfully in the isolated database. A
duplicate application was rejected. The real six-receipt importer then
inserted six rows and replayed with zero duplicates. The existing restricted
observer role could SELECT all six but could not DELETE them; UPDATE,
DELETE and retrospective approval changes were rejected by the immutable
trigger. The test automatically stopped and deleted its isolated database.

A separate private Founder API readout now exists at
`/v1/founder-mailbox/workspace-solar-historical-evidence-status`,
implemented by `empire_os/workspace_solar_historical_status.py`.
It compares the currently verified private six-receipt custody against
the dedicated EmpireDB historical-receipt table using the **existing**
`empire_closer_observer` login in a read-only transaction.

The isolated PostgreSQL test verified the readout's actual state transition:
`SCHEMA_ACTIVE_NO_HISTORICAL_RECEIPTS` before import and
`SIX_HISTORICAL_RECEIPTS_VERIFIED_IN_EMPIREDB` after the six exact inserts.
For an unapplied production migration, the correct status is
`PRIVATE_CUSTODY_ONLY_DATABASE_SCHEMA_HELD`, showing zero **database**
receipts but six genuine provider receipts in private custody. A
partial/contradictory source cannot report completed admission, and
no result implies canonical sent-intent creation, tenant binding, approved
outbound, CRM opportunity or revenue.

The readout is mounted only on the existing loopback Founder read API
(port 8766); the public site and authenticated CRM tenant API are not
changed. The underlying original Workspace tracking and five-minute timer
remain unchanged.

Read-only private status check once deployed:

```bash
curl -fsS http://127.0.0.1:8766/v1/founder-mailbox/workspace-solar-historical-evidence-status
```

The readout is **not** a DB activation instruction; the migration/import
remain separately held pending explicit founder authorisation.

## Commercial completion gates still open

1. Independently verify the newly admitted historical evidence in the
   existing founder read workflow, without displaying personal addresses.
2. Only after a genuine inbound response, verify original provider chain,
   sender, suppression/opt-out state, tenant and contact authority.
3. Obtain a separately reviewed canonical-admission design if a true CRM
   sales conversation needs to be created from an external historical
   send. The new evidence table alone does not authorise that promotion.
4. Continue sales acquisition and commercial partner conversations in the
   existing outbound programme; six sent emails by themselves are not
   verified demand or revenue.

**Status:** six authentic Gmail original-sent receipts in private custody;
migration 052 and DB importer built/staged; DB activation held for
explicit founder authorisation; zero new commercial revenue.
