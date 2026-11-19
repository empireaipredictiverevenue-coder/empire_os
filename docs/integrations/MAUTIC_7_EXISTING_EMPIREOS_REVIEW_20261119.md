# EmpireOS / Mautic 7 — minimal integration audit and guarded handoff

**Date:** 2026-11-19
**Owner:** Existing EmpireOS Smart CRM / GTM owner; no new marketing authority
**Status:** ISOLATED_IMPLEMENTED_AND_TESTED; NOT MERGED; NOT DEPLOYED; NOT CONNECTED
**Branch:** feature/mautic-webhook-review-20261119
**Base:** bb1424657
**Source code:** empire_os/mautic_webhook_review.py
**Tests:** tests/test_mautic_webhook_review.py

## Findings recovered from existing EmpireOS

- Smart CRM already has tenant-scoped CRM journey preview, graph designer and segment distribution: empire_os/revenue_crm_journeys.py. It is local-design-only, no workflow persistence or execution.
- Canonical channel consent/suppression review is separate and explicitly fail-closed: empire_os/revenue_crm_channel_evidence.py.
- The existing outbound governor preserves founder approval and suppression gates: empire_os/outbound_governor.py. No replacement sender or database is authorised.
- Mautic was previously considered as an open-source reference, not approved as a wholesale replacement.

## External upstream review

- Official source: https://github.com/mautic/mautic (7.x upstream branch on 2026-11-19)
- Mautic 7 uses Symfony/PHP with a separate application/database; requires independent operational ownership.
- Current root composer.json declares GPL-3.0; **no Mautic source code is copied** into this adapter. Review licence obligations with counsel before distributing any forked or modified upstream code.
- API v2 is documented at /api/v2 per instance, with actual endpoints discoverable after authentication; no external API integration is assumed to be configured.
- Mautic documented webhooks use base64(HMAC-SHA256(raw HTTP body, webhook secret)) in Webhook-Signature.
- Relevant documented events:
  - mautic.form_on_submit — submission, including sensitive fields; never infer opt-in.
  - mautic.lead_channel_subscription_changed — contactability status, not canonical first-party consent.
  - mautic.email_on_open — low-confidence engagement, potentially bot/proxy generated.
- References:
  - https://devdocs.mautic.org/en/7.3/webhooks/getting_started.html
  - https://devdocs.mautic.org/en/7.3/webhooks/events/index.html
  - https://devdocs.mautic.org/en/7.3/webhooks/events/email_on_open.html
  - https://devdocs.mautic.org/en/7.3/webhooks/events/form_on_submit.html
  - https://devdocs.mautic.org/en/7.3/webhooks/events/lead_channel_subscription_changed.html
  - https://devdocs.mautic.org/en/7.0/rest_api/api_v2.html

## Implemented now

Pure-Python signed webhook review boundary:
1. Requires raw bytes, a per-integration server-held secret and a valid HMAC signature before decoding JSON.
2. Requires an authenticated **server-provided** tenant and canonical IDs from a trusted, server-side Mautic-contact→Smart-CRM-prospect binding map. Never creates identity joins from email, untrusted headers or payload assertions.
3. Rejects duplicate JSON keys, unsupported event types, bad IDs, oversized batches/bodies, malformed subscription transitions, and cross-tenant identities.
4. Projects three supported Mautic events into **review-only** signals; does not include names, email addresses, IPs, message content or form answers in output.
5. Does not equate "contactable", a form submission, or an email-open pixel with marketing consent, verified opportunity or revenue.
6. Emits a keyed evidence fingerprint suitable for future canonical idempotency checks, without claiming that replay prevention is already installed.
7. Does not create network listeners, send mail, change CRM or persist any data; it is opt-in Python code only.

## Verification

Executed on EmpireOS in the isolated worktree using the existing Python virtual environment:

    PYTHONDONTWRITEBYTECODE=1 /srv/empire_os/.venv/bin/python -B -m pytest -q -p no:cacheprovider tests/test_mautic_webhook_review.py tests/test_revenue_crm_journeys.py tests/test_revenue_crm_channel_evidence.py

**Observed:** 61 passed, 1 third-party Starlette/anyio deprecation warning; no external Mautic, real customer data, tenant tokens, DB write or network send.

## Commercial use and release boundary

This is **not**:
- A complete Mautic fork, installation, CRM sync, campaign execution engine, or production web endpoint.
- An identity resolution, email opt-in or suppression authority.
- A verified customer/revenue event.
- A functioning live buyer nurture campaign.

