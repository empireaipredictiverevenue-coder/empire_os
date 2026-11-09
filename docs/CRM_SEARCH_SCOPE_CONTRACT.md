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
The function sets row_security=off to raise if RLS would silently filter its
owner's read; this does not grant BYPASSRLS. Missing privileges remain errors.

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
