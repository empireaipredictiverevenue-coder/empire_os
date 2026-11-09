# CRM search evidence connection — implementation checkpoint

Status: scope validation, candidate database reader and HTTP adapter implemented.
HTTP mount tested on isolated authenticated CRM source; branch reconciliation
and production activation pending.
Production activation: not authorised by this document.

## Observed boundary

Founder-provided EmpireDB catalog capture confirms seo_sites has id,
tenant_key and base_url, but no canonical entity or UUID tenant link.
prospect_entity_links connects prospects to business_entities.
tenant_business_entity_bindings holds evidence-backed, time-limited tenant
scope. The displayed grants give empire_search_reader SELECT on search sites,
backlinks and AI visibility; the capture does not prove all effective grants.

The inspected CRM authorization function uses session-derived tenant identity
and requires exactly one eligible prospect/entity/binding join. Observed-only
bindings are excluded. The existing search repository uses a configured text
tenant_key. Neither a request tenant key nor a matching website establishes
CRM authority.

## Required flow

Authenticated CRM principal -> existing authorised prospect/entity resolution
-> explicit tenant/entity/site evidence binding -> restricted observation read
-> existing growth brief builder.

The new revenue_crm_search_scope module validates server-loaded mapping rows.
It is not authentication and must never receive binding records from an HTTP
payload. Its tenant and authorised entity arguments come from trusted CRM
resolution. The request may select prospect/site IDs but cannot authorise them.

## Database delta to prepare and verify

Prepare a separately reviewed, initially empty tenant/entity/site binding
relation in EmpireDB. Required values: tenant UUID, entity UUID, site UUID,
search tenant key at approval, binding evidence reference, active flag,
valid-from and optional valid-until. Use existing entity/site foreign keys.
Pin the approved site identity (including base URL) or revoke the binding on
identity changes; a mutable site URL must not silently redirect authority.
Do not seed bindings by matching domain names, and do not cast tenant_key to
the CRM tenant UUID. Genuine owner evidence is required for provisioning.

Prepare a bounded restricted reader following the existing trusted session
tenant foundation. It must independently recheck CRM prospect authorization,
exact entity identity, binding validity, site identity and tenant-key match
within the same read-only transaction as observation selection. The Python
validator is defence in depth, not the database access boundary.

Do not grant the CRM reader access to the global binding tables or membership
in empire_search_reader. The intended narrow reader returns tenant_id,
prospect_id, entity_id, site_id, binding provenance and only the selected site's
observations. Select query/engine before limiting citation rows; return explicit
truncation metadata. Sanitize errors without hiding unavailable evidence.

Authenticated route outcomes must distinguish unauthenticated, unauthorized,
not connected, connected with no observations, connected with observations,
and reader unavailable. The existing caller-supplied preview remains a preview.
Neither empty results nor a valid binding proves rankings, revenue or citations.

## Required verification before activation

Scope unit tests cover cross-tenant/prospect/entity/site rejection, duplicate
current bindings, revocation, expiry, future validity, malformed provenance and
timezones. Eight local cases pass. These tests do not prove PostgreSQL isolation.

Candidate SQL now lives in migrations/empiredb/proposals; no production
migration number is reserved. It creates an empty, inactive-by-default explicit
binding table and a restricted reader, owned by the existing migrator role.
It pins the approved base URL and search tenant key and checks current CRM
scope within the database statement. Runtime callers receive EXECUTE only.
The revised function uses row_security=on with explicit session-tenant/site
policies. An exact effective-policy contract check rejects policy drift instead
of reporting silently filtered rows as empty evidence. No BYPASSRLS is granted.

The candidate has been exercised in a temporary PostgreSQL 18 cluster with
real tenant A/B and unbound login sessions. Fixtures are isolated synthetic
test records, never production observations. The cluster listens only on its
private Unix socket and is stopped and removed after testing. Fixture schema
is deliberately minimal; this does not establish compatibility with every
live policy, grant or source-table constraint.

The HTTP adapter now reuses the request-scoped CRM repository and its existing
_fetch_all login/tenant checks. It validates the result envelope before passing
stored observations to the existing growth brief builder. It adds no DSN,
global repository, authentication system or caller-supplied evidence endpoint.
The exact mount is docs/patches/crm_search_authenticated_mount.patch, tested on
server commit 68a1aafbe89c19566821c66e8d12b9ef8abe3b8f in isolated worktree
/home/ubuntu/empire_worktrees/crm_search_http_20261025. Eight HTTP tests pass
with test-double database responses; the ten real PostgreSQL reader tests run
separately. A combined HTTP-to-real-database test has now passed; see the 2026-11-09 checkpoint below.