Any later connection must use the existing Smart CRM authorisation and GTM governor. Gate merging/release on: authenticated tenancy, immutable contact binding ownership, verified source consent and suppression receipts, replay dedupe persistence, inbound endpoint authentication/abuse limits, PII handling/retention, bounded queue/backoff, tests against a controlled real Mautic instance, and founder/owner approval.

## Decision on fork versus integration

**Choose a narrow event adapter first.** Do not clone a second Mautic customer database, sender or journey product into production. Evaluate a separately isolated upstream Mautic installation only if an observed customer journey requires complex branching/execution functionality that the current EmpireOS owner cannot deliver economically. Full-fork ownership is *not* authorised by this review.


## Follow-on delivery — 2026-11-19: guarded HTTP to Smart CRM preview

**Implementation:** empire_os/mautic_crm_integration.py
**Synthetic HTTP tests:** tests/test_mautic_crm_integration.py
**State:** ISOLATED_IMPLEMENTED_AND_TESTED_ONLY, NOT MOUNTED IN PRODUCTION.

A separately instantiated, opt-in FastAPI router now implements
POST /v1/revenue-crm/integrations/mautic/{source_id}/events/preview.
The handler uses a source-resolver callback whose tenant and signature secret
MUST come from server-held configuration, never body fields or tenant headers.
It validates Mautic's raw-body Webhook-Signature before resolving matching
Smart CRM prospects through a tenant-bound reader. Non-PostgreSQL readers
are refused unless a special synthetic-test flag is explicitly set.

For each verified event with an independently trusted bound contact:
- Resolve the existing CRM prospect and run preview_crm_journey.
- Return its observed segment and blockers, plus a review-only event category.
- Never treat form submission or Mautic contactable as opt-in, an email open
  as purchase, or a source status change as canonical suppression clearance.
- Never mutate the CRM, create subscribers, schedule work or send outreach.

**Durable replay staging:** SqliteMauticReceiptJournal writes only tenant ID,
source ID and a keyed event fingerprint, not raw source contact details.
It requires a private owner-controlled directory and 0600 file, rejects
insecure existing files, and uses an atomic BEGIN IMMEDIATE transaction
and uniqueness key to avoid duplicate admission across requests, threads and
journal reopening. It is for isolated evaluation ONLY; it is not an approved
replacement for an EmpireDB replay ledger or canonical event inbox.

**Critical outstanding delivery design:** The staging receipt store preserves
deduplication proofs, but not deliverable normalized CRM signal history.
The webhook returns a preview and Mautic will not use that response as a
customer-facing marketing journey. Do not register this webhook as a live
production listener until a canonical EmpireDB delivery/outbox owner has
provided a durable, tenant-scoped event inbox with independent readback and
acknowledgement semantics. Otherwise an acknowledged event could be lost.
The marketing journey designer is a separate design-only surface and no
server-driven journey execution has been authorised.

### Verified tests (synthetic fixture, not a real Mautic service)

The FastAPI TestClient test suite exercises signed HTTP delivery using Mautic's
documented event shapes, tenant-binding and suppression checks, and checks
that replay after reopening the journal yields zero new events. It includes
concurrent duplicate receipt admission, missing canonical prospects, and
privacy protections. No real data or sender is involved.

The relevant suite command is:

    PYTHONDONTWRITEBYTECODE=1 /srv/empire_os/.venv/bin/python -B -m pytest -q -p no:cacheprovider \
        tests/test_mautic_crm_integration.py tests/test_mautic_webhook_review.py \
        tests/test_revenue_crm_journeys.py tests/test_revenue_crm_channel_evidence.py \
        tests/test_revenue_crm_design_store.py tests/test_revenue_crm_journey_designer.py

One broad branch-based verification including tests/test_outbound_governor.py
returned **91 passed, 3 failed**. These three are baseline drift
on the isolated base commit: tests/test_outbound_governor.py in the currently
active, dirty /srv/empire_os checkout independently returned **11 passed**.
The Mautic branch does not edit the governor or those tests. No governor fix,
source cherry-pick or merge was authorised here. Reconcile owner work before
any merge and rerun all relevant tests on that final integration candidate.

### Conditions for a real Mautic-backed demonstration

1. Verify an isolated Mautic 7 test instance, version and API/webhook event
   payloads. No Mautic systemd service, Docker container name or repo config
   was located in the inspected EmpireOS environment.
2. Bind test contact IDs to existing, authenticated Smart CRM prospect IDs
   using the canonical identity owner, not email matching.
3. Confirm approved secrets, per-tenant dedicated CRM read login,
   source configuration, consent/suppression gates and webhook listener scope.
4. Add a DBA-reviewed EmpireDB canonical replay/event-inbox implementation
   and an auditable delivery handoff before acknowledging live events.
