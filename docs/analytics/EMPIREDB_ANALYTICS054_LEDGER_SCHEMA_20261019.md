# EmpireDB Analytics054 — staged first-party consent + event ledger

19 October 2026 | Founder Analytics next wave | **NOT DEPLOYED**

## Existing owner and purpose
This is additive to canonical **EmpireDB PostgreSQL**, NOT Supabase,
a new analytics database, a replacement CRM or a live website collector.
It consumes the already staged:
- offline first-party event validation contract;
- dormant local-only FastAPI HTTP harness;
- consent/revocation and server-side acquisition simulation;
- Tag Intelligence static-page source audit;
- active branded /department Founder Console with GSC metrics.

The user's objective is actual website sessions, engagement, sources,
funnels and verified lead/revenue attribution. Those cannot be derived
from GSC clicks or a simulator. **Unknown remains Not connected.**

## Built, source only (new migration 054)

File: migrations/empiredb/054_first_party_analytics_ledger_held.sql

This migration is held behind the EXISTING founder DB activation gate.
It must never be automatically run on service boot or ordinary deploy.

Creates exactly 3 NEW, tenant/property-scoped tables:
1. public.empire_analytics_sessions — HMAC digest reference (no plaintext
   cookie/session token), tenant UUID, exact empire-ai.co.uk property,
   server-classified acquisition source + evidence category, policy
   revision and a maximum 30-minute lifetime.
2. public.empire_analytics_consent_decisions — APPEND-ONLY revisioned,
   purpose-specific grant/deny/revoke, policy revision, evidence digest
   and database-issued recorded timestamp. No raw consent web form.
3. public.empire_analytics_event_receipts — APPEND-ONLY, tenant/property
   scoped 64-hex digest with unique key (cross-request replay protected),
   only page_view/engagement/cta_click/form_start/form_submit_attempt
   and a short opaque page key, bounded timestamp and database issued
   received timestamp. No browser URL query strings, IP, email,
   user agent, device fingerprint, form bodies, revenue or payment.

Database-level gates:
- Exact database name empiredb (or isolated empire_analytics_fixture)
  and verified NOLOGIN/NO SUPERUSER migrator role.
- Owner-enforced RLS and FORCE RLS on all three tables; ZERO tenant
  access policies and ZERO application LOGIN/role GRANTS in this wave.
- Append-only mutation triggers prohibit UPDATE and DELETE.
- Consent trigger serializes with a lock on the parent session row:
  revision must advance sequentially, grant is never silently repeated,
  terminal revoke cannot be superseded by a later grant.
- Event trigger locks the session row and inspects the latest durable
  consent decision on every insert, requires an active, unexpired
  session, and rejects any event that occurred BEFORE the last grant.
  Thus a previously unconsented browser event cannot be inserted
  after consent is later given.
- Unique (tenant_id,property_key,event_digest) rejects duplicate event
  receipts across separate transactions/requests.
- Foreign keys force matching tenant/property/session attribution.
- Current database timestamp overwrites caller values for decision
  recorded_at and event received_at.
- No unrestricted data reader, automatic callback or public RPC.

This still does NOT prove legal consent. Future session issuer/ledger
writer must authenticate CMP decisions; the fixed evidence_class
string and hash alone can never serve as independent proof. The
schema is strictly held pending that authority.

## REAL isolated database testing (not mocks)

Automated PostgreSQL 18 fixture:
tests/analytics/test_analytics_ledger_pg18_20261019.py

Each run boots a fresh PostgreSQL 18 cluster under a temporary local
directory with listen_addresses='' and a PRIVATE UNIX SOCKET. It creates
only a temporary database 'empire_analytics_fixture' and NO production
connections; the cluster is stopped and deleted at test completion.

Coverage:
- Actual SQL migration executes, exact 3 tables, forced RLS, no policies.
- Unprivileged role cannot read sessions, consent or events.
- Denied/missing consent prevents insertion. Server-side grant permits
  event receipts; revoke immediately stops any subsequent receipts.
- Sequential revision and terminal revoke cannot be bypassed.
- Cross-tenant FK and cross-request unique event digests enforced.
- Browser purchase/revenue values and raw/PII-bearing paths rejected.
- Updates/deletes rejected.
- Backdated pre-consent events rejected, forged timestamps overwritten.
- Concurrent consent revisions cannot fork.
- Re-run migration and wrong target DB fail closed.

## How to verify safely now

    cd /srv/empire_os
    ./.venv/bin/python -m scripts.review_analytics_ledger_schema_20261019 --read-only
    ./.venv/bin/python -m pytest -q tests/analytics/test_analytics_ledger_pg18_20261019.py tests/analytics/test_analytics_ledger_schema_preflight_20261019.py

The reviewer checks an exact pinned SHA256 of the staged SQL, without
connecting to ANY DB, and must report:
ANALYTICS054_SCHEMA_STAGED_FOUNDER_DB_APPROVAL_REQUIRED.

## Remaining before ANY production migration or tracking

1. Separate explicit founder DBA approval for the exact schema SQL;
   verify live EmpireDB migrator ownership, object collision and full
   restore/rollback plan before applying.
2. Approve retention and erasure authority. Tables are append-only
   in this proposal; that is a data-governance blocker for personal-
   data processing unless a separate controlled retention/erasure
   procedure is designed/tested before live collection.
3. Independently validate website-consent UI and actual grant/revoke
   proof, privacy/legal basis, region policies and policy version
   with ASTRA as flagship website owner. Existing prospect email
   opt-ins are NOT analytics consent.
4. Build a dedicated purpose-bound server issuer, HMAC digest/key
   rotation, secure tenant authority and source-classification receipts.
   DO NOT treat offline nonce or caller 'approved' boolean as genuine.
5. Introduce a dedicated restricted LOGIN under a separate founder-
   approved activation for auditable inserts and retention operations,
   using canonical EmpireDB tenant bindings, RLS tests and role ACLs.
6. Connect an explicitly approved public website event sender and
   gateway; apply bot/noise filters, replays, consent opt-out, sampling
   and throttling. Verify actual receipt from first consenting user.
7. Add real aggregated user/session/channel/cohort reports only after
   source observation and consent authority are proven. Join CRM and
   on-chain payments only using verified canonical identifiers/receipts.
8. Confirm no 053/other-agent schema chain conflict before DBA action:
   numbering 054 is a proposed additive source migration, not
   evidence that any preceding migration has been deployed.

**Current status:** staged source validated in isolation, no production
DB writes, no service restart, no public page changes, £0 spend,
no visitor/session counts and no new analytics cookies.
