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