5. Demonstrate a full genuine form/consent to qualified CRM conversation
   to founder-reviewed follow-up to verified outcome, with sending disabled
   until separately authorised; track real qualified enquiries, not opens.
6. Repeat runtime and end-to-end tests, independent review and founder gate
   before merge/deployment; no webhooks, migrations, service restarts or
   outbound actions were enabled by this branch.

Mautic's developer webhook docs explicitly warn parts may be outdated.
Payload assumptions should be revalidated against the exact tested release.
Source: https://devdocs.mautic.org/en/7.3/webhooks/getting_started.html


## Canonical EmpireDB inbox candidate — 2026-11-19 (follow-on)

**Code:** empire_os/mautic_crm_inbox.py
**Tests:** tests/test_mautic_crm_inbox.py
**Prepared unnumbered SQL:** docs/integrations/sql/MAUTIC_CRM_EVENT_INBOX_PREPARED_ONLY_20261119.sql

Verified with the existing Smart CRM API:
- A dedicated per-tenant, NOINHERIT PostgreSQL writer session must be
  bound to exactly one trusted canonical tenant, checked through the same
  existing public.empire_current_tenant_id() authority.
- Normalized allowlisted review evidence, not Mautic raw body or contact
  data, is INSERT-only into a tenant/source/HMAC unique inbox.
- Source and event constraints, immutable review status, force-RLS and a
  separate committed readback prevent false acknowledgements.
- Unknown Mautic contacts are returned as 503 instead of 2xx in the
  **canonical inbox path**, so a producer can retry after binding is fixed.
- Normalized event stays REVIEW_ONLY. It does not alter CRM prospect stage,
  grant marketing consent, run the journey designer or send any message.
- SQLite is permitted only in a separate synthetic test harness; production
  route rejects it by default.

**Critical schema reconciliation:**
The isolated worktree was branched from bb1424657, which lists migrations
only through 075. The active EmpireOS tree already contains migrations
076–080 including 076_predictive_forecast_registry_native_held.sql.
Therefore no "076 Mautic" migration should be claimed or installed. The
prepared SQL was moved out of the sequenced migration folder and remains
**unnumbered, held for the canonical EmpireDB DBA/owner to allocate**.
This avoids an unauthorised migration-number clash with another owner.

**Upstream payload verification:**
The official Mautic 7.x branch contains
app/bundles/WebhookBundle/Http/Client.php (reviewed upstream SHA
e323d688a2cbc37f4ebcc9bd7d2f2042833bde24), which generates
base64(HMAC-SHA256(raw JSON, configured secret)), sends a
Webhook-Signature header, and declares application/json. In-process
HTTP contract tests exercise these exact properties. No Mautic source
was copied into EmpireOS.

**Real-instance status:** no Mautic systemd service, running Docker Mautic
container, or existing Mautic config was detected. The ubuntu login does
not have direct Docker daemon permissions; a privileged read-only Docker
query was blocked by the remote command policy. No Docker image was pulled,
no systemd unit changed, no container created and no instance installed.

**Remaining verification before release:**
- Canonical owner assigns an approved migration number and reviews existing
  role grants, RLS, DDL and rollback plan. SQL remains **not applied**.
- Provision dedicated source secret, per-tenant binding and DB writer
  using existing EmpireOS security/DBA procedures. No credentials in Git.
- Independently authenticate the ingestion principal/source; source IDs
  and webhook secrets must come from a secure registry; do not use
  headers or self-declared body tenant.
- Test the actual pinned Mautic instance's Test Payload and real
  subscription/form workflows, including redelivery after outage.
- Prove the durable inbox events reach a canonical founder-review screen
  and that any future journey steps remain approval-gated.
- Obtain founder release approval, then merge owner-reviewed branch and
  deploy with a reversible canary; measure genuine enquiries and sales.

**Execution and measurement truth:** isolated Python integration and
prepared DDL only. No verified live Mautic traffic, conversion, marketing
subscriber, buyer or sales event is claimed. No sending, payment, migrations,
deployments or background automation was started.


## Independent isolated PostgreSQL 18 runtime verification — 2026-11-19

This follow-on closed the gap between mocked PostgreSQL tests and an
actual database runtime. New independent fixture files:

- scripts/test_mautic_crm_pg_isolated.sh
- tests/fixtures/mautic_crm_pg_runtime_fixture.sql
- tests/test_mautic_crm_pg_runtime.py

The script explicitly refuses root execution, creates a disposable private
PostgreSQL 18 cluster under an isolated /tmp directory, and configures **no
TCP listener**. It uses only owner-private Unix sockets. The fixture creates
dummy roles, a trusted session_user-based tenant resolver, synthetic CRM rows
and a tenant CRM reader projection. The held inbox SQL is applied **only**
inside this disposable fixture and independently tested using actual
psycopg PostgreSQL connections from dedicated role logins.