The GitHub base inspected at 3ca194c051906780e66029c23758f7492a964fd9 still lacks
the authenticated CRM API. Do not apply the mount there or replace its API with
the newer server file wholesale. The integration tests explicitly skip on that
old base; skipped CI tests are not acceptance evidence. Reconcile with the
authenticated CRM owner branch and require the tests to actually execute.

Next: reconcile the candidate
with the current live catalog, owner privileges, RLS policies and migration
sequence before requesting production activation. The rollback refuses to
drop provisioned bindings; recovery with real binding history needs review.

Shared /srv/empire_os has concurrent edits including CRM transport; do not
overwrite them. This checkpoint is a separate draft scope-validation slice,
not a claim that the account evidence reader or wider SEO programme is complete.

## 2026-11-09 verification checkpoint

PR #105 remained open/unmerged at 2af2b31a1b1b21eeab608abffe7c6b02f5f0d416.
Observed shared checkout HEAD: f51b67be47d76c836816f5a6c0c71f1b8157c799.
The active CRM service working directory is
/opt/empire-ai/crm-pilot-releases/smart-crm-work-queue-20261104v1.
The shared API still exposes the supplied-data preview and does not mount this
stored-evidence route. The shared transport has uncommitted changes owned
outside this bounded verification task; they were not modified or staged.

Added tests/test_crm_search_evidence_end_to_end.py. Actual run: 15 tests passed,
zero skips, using the existing isolated authenticated-API worktree and a fresh
PostgreSQL 18 Unix-socket cluster. Five combined HTTP/database cases plus ten
inherited SQL cases executed. The real PostgresRevenueCrmRepository connects
as tenant A/B database LOGINs; its _fetch_all method is not mocked. The tests
verify stored citation analysis, binding revocation between HTTP requests,
tenant-B own scope, cross-tenant denial, HTTP/database tenant mismatch,
missing-login rejection and source privilege failure returning sanitized 503.
The fixture now includes the existing CRM040 EXECUTE prerequisite for the
trusted tenant resolver, so the real transport can perform its own check.

Limits: the HTTP authentication callback supplies isolated fixture identities;
this does not test founder cookies, signature verification or the live gateway.
Fixtures use minimal schemas and fixture-only source records. The temporary
cluster was shut down and removed. The HTTP mount remains an isolated patch;
no production migration, grant, binding, restart or deployment was performed.

Release dependency belongs to the existing authenticated CRM integration owner:
reconcile the reviewed mount/reader with that owner's current branch and
transport changes, verify current live catalog/RLS/owner prerequisites, and
prepare the explicitly gated migration and code release. No authority to merge
another owner's unfinished work is implied by passing these tests.

## Current transport compatibility — 2026-11-09

The previously unresolved transport difference is now tested. The shared
transport adds CRM_LOGIN_AUTHORITY_SQL and checks dedicated login membership
and privileges before SET LOCAL ROLE. Without changing that file, loaded its
exact source (SHA256 853f3bcd9d69be07685c6cf7db0c20578a9b6a4471f6afe8772108ab79728a9a)
into the isolated integration suite. All 15 HTTP/PostgreSQL checks passed, with
zero skips. No transport modification is required for this search integration.
The presence of uncommitted transport changes is not itself evidence of an
active conflicting operator; persistent ownership must still be reconciled
before modifying shared release files.

Bounded production proposal, NOT executed: install only the reviewed search
binding/reader migration, add the search-evidence adapter and mount to the
existing authenticated CRM release, retain the existing transport and auth,
and verify unsigned rejection plus a genuine signed founder session. Leave
site bindings empty/inactive until genuine scope evidence is provisioned.
No observation collection, outreach, publication or payment activation.

Before apply, original CRM/DB release owner must confirm current migration
ordering, prerequisite function definitions/owners, effective privileges,
source schema/RLS compatibility, current release identity and rollback. If any
precondition differs, stop before mutation and reconcile the exact delta.
The new SQL rollback may run only while no binding history exists; otherwise
preserve evidence and review recovery. This is a code/tested proposal, not
production migration approval or a claim of live functionality.

## Founder-approved release: live ACL reconciliation — 2026-11-09

Founder explicitly approved the bounded migration and authenticated CRM route
release, conditional on preflight. Approval persists; no binding provisioning,
outreach, collection or payments are included. Desktop Commander rejected the
sudo PostgreSQL preflight as "Command not allowed"; no alternate execution
route was used. Founder supplied two read-only catalog captures instead.

