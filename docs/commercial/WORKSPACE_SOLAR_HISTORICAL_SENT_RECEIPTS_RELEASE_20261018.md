# Empire AI — Historical Google Workspace Sends / Canonical Evidence Release

**18 October 2026 | Migration 052 VERIFIED LIVE; six historical receipt inserts remain separately held**

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

## EmpireDB 052 historical-receipt extension — verified production schema

`migrations/empiredb/052_workspace_historical_send_receipts_observe_only.sql`
was applied to production EmpireDB on 18 October 2026. It creates
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

## Founder-approved migration 052 — archived operator procedure (now completed)

On **18 October 2026**, the founder explicitly approved **migration 052**,
which creates only the separate historical sent-evidence table. This is
**schema-only approval**; it does not approve the separate historical
six-receipt INSERT, creation of canonical outbound intents, CRM mutation,
outbound sends or financial activity.

The one-time operator release script is
`scripts/activate_workspace_historical_receipts_migration_052_20261018.sh`.
It pins the unchanged migration source digest, checks private custody and
read-only API evidence, and on its explicit privileged branch verifies the
actual live EmpireDB name, archive health, PostgreSQL role and schema
authority. It uses postgres peer authentication and a single transaction
to apply the frozen migration 052 SQL, then checks forced RLS, the
append-only trigger, SELECT-only closer grants, **zero** database receipt
rows and the existing private Founder reader's honest post-migration state.
It does not restart any application service or import any receipts.

The read-only nonprivileged preflight has passed on EmpireOS. An attempt
to run privileged SQL directly through the connected remote command
interface was denied before execution; this permission boundary was
respected. At that earlier checkpoint, migration 052 had not yet been applied.
**The founder subsequently completed this operator action successfully.**
The command below is preserved as historical release evidence, NOT a
command to rerun on the activated database:

```bash
cd /srv/empire_os
bash scripts/activate_workspace_historical_receipts_migration_052_20261018.sh --preflight
sudo bash scripts/activate_workspace_historical_receipts_migration_052_20261018.sh --apply-founder-approved-migration-052
```

The exact success marker is `EMPIREDB_MIGRATION_052_SCHEMA_VERIFIED`,
together with `historical_table=active rows=0`. If any role, archiver,
schema or security check fails, the operator must report the HOLD marker;
do not work around it or import receipts. The SQL migration is already
transactional, and the preflight refuses to run a second create.
After activation, the live private status should read
`SCHEMA_ACTIVE_NO_HISTORICAL_RECEIPTS`. No automatic DB INSERT occurs.

The original six receipts remain preserved in private custody.
`scripts/import_workspace_historical_sent_receipts_20261018.py`
is a separately gated import, **not included in this approval**. Its
privilege-drop flow was fixed to validate the protected provider snapshot
before permanently dropping from root to OS `postgres`, carrying only
the prevalidated in-memory evidence into SQL. Conflict and replay checks
were tested on a separate PostgreSQL 18 scratch instance. A future import
must never be launched by cron, CI, backend startup or a generic deploy.


## Concurrent Founder API release — historical recovery procedure (now completed)

After the founder's schema-only approval, the existing private Founder API
was found running another agent's **newer frozen release**:
`/opt/empire-ai/founder-read-releases/bridge-sources-history-75912015`.
Its Gmail and canonical-intent endpoints remained healthy, but it had
not included the preexisting
`/v1/founder-mailbox/workspace-solar-historical-evidence-status`
read-only route. That endpoint had been live earlier, but now returned
HTTP 404. The approved migration operator refused this unverifiable
precondition, correctly making **no production schema change**.

To preserve all that agent's other work, a fresh isolated copy of the
currently running release was prepared at
`/home/ubuntu/empire_worktrees/empire_founder_api_hist052_bridge_additive_20261018`.
It differs only by the safe `empire_os/founder_mailbox_api.py`
read-only route and the existing
`empire_os/workspace_solar_historical_status.py` module. All other
source matches the newer active release by content comparison. An
isolated port-8776 preview verified health and route presence without
production credentials; live protected DB results were intentionally
unavailable in that sandbox.

The operator-only, rollback-protected script
`scripts/deploy_private_founder_hist052_read_api_20261018.sh`
checks the exact active new release, source hashes, existing Gmail and
canonical routes, services and public Founder URL. It adds only a new
`95-private-historical-evidence-read-api.conf` override for the
existing 8766 service, and confirms that the restored read-only status
returns **six genuine private receipts, zero EmpireDB rows and an
unapplied table**. If that or any previous route check fails, it removes
the new override and restarts the previous 90-owned agent release.

