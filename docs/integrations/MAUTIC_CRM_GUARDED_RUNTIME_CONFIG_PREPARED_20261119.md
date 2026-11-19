# EmpireOS — Mautic 7 to existing Smart CRM: guarded activation contract

**State:** IMPLEMENTED_AND_ISOLATED_TESTED, NOT LIVE, NO APPROVAL IMPLIED.
**Owner:** Existing Smart CRM/first-party-login and DBA owners.
**Branch:** integration/mautic-crm-active-20261119.
**Synthetic native producer evidence:** https://github.com/empireaipredictiverevenue-coder/empire_os/actions/runs/44526866616

## Exact activation behaviour

The existing EmpireOS hub calls create_crm_routers_for_hub(). It still exposes
the original CRM read-only stub unless the existing founder-authorised
EMPIRE_CRM_PILOT_MODE and EMPIRE_CRM_PILOT_CONFIG_FILE are configured.

The Mautic route pair is additionally created **only** if both separate
settings exist, in the same process, with these exact values:

    EMPIRE_CRM_MAUTIC_MODE=APPROVED_READ_ONLY_MAUTIC_INBOX
    EMPIRE_CRM_MAUTIC_CONFIG_FILE=/absolute/private/mautic_source.json

With no separate Mautic settings, the existing pilot stays exactly two
routers. A Mautic setting without an approved CRM pilot, partial settings
or an unknown mode causes fail-closed startup rather than activation.

The separate source JSON must have EXACTLY these fields:

- schema_version: empire.mautic_crm_source_pilot.v1
- founder_approval_ref: separate, explicit approval reference, distinct
  from the original CRM pilot's founder_approval_ref
- source_id: stable lower-case [a-z0-9_-] name (3–64 chars)
- tenant_id: canonical UUID already present in the approved CRM pilot's
  dedicated tenant reader inventory; no caller-supplied tenant ID
- source_evidence_ref: reviewed Mautic source provenance reference
- webhook_secret_file: absolute owner-private, regular, non-symlink file
  holding exactly 64 lower-case hex characters (Mautic source secret)
- writer_dsn: local /var/run/postgresql port 5432, empiredb database,
  dedicated empire_mautic_tenant_[0-9a-f]{12,32} LOGIN distinct
  from all CRM pilot reader DSNs; no network or shared DB login
- contact_bindings: 1–200 explicit numeric Mautic contact IDs, each
  mapped to {"prospect_id": "canonical CRM prospect UUID",
  "identity_evidence_ref": "independently verified evidence ref"}

Only original approved CRM tenant DSNs are reused for canonical prospect
reads. The source's distinct writer role is used exclusively by the
existing prepared Postgres Mautic inbox. No new CRM, sender, data broker,
account, connection-sharing layer or downstream workflow is built.

Files must be owned by root or the authorised CRM service process, mode
0600 (no group/other access), non-symlinks, and within configured size
limits. Duplicate JSON keys, unknown fields, missing identity evidence
references, noncanonical IDs, reuse of CRM read logins, cross-tenant
mapping, malformed secrets, and duplicate prospect mappings fail closed.

**Do NOT put real credentials, contacts, tokens or proofs in Git.**
The strings in this document are FIELD CONTRACTS, not approved source
bindings. No production source/tenant/identity evidence is invented.

## HTTP after explicit staged opt-in

1. POST /v1/revenue-crm/integrations/mautic/{source_id}/events/preview
   is the existing Mautic signed-body ingress. It requires the private
   per-source HMAC secret, known server-approved source/tenant, exact
   verified contact binding, canonical tenant-bound prospect reader,
   and successful real EmpireDB inbox commit plus readback.
   A valid event with an unbound contact or unavailable canonical reader
   yields HTTP 503, so upstream Mautic retains/retries it; no false ack.