Observed in those captures: both trusted functions are stable SECURITY DEFINER,
owned by empiredb_migrator with empty search_path; session_user determines
tenant identity. New table/function are absent. All three SEO tables are owned
by postgres, have RLS enabled, and lack effective SELECT for migrator.
Migrator is nonsuperuser, no BYPASSRLS, inherits empiredb_tenant_reader only.
Existing SEO policies target empire_search_reader using app.tenant_key.

Root cause in candidate: the old fixture owned SEO tables as migrator and did
not reproduce production ACL/RLS. Passing its 15 tests did not prove readiness
against the live source ownership contract. Fixture corrected to independent
administrator ownership, enabled RLS and existing legacy search policies.

Smallest candidate delta:
- grant migrator SELECT on only the three source tables, constrained by added
  policies using trusted session tenant plus current, identity-pinned bindings;
- preserve existing search policies and all roles' BYPASSRLS attributes;
- temporarily grant site-id REFERENCES for FK creation, restore prior effective
  absence before commit, preserve pre-existing reference permission;
- reader uses row_security=on and checks exact applicable policy definitions,
  roles, command and enabled RLS, rejecting added or changed applicable policies;
- migration validates source column types, baseline SELECT absence, RLS, trusted
  function owners, default ACL exposure and empty bindings transactionally;
- rollback removes only this function/table, three new policies and SELECT
  grants; refuses to destroy any populated binding history.

Validation: 19 combined HTTP/PostgreSQL tests passed, zero skips, in isolated
PostgreSQL 18; git diff --check passed. Includes legacy reader preservation,
forced RLS isolation, disabled RLS rejection, altered policy rejection,
unexpected public policy rejection, revoked source privilege, and all previous
HTTP/tenant/binding/query/rollback cases. Tests supply fixture HTTP identities;
genuine signed founder-session verification remains a live acceptance step.

Candidate SHA256:
9c232e5ac7d8712da87eba0b244e7e2b46187516f086f0b3a425c678afddca02
Path: migrations/empiredb/proposals/crm_search_evidence_reader.sql

NOT LIVE. Apply uses one transaction and ON_ERROR_STOP; any guard failure
rolls back the whole database delta. No restart is part of this database step.
The authenticated route release must follow confirmed database installation
and fresh current-release reconciliation; shared dirty auth/transport unchanged.

## Provenance type correction after failed live preflight — 2026-11-09

Founder ran candidate SHA256 9c232e5ac7d8712da87eba0b244e7e2b46187516f086f0b3a425c678afddca02.
It failed at the initial schema guard, before grants or object creation.
Follow-up catalog capture confirms the new binding table and reader are absent.
Actual observation provenance columns are text[], not the assumed jsonb.
All other source columns required by the reader match the supplied catalog.

Corrected only the two provenance type expectations in the candidate SQL.
Updated both SQL and HTTP/database fixtures to store native text arrays and
insert ARRAY literals. Existing to_jsonb row serialization produces the JSON
arrays expected by the adapter; no production column conversion is needed.
Nineteen HTTP/PostgreSQL integration tests passed, zero skips (2.652 seconds).
git diff --check passed. No live migration, restart or route deployment occurred.

Replacement candidate SHA256:
f989749d437f7e47377eca1cdf6a801c2de6cb2081c63a1a1ffcde8fdffeae44

The original bounded founder approval remains applicable. The replacement
candidate retains all guards and the single-transaction installation. Use its
new checksum; do not retry the superseded candidate.

## Default-ACL correction after final guard rejection — 2026-11-09

Founder capture shows the text-array candidate passed schema and policy guards,
then failed its final ACL guard. Subsequent catalog confirms both new objects
are absent. The transaction rolled back. Observed migrator defaults in public:
empiredb_app SELECT/INSERT/UPDATE/DELETE and empiredb_readonly SELECT on tables.

Candidate now explicitly revokes all table privileges from those two roles on
crm_search_site_bindings only. No ALTER DEFAULT PRIVILEGES is performed by the
migration. Existing database defaults and existing objects remain unchanged.
The final unexpected-ACL guard remains in place.

Fixture now reproduces those five default grants. Twenty HTTP/PostgreSQL tests
passed with zero skips (2.761s), including explicit denial of both generic
roles on the binding table and preservation of all five default grants.
git diff --check passed. No production application or restart performed.

Replacement SQL SHA256:
8dd86492653b3e844b0251013fd461d4f2bc8f9d52487d270e51deffc5450ac6
Use this checksum for the already-approved bounded migration. Bindings remain
empty; authenticated HTTP mount and genuine founder-session proof remain pending.