**The additive private read-API release was subsequently applied and independently verified.**
It does not authorise or execute migration 052; it simply restores the
previously verified readback necessary to deploy migration 052 safely.
The existing role and systemd credential are reused without copying
private credentials.

Since the founder has ALREADY approved schema migration 052, the
trusted Ubuntu operator can run the two separate, fail-closed steps
below, in order:

```bash
cd /srv/empire_os
sudo bash scripts/deploy_private_founder_hist052_read_api_20261018.sh --apply-approved-additive-private-read-api
bash scripts/activate_workspace_historical_receipts_migration_052_20261018.sh --preflight
sudo bash scripts/activate_workspace_historical_receipts_migration_052_20261018.sh --apply-founder-approved-migration-052
```

Each command must succeed before moving to the next. The required final
markers are `FOUNDER_HISTORICAL_READ_API_ADDITIVE_RELEASE_VERIFIED`
and `EMPIREDB_MIGRATION_052_SCHEMA_VERIFIED` with an **empty table**.
The six-receipt historical importer remains a **separately gated INSERT**
and must not be run under this schema-only approval.

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

## Founder Mail evidence display — isolated release staged

The existing Founder Mail server-rendered tracking panel now also reads the
private historical receipt read endpoint and distinguishes
`6 original sends preserved in private evidence custody` from
`0 of 6 historical receipts verified in EmpireDB` while migration 052 is
still held. The text makes clear that preserved evidence is NOT a sent
intent, an approved campaign, a customer, a CRM case or realised revenue.
Invalid/stale/unavailable status renders an explicit unavailable state
instead of guessing zero or implying database completion.

The exact source change is limited to
`apps/search-command-centre/src/app/founder/mail/workspace-solar-review.tsx`.
The production Next.js 16 Webpack build completed successfully in the
frozen isolated release
`/home/ubuntu/empire_worktrees/empire_founder_mail_historical_evidence_candidate_20261018`.
An isolated loopback preview on port 3099 rendered the six verified
original sends and the correct migration-held text; all eight existing
Founder routes matched the current live console at HTTP 200, including
YouTube and Intent Review. The live console currently remains on its
previous isolated reply-triage release.

A rollback-protected, operator-only incremental release script is staged:
`scripts/deploy_private_founder_mail_historical_status_20261018.sh`.
Its read-only preflight passed against the running service; it checks
frozen source hashes, existing private API, prior 70+80 drop-ins, the
existing routes, service health and public Founder Mail HTTP 404. On
failure it removes only the new 90 drop-in and restarts the previous
private console. No database, CRM, sender, payments, public website or
customer artifact is changed by the UI switch.

**For a separately approved private UI cutover only** (not DB approval):

```bash
cd /srv/empire_os
bash scripts/deploy_private_founder_mail_historical_status_20261018.sh --preflight
sudo bash scripts/deploy_private_founder_mail_historical_status_20261018.sh --apply-approved-private-release
```

Expected success marker:
`FOUNDER_HISTORICAL_EVIDENCE_UI_RELEASE_VERIFIED`.
Do NOT claim the new panel is live until its operator output and a live
port-3001 readback confirm the new working directory. Migration 052 and
its separate protected importer remain unactivated.

## Private Founder Mail release independently VERIFIED LIVE — 18 October 2026

The founder ran the single private UI cutover command
`sudo bash scripts/deploy_private_founder_mail_historical_status_20261018.sh
--apply-approved-private-release`. Its terminal output reported
`PRECHECK_PASS` and `FOUNDER_HISTORICAL_EVIDENCE_UI_RELEASE_VERIFIED`.

Independent post-release inspection confirmed:
- `empire-founder-console.service` **active**, running the exact frozen
  `/home/ubuntu/empire_worktrees/empire_founder_mail_historical_evidence_candidate_20261018`
  release and the expected systemd drop-ins `70`, `80` and `90`.
- All eight existing private Founder routes returned HTTP **200**.
  No other agents' YouTube, Intent Review, Solar or revenue routes were lost.
- The actual live Founder Mail HTML rendered
  `Commercial outreach tracking`, `Original Gmail sends`,
  `6 original sends preserved`,
  `0 of 6 historical receipts verified in EmpireDB`,
  and `migration 052 is staged`, together with the real GB NRG and
  100% Renewables business review cards.
- The existing private API returned
  `PRIVATE_CUSTODY_ONLY_DATABASE_SCHEMA_HELD`,
  six real provider historical receipts in private custody, table
  `database_historical_receipt_table_active=false`, and **zero**
  production EmpireDB historical receipts. It reported zero canonical
  outbound intents created, CRM records created and emails sent.
- The existing authenticated CRM pilot, Founder read API, and
  original Gmail-monitoring timer remained **active**. The Gmail reply
  review still had six original sent messages and zero inbound candidates.