2. GET /v1/revenue-crm/integrations/mautic/inbox/reviews
   uses exactly the original CRM authenticated principal resolver and
   the dedicated CRM reader with existing session_user/tenant RLS.
   It returns bounded REVIEW_ONLY metadata without raw contact PII,
   and cannot send, write CRM or clear suppression.

No source mode offers publishing, customer messaging, payments, consent
promotion or autonomous campaign execution. No public source is mounted
without both separate gates.

## Real state and controlled release boundary

- PASS: Official Mautic 7.2.2 + disposable MySQL installed in hosted CI;
  native queued signed suppression webhook delivered to actual EmpireOS
  adapter; 503 retained the queue with retries=1; second HTTP 200
  acknowledged/deleted the queue. Isolated containers/volumes cleaned.
- PASS: The separately prepared SQL inbox role/RLS/isolation tests using
  disposable genuine PostgreSQL 18. No live EmpireDB migration.
- PASS: Opt-in CRM pilot wiring security unit and regression tests.
- HOLD: **No verified production Mautic source identity binding** has been
  presented to this guarded configuration. A founder approval reference
  in a file is not independently proven permission to deploy.
- HOLD: The unnumbered, DBA-only SQL
  docs/integrations/sql/MAUTIC_CRM_EVENT_INBOX_PREPARED_ONLY_20261119.sql
  has not been applied and role grants are not provisioned for production.
- HOLD: Reconcile the live CRM owner's uncommitted auth/tenant changes;
  verify production DB grants and authentic member login.
- HOLD: Founder's guarded canary/release permission for source secret
  provisioning and endpoint exposure; do not infer it from engineering
  permission or from successful synthetic tests.

**Next actual activation dependency:** the existing CRM/DBA owner must
verify one genuine first-party Mautic contact ID to canonical prospect
identity with provenance; approve required tenant-specific read/write
roles and DBA migration; verify private source registration; run a
single no-send canary and read back the canonical inbox. These are
external authority/evidence tasks, not software-install blockers.

**No production changes, database writes, customer messages, paid
resources or host permissions occur by importing this module.**


## Live EmpireOS readiness readback — 19 November 2026

Performed on the already-running EmpireOS host. **Read-only only:** no
schema installation, roles, service changes, credentials rotated, email
delivery or customer data reads. The actual pilot process's existing
configured PostgreSQL password file was reused in memory (not printed
or copied) for an authenticated tenant-role catalog-only transaction.

**Existing live CRM pilot (empire-revenue-crm-pilot.service):**
- Service status: active/running (started 16 November 2026).
- Existing EMPIRE_CRM_PILOT_MODE: APPROVED_READ_ONLY_PILOT.
- Existing pilot config path: configured and readable to its service user.
- Existing pilot configured tenant login inventory: 1.
- Existing authenticated tenant LOGIN: successfully connected to
  canonical EmpireDB with SET TRANSACTION READ ONLY.
- HTTP GET /v1/revenue-crm/prospects without auth: 401.
- Mautic inbox GET and unknown-source webhook preview: 404.
- EMPIRE_CRM_MAUTIC_MODE is unset; no Mautic pilot config is registered.

**Direct canonical EmpireDB catalog facts (verified on same tenant LOGIN):**
- Correct database = empiredb: TRUE.
- public.empire_current_tenant_id() exists: TRUE.
- Existing empiredb_migrator role: TRUE.
- Existing empire_revenue_crm_reader role: TRUE.
- Tenant-bound SECURITY DEFINER function meets expected migrator
  ownership / stable-function guard: TRUE.
- Canonical tenant login CONNECT privilege: TRUE.
- public.empire_crm_mautic_event_inbox exists: **FALSE**.
- empire_mautic_crm_inbox_writer role exists: **FALSE**.
- Login roles matching empire_mautic_tenant_%: **0**.

**Decision:** The running CRM pilot works as its existing authenticated
reader and is NOT a deployed Mautic integration. This is not a Docker
or webhook delivery problem; actual Mautic 7 producer delivery and
HTTP503 retry are independently verified by CI run 44526866616.