The first fixture run failed because the operating environment's default
cluster locale could produce SQL_ASCII text decoding as bytes. The runner
now requires UTF8 and C.utf8, consistent with proper modern PostgreSQL
encoding. The runtime checks also exposed that the drafted schema's
GRANT USAGE ON SCHEMA public could be ineffective under a migration role
which does not own that schema. The held draft now requires schema USAGE
to be provisioned by its owner and confirms the required schema/table
privileges before transaction commit. This preserves the DBA authority gate.

**Verified result:** the isolation script passed 4 actual PostgreSQL
tests, including real RLS cross-tenant exclusion, INSERT-only writer
permissions, committed insert/readback, duplicate receipt handling,
real tenant-bound Smart CRM prospect read, and a signed HTTP webhook
accepted exactly once and persisted to the canonical fixture inbox.
Temporary PostgreSQL was stopped and test files removed by the script.
The in-process FastAPI tests use **synthetic Mautic-shaped HTTP requests**;
they are not claims of an installed/connected Mautic server.

**Upstream Mautic 7.x source compatibility correction:** Confirmed in
app/bundles/EmailBundle/EventListener/WebhookSubscriber.php that
mautic.email_on_open emits a nested stat object, NOT a top-level contact
record. The stat serializer declares a lead association in
app/bundles/EmailBundle/Entity/Stat.php. Updated the bounded adapter to
read stat.lead.id for email-open events and reject stat payloads with no
verified lead identity. Added privacy and signature regression tests.
The lead-channel subscription status labels were confirmed from
app/bundles/LeadBundle/Event/ChannelSubscriptionChange.php.
References are from upstream GitHub 7.x, SHA
e323d688a2cbc37f4ebcc9bd7d2f2042833bde24.

**Relevant suite:** 108 existing and Mautic-specific in-process tests
passed; 4 additional real PostgreSQL isolated integration tests passed.
Third-party HTTPX/Starlette deprecation warnings remain unrelated.

**Still not authorised/completed:** Real Mautic provisioning or delivery,
deployment, production registration of the FastAPI router, allocation of a
sequenced migration number, applying held SQL in EmpireDB, obtaining
canonical production source bindings/secret/reader/writer logins, webhook
queue health, workflow execution, outbound sends, sales, or any revenue
claim. Requires canonical DBA/Smart CRM owner review and founder release gate.


## Reconciled integration and test-environment preflight — 2026-11-19

**New integration branch:** integration/mautic-crm-active-20261119

The original four Mautic commits were cherry-picked, in order, onto
the newer immutable committed EmpireOS snapshot
9ac776b6506442aeb81927f2554f3fb12f4a0846.
This preserves the original isolated development branch and does not
modify the active dirty /srv/empire_os checkout. There were no source
merge conflicts.

**Verification against the newer committed base:**

- 141 Smart CRM, Mautic, tenant-security and transport tests passed.
- 4 tests against ephemeral real PostgreSQL 18 (no production DB) passed.
- The SQL remains unnumbered and prepared only.
- The committed snapshot does not include any simultaneously dirty
  changes in /srv/empire_os; owner comparison is necessary before merge.

**Actual Mautic runtime preflight:**

- Official Mautic Docker 7.2.2-20261026 Apache image tag confirmed
  on Docker Hub, with matching official Apache guidance.
- tests/mautic_sandbox/compose.yaml defines a manual-profile,
  loopback-port, internal-network, worker-free Mautic/MySQL fixture.
- scripts/preflight_mautic_contract_sandbox.py validates the Compose
  JSON, images, profiles, mounts, restart/no-worker and isolation gates.
- Docker Compose v5.7.1 configuration and isolation checks passed.
- Actual Docker daemon permission check failed for ubuntu:
  MAUTIC_RUNTIME_BLOCKED_DOCKER_DAEMON_ACCESS (exit 24).
- Connected Windows WSL launch also failed (CreateInstance/E_UNEXPECTED).
- LXD has no configured storage pool/default profile and was not used
  to alter host container infrastructure.

**No real Mautic container or test app was started.** Neither host
Docker permission escalation nor new paid cloud resources, host
service restarts, migrations, production deployments or outbound
sending was authorised or performed. The full signed webhook
producer-driven integration remains **NOT LIVE / NOT VERIFIED**.

**Needed release gate:** provide a dedicated approved sandbox
container runner (not blanket Docker socket privileges on EmpireOS),
then test actual pinned Mautic webhook payloads and delivery against
the signed adapter, reconcile current dirty owner changes, and only
then review production migration/application registration.