## Database commit and current-runtime route preparation — 2026-11-09

Founder terminal capture confirms SHA256 8dd86492653b3e844b0251013fd461d4f2bc8f9d52487d270e51deffc5450ac6 passed every migration guard and COMMIT.
This is founder-reported installation evidence; independent catalog readback is
included in the prepared route publisher before it can modify any source file.

Read-only service inspection confirms active service on port 8783, working
directory /opt/empire-ai/crm-pilot-releases/smart-crm-work-queue-20261104v1,
entrypoint private_crm_original_v411_source_entrypoint_20261108:app.
Preserve current Data Cloud and LinkedIn overlays, auth and transport.

Staged exactly three files in the owned worktree:
proposals/crm_search_release_20261109/
- revenue_crm_api.py: current deployed API plus six-line authenticated mount
- revenue_crm_search_growth.py: tested evidence-reference deduplication
- revenue_crm_search_evidence_api.py: existing tested restricted reader adapter

All 20 combined HTTP/PostgreSQL tests passed using this staged API/growth/adapter
and the actual deployed CRM dependencies/transport, zero skips (2.696s).
Publisher database readback SQL separately passed against the isolated fixture.
Publisher checks source hashes, runtime identity, installed reader body/ACLs and
zero bindings before changes. It backs up only the two replaced files, installs
three pinned files, restarts this one existing service, checks unsigned 401 and
writes an explicit receipt with signed_founder_session_verified=false.
No database writes, bindings, outbound or financial activation are included.
No automatic rollback/retry is attempted on failure; preserve the scoped backup.

Publisher SHA256:
3b5d35724a0325df9207047d9f47adab7c231fc8de02b808f10f7a2256b574b0

NOT EXECUTED. The founder must run the bounded publisher through the existing
terminal because the remote tool rejected privileged database access. The
existing release approval stands. A genuine signed founder-session acceptance
check remains required after unsigned runtime verification.

## Failed in-place route release, verified recovery, additive replacement

The founder executed the former publisher. Database preflight passed. Its
in-place API replacement caused the original LinkedIn entrypoint to reject
pinned_crm_work_queue_release_drift. Service failed after systemd retries.
Original API and growth files were restored from the scoped backup; added
adapter removed. Independent remote checks confirmed active/running, zero
restarts since recovery, health 200 and unsigned prospect access 401, with
original SHA256 values restored. Database migration remains installed.
The former publisher now refuses execution unconditionally (WITHDRAWN).

Root cause: tests imported the API with deployed dependencies but omitted the
whole startup chain's frozen-source hash checks. That verification was
insufficient for production release. Do not change or disable those guards.

Replacement package proposals/crm_search_additive_20261109 imports the entire
original entrypoint first, then attaches only the new route. It reuses the
existing signed CRM authenticator, account-bound membership and dedicated
tenant transport using already-validated configuration held in memory.
No existing empire_os file, HTML/JS, auth guard or service credential changes.
The growth builder/adapter are packaged versions of the existing implementation;
no second runtime, collector or authority is introduced.

Validation:
- 21 isolated PostgreSQL/HTTP tests passed (3.563s), zero skips, with original
  deployed API/transport unchanged and previous route objects preserved.
- Full original startup and additive startup rehearsed using the existing
  service configuration in a separate process; values neither printed nor saved.
- Python audit hook prohibited file mutations, network connects/binds and
  subprocess creation throughout imports and in-process HTTP checks.
- Original health200/prospect401/search404 and additive health200/prospect401/
  search401 all passed. Existing LinkedIn and Data Cloud guards executed.
- Exact rollback routine tested against isolated files/service doubles:
  removes only its own new override, leaves neighbor config intact, reloads,
  restores original entrypoint and requires health200/prospect401/search404.
  This is not a claim of a live rollback of the new candidate.

New publisher: proposals/activate_crm_search_additive_20261109.py
SHA256 e59d928f1177c6fdbaba3c8694a39243b4f8b236925f364f1f813177e0dcb342

It checks database body/ACLs/zero bindings, original hashes and candidate
hashes; rehearses the full chain before mutation and again from root-owned
candidate files; creates one new systemd override for this SAME CRM service.
On runtime smoke failure it removes that override and verifies original
service recovery. No DB writes or original source replacements. Explicit
apply flag includes rollback. NOT EXECUTED. Signed-founder acceptance and
genuine scope bindings remain outstanding after successful route installation.