- The public `https://empire-ai.co.uk/founder/mail` remained HTTP **404**.
  The application continued serving only from the private listener.

**At that earlier private UI checkpoint**, the UI release was complete
but neither database operation was active. Migration 052 was subsequently
approved and successfully activated; only the separate six-row importer
remains HELD pending its own founder authorisation. To revert
only this UI release, the existing operator-run rollback removes
`/etc/systemd/system/empire-founder-console.service.d/90-private-historical-evidence-release.conf`,
reloads systemd and restarts `empire-founder-console.service`, restoring
the verified prior frozen 70+80 release. No rollback has been needed.

## Production activation confirmed — 18 October 2026, 22:16–22:18 UTC

The founder ran the operator-approved three-command sequence in the
trusted Ubuntu terminal. The first command reported:
`FOUNDER_HISTORICAL_READ_API_ADDITIVE_RELEASE_VERIFIED`, restoring the
read-only historical endpoint on the **currently active newer Founder
bridge** with the prior 90 drop-in retained for rollback.

The migration command reported all its preconditions passed:
`MIGRATION_052_SOURCE_AND_PRIVATE_EVIDENCE_PREFLIGHT_PASS` and
`LIVE_EMPIREDB_ROLE_ARCHIVER_AND_SCHEMA_PREFLIGHT_PASS`. PostgreSQL
executed `BEGIN`, created the table/function/trigger/policy and granted
SELECT, then returned `COMMIT`,
`MIGRATION_052_SQL_TRANSACTION_RETURNED_SUCCESS` and
`EMPIREDB_MIGRATION_052_SCHEMA_VERIFIED`. The release readback
confirmed forced RLS, the append-only trigger, observer SELECT without
INSERT/UPDATE/DELETE and exactly **zero** receipt rows.

An independent subsequent live read from the existing loopback Founder
API (port 8766) returned the precise JSON state
`SCHEMA_ACTIVE_NO_HISTORICAL_RECEIPTS` with:
- `private_custody_receipts_verified=6`
- `database_historical_receipt_table_active=true`
- `database_historical_receipts_verified=0`
- `canonical_outbound_intents_created=0`
- `crm_records_created=0`
- `outbound_sent=false` and `database_writes=false` (reader path)

All four existing Founder Console / read API / CRM pilot / Gmail timer
units remained active. The Gmail review still showed the original six
genuine sent messages and zero new inbound header candidates. Public
`https://empire-ai.co.uk/founder/mail` remained HTTP 404.

**Closed gap:** migration 052 schema and owner-preserving private API
readback are live and verified. **Open gap:** import the six preserved
historical receipts into the new table, which is a separate six-row
database write and was NOT included in the migration approval. Its
importer remains gated pending explicit founder authorisation.
Even after such an import, historical receipts remain `UNBOUND`, not
approved outbound intents, verified tenants, genuine replies, CRM
customers or realised revenue.

## Founder approval of exactly six evidence inserts — 18 October 2026

The founder subsequently gave **explicit approval** to import the six
authenticated historical Gmail receipts into the now-active migration 052
table and continue building the read-only commercial lineage workflow.
This is a separate authorisation from the earlier **schema-only** approval.
Its permitted effect is a single idempotent transaction inserting up to six
previously verified, still-unbound historical sent receipts into
`public.workspace_historical_sent_receipts`. No `outbound_intents`
approval, tenant authority, CRM customer, reply, email send or payment is
authorised or inferred.

The importer's default DSN was pinned to local PostgreSQL socket
`/var/run/postgresql`, port `5432`, database `empiredb`, OS peer
account `postgres`. The approved import preflight and regression suite
PASS. The connected remote command interface explicitly rejected the
privileged operator command `Command not allowed`, and no bypass was
attempted. **The production table therefore remains empty pending the
founder's trusted Ubuntu execution.** The six original provider receipts
remain intact in the restricted 0600 private custody.

A separate exact six-company, read-only verification runner was built at
`scripts/verify_workspace_historical_six_import_20261018.py`. It
reads only two existing private loopback APIs, validates every individual
receipt as still UNBOUND, verifies independent six original sent anchors,
and rejects fabricated approval, CRM, outbound or revenue authority. It
returns a nonzero status until all six historical rows are proven in
EmpireDB. Its tests pass with no live database mutation.

**Single founder-owned authorised transaction, then independent readback:**

```bash
cd /srv/empire_os
sudo /srv/empire_os/.venv/bin/python -B -m scripts.import_workspace_historical_sent_receipts_20261018 --apply-founder-approved-historical-receipts-only
/srv/empire_os/.venv/bin/python -B -m scripts.verify_workspace_historical_six_import_20261018 --verify-read-only
```