**Required approved DBA delta:** Independently provision/verify the
dedicated NOLOGIN, NOINHERIT Mautic inbox writer and a unique tenant
LOGIN with an existing authorised tenant binding, including schema
USAGE. Then review, number and apply the existing **prepared-only**
Mautic inbox migration under the established DBA change/rollback
procedure, not from this branch. Do not copy any synthetic contact
mapping to live CRM. The existing verified tenant reader keeps only
SELECT on the review table.

**Required commercial/identity delta:** An actual authorised Mautic
source must exist, with a server-held secret, immutable first-party
Mautic numeric contact-to-canonical prospect proofs and explicit
founder approval for the scoped no-send canary. A checked-in evidence
reference string is not proof of a real approved source.

**No-merge reason:** The running production checkout includes
uncommitted CRM owner auth/transport changes and uses branch
agent/data-cloud-wave4, which is over a thousand local commits ahead
of its remote. GitHub main differs from this integration by thousands
of unrelated commits. Opening an ordinary PR to main or replacing
production code would sweep unrelated owner work into a release.
Preserve the existing clean pushed integration branch until the CRM
owner selects the correct reviewed release base.

**Next verifiable production milestone:** Approved DBA role/migration
receipt + verified live source/identity binding -> one guarded ingress
canary -> authenticated tenant-only inbox readback -> explicit final
founder release decision. No application restart, schema write,
provisioning or sender activation is implied by this document.


## DBA role + fail-closed rollback: executed in disposable PostgreSQL 18

The live EmpireDB public schema is owned by pg_database_owner;
empiredb_migrator has USAGE and CREATE but no schema GRANT OPTION.
Therefore the required writer's schema USAGE must be granted by the
actual DBA/schema owner, not by SET ROLE empiredb_migrator.

The missing exact writer-role bootstrap is now prepared here:
docs/integrations/sql/MAUTIC_CRM_INBOX_WRITER_ROLE_PREPARED_ONLY_20261119.sql

It creates one NOLOGIN, NOINHERIT, nonprivileged writer and grants
schema USAGE. It checks the canonical security-definer tenant-binding
function, refuses role collisions, and cannot create customer data,
tenant writer logins, passwords, or network listeners.

The existing prepared inbox table and RLS migration remains:
docs/integrations/sql/MAUTIC_CRM_EVENT_INBOX_PREPARED_ONLY_20261119.sql

The prepared DBA-controlled rollback is:
docs/integrations/sql/MAUTIC_CRM_INBOX_ROLLBACK_DBA_ONLY_20261119.sql

Rollback must refuse any tenant login memberships or stored event
evidence. It cannot use CASCADE or DROP OWNED BY; an authorised
DBA may roll back only an empty, disconnected inbox. Never discard
real customer evidence just to make rollback pass.

**Executed fixture proof:** scripts/test_mautic_crm_pg_isolated.sh
now provisions the exact role, applies the exact migration, passes all
7 tenant/RLS/HMAC/receipt tests on a truly disposable PostgreSQL 18
cluster, confirms a second role bootstrap refuses existing-role
collision, confirms the rollback refuses member-bound and nonempty
inboxes, and after fixture-only clearing verifies empty-role/table
rollback succeeded. No production DB, roles or source was modified.

**Production still requires exact DBA authority and verified source:**
approved change/rollback and backups; checked real instance and role;
unique tenant writer login bound to an independently verified
session_user tenant; original numbered migration; real Mautic source
and numeric-contact to canonical prospect evidence; guarded no-send
canary followed by authenticated inbox readback. Missing real source
evidence must never be substituted with a synthetic ID.


## Corrected approval and identity source of truth (2026-11-19)

The original isolated source configuration correctly required private files
and evidence-ref syntax, but the application was still trusting arbitrary
well-formed source_evidence_ref, founder_approval_ref and
identity_evidence_ref strings without checking their underlying records.
This is not independent verification and is now corrected.