Expected import marker:
`SIX_EXTERNAL_SENT_OBSERVATIONS_STORED_UNBOUND`,
`verified_receipts=6`, `new_receipts=6` (or
`replayed_identical_receipts=6` on a verified idempotent rerun).
Expected post-import verification marker:
`SIX_HISTORICAL_GMAIL_RECEIPTS_IN_EMPIREDB_VERIFIED`.
Do not proceed as though the transaction succeeded if the importer
returns `HELD_HISTORICAL_RECEIPT_IMPORT` or the readback runner
returns `HISTORICAL_SIX_IMPORT_VERIFICATION_HELD`.

Even once proven, the imports are historical external-sent **evidence**,
not canonical-approved sends or sales opportunities. Buyer contact,
suppression and tenant matching remain their own later review stages.

## Six-receipt production import completed — independently verified

The founder ran the separately approved, explicit one-time historical
receipt import in the trusted EmpireOS Ubuntu terminal. The importer
reported `SIX_EXTERNAL_SENT_OBSERVATIONS_STORED_UNBOUND`,
`verified_receipts=6`, `new_receipts=6`,
`replayed_identical_receipts=0`, and **zero** canonical outbound
intents, CRM rows, email sends, payment events and retrospective approvals.

The immediately following independent check reported
`SIX_HISTORICAL_GMAIL_RECEIPTS_IN_EMPIREDB_VERIFIED`. A second readback
through the *running* private Founder API confirmed:
`SIX_HISTORICAL_RECEIPTS_VERIFIED_IN_EMPIREDB`, six original authenticated
Gmail sent messages, six immutable historical DB receipts and the
per-company `UNBOUND_HISTORICAL_EVIDENCE_IN_EMPIREDB` classification
for GB NRG, Perfect Sense Energy, Solar4Good, Sustain Commercial Solar,
SOL PV Group and 100% Renewables. The standard CRM pilot, Gmail timer,
Founder Console and read API all stayed active. No incoming Gmail
candidate, CRM conversation, canonical original approval or revenue
was verified.

**Evidence import is closed.** Do NOT replay these six historical
outreach emails or create six synthetic `outbound_intents` in an attempt
to make the CRM look populated. The separate consent, suppression,
contact identity and tenant authority checks remain genuine
commercial dependencies.

## Read-only six-company CRM reconciliation built after import

New `empire_os/workspace_solar_crm_readiness.py` and
`scripts/review_workspace_solar_crm_readiness_20261018.py` read the
three **existing** private Founder API surfaces: authenticated Workspace
reply review, exact canonical thread/recipient intent aggregates, and
historical six-receipt DB admission. Every company must appear exactly
once in all sources, and the no-approval/no-CRM-write flags must agree.
Incomplete, stale, contradictory or forged source authority fails closed
rather than producing a false commercial opportunity.

The initial live on-demand check passed for all six companies:
`SIX_COMPANY_HISTORICAL_TO_CRM_GAP_REGISTER_READ_ONLY`,
`historical_receipts_verified_in_empiredb=6`,
`inbound_provider_header_candidates=0`,
`crm_records_created=0`. For each company the restricted canonical
observer still sees no matching original canonical intent, and no
genuine incoming buyer reply is observed. These are two **separate**
unresolved steps; historical evidence storage alone is complete.

Read-only repeat, no sudo or activation required:

```bash
cd /srv/empire_os
./.venv/bin/python -B -m scripts.review_workspace_solar_crm_readiness_20261018 --read-only
```

This command is not a CRM promotion workflow and grants no outbound or
payment authority. No extra timer, database migration, API listener,
login or inbox was created. The existing five-minute Workspace monitor
continues to produce the original independent reply evidence.

## Commercial completion gates still open

1. **Closed:** all six historical receipts were independently verified in
   EmpireDB through the existing private Founder read workflow.
2. **Open:** when a genuine reply arrives, verify original provider chain,
   sender and message content, suppression/opt-out state, exact contact
   and tenant authority before any CRM promotion.
3. **Open:** design a separately reviewed canonical intent/contact admission
   if an external historical send produces a real buyer conversation. The
   evidence table alone cannot backfill previous approvals.
4. **Open:** continue legitimate commercial acquisition through the existing
   approved programme. Six sent emails alone are not buyer interest or revenue.

**Current verified status:** six authentic Gmail original-sent receipts
are stored in EmpireDB under migration 052 with forced RLS and an
append-only trigger. The separately approved six-row import is complete
and independently read back; the receipts remain UNBOUND, not canonical
approved outbound intents. The existing Gmail observer has zero incoming
reply candidates, with no verified CRM opportunity or recognised revenue.