The existing CRM pilot additionally requires its original owner to inject
a Trusted Mautic Evidence Authority object with two methods:

- verify_source(source_id, tenant_id, source_evidence_ref,
  founder_approval_ref) -> exactly True only for a genuinely authorised
  source and founder-approved integration proven in first-party records.
- verify_binding(source_id, tenant_id, contact_id, prospect_id,
  identity_evidence_ref) -> exactly True only where the exact Mautic
  numeric contact and canonical CRM prospect have independently verified
  immutable first-party identity provenance.

These callbacks are internal Python dependencies, NOT fields from the
Mautic webhook payload, source JSON, environment variables or HTTP
headers. Exceptions, unavailable records, False/None/non-True returns
or absent callbacks fail closed *before either Mautic router is mounted*.

No real verified source or contact-binding evidence authority was
found in the running production CRM. Therefore the integration cannot
claim founder or identity approval merely because strings in a local
JSON file look plausible. Existing CRM-only pilots keep their original
routing and authentication, unaffected.

The synthetic tests supply a fixture-owned mock attestor with exact
positive and negative reference comparisons. This is test proof of the
fail-closed mechanism, NOT a real customer identity, real Mautic
installation or live founder approval. A real owner-backed verifier
must be attached as part of the guarded source/DBA release.

**Current release truth:** integration implemented and tested in an
isolated branch; native queue/503 retry proven in separate GitHub CI;
production no Mautic daemon, no source configuration, no source identity
attestation, no Mautic inbox/writer SQL, no public route and no sending.
Do not enable EMPIRE_CRM_MAUTIC_MODE on the existing service until the
record-backed verifier and the DBA/source release gates are complete.


## Full private-configuration → PostgreSQL integration proof (19 November 2026)

The eight-test disposable PostgreSQL 18 fixture now includes a full
configuration-to-receipt canary rather than testing the source factory
and database webhook handler independently.

The canary uses:
- A private 0600 source JSON and separate private 0600 64-hex webhook
  secret, decoded by the actual production source factory.
- The independent, synthetic first-party approval and exact contact
  verifier injected at the existing Smart CRM pilot wiring boundary.
- Real, distinct NOINHERIT PostgreSQL login roles matching the production
  reader/writer naming constraints, mapped via the same
  session_user-derived tenant resolver and enforced by actual PostgreSQL
  FORCE ROW LEVEL SECURITY.
- An exact signed Mautic-shaped subscription-change event delivered to
  the configured HTTP ingress route, followed by a committed inbox
  readback using the existing authenticated CRM review router.
- No email, SMS, marketing consent grant, customer row write, or sender
  registration. A second signed delivery is a deduplicated replay.
  An unbound numeric Mautic contact returns retryable HTTP 503.
- Live-instance-style revocation: the fixture source/identity authority
  is revoked AFTER source configuration and router construction.
  Both a revoked source and a revoked contact binding independently cause
  HTTP 503, before canonical DB access or a receipt. Approvals made at
  process startup cannot stay effective after the authoritative evidence
  has been withdrawn.
- Invalid-signature requests are rejected before touching the
  independent source/identity evidence authority, avoiding a
  database query for unauthenticated requests.
- Private role creation, prepared inbox migration, real RLS tests,
  collision rejection, refusal to roll back nonempty/member-bound
  evidence, then empty-only fixture rollback and complete cleanup.

**Scope limitation:** All tenant IDs, contact IDs, source refs and founder
references in these tests are synthetic. This is a genuine configured
HTTP → PostgreSQL integration test, not a production customer canary
or proof that a live Mautic source exists.

**Production remains held:** The live Mautic application and source
evidence are not present; the actual DBA role and inbox have not been
provisioned. The running Smart CRM pilot must not be restarted or
given arbitrary synthetic contact identities as a substitute.
