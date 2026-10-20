# Empire AI — Inbound Revenue Recovery Engine

**Owner:** inbound voice / commercial recovery integration
**Branch:** feature/inbound-revenue-recovery-20261020
**Scope:** Upgrade the existing EmpireOS Voice Lab, Conversation OS, CRM and Revenue Intelligence; do not replace Lead Smart, Predictive Revenue, or their existing owners.

## Product goal

Sell verified business outcomes, not merely an AI receptionist. Businesses should see: provider-proven missed calls, independently verified callbacks, calendar-confirmed appointments, and actually paid recovery. Neither an enquiry nor an appointment request is paid revenue.

## Components implemented in the feature branch

- empire_os/inbound_revenue_recovery.py — deterministic receptionist response policy, tenant profiles, deduplicated recovery ledger, verified outcome and payment attribution.
- empire_os/inbound_recovery_api.py — dedicated token-gated preview surface disabled unless an explicit environment flag is enabled.
- empire_os/inbound_provider_contract.py — isolated number-to-tenant registry, explicit DID ownership and disabled/enabled routing contract, and status mapping requiring prior signed provider attestation.
- empire_os/inbound_signature_verification.py — Vonage Voice JWT HS256 verification with issuer/API key/application checks, payload SHA-256, freshness and JWT ID (no publicly exposed intake endpoint).
- empire_os/inbound_recovery_store.py — offline SQLite tenant-scoped persistence, signed callback JWT replay tracking, idempotent retry handling, and a genuinely read-only connection mode for reports.
- empire_os/inbound_recovery_scorecard.py — no-estimates recovery funnel and operational review actions based on valid evidence only.
- empire_os/inbound_business_hours.py — time-zone aware staffed windows, business-confirmed closures, after-hours fallback and DST-aware next opening.
- empire_os/hub.py — registers only the preview router; leaves existing Vonage live call routes untouched.
- scripts/review_inbound_revenue_recovery_20261020.py — offline JSONL or existing SQLite review, optional scorecard, tenant filtering and read-only enforcement.
- supabase/migrations/20261020124500_inbound_revenue_recovery_prepared.sql — prepared, unapplied schema for tenant profiles, evidence events and signed callback replay receipts; all tables default-deny RLS.
- tests/test_inbound_revenue_recovery.py, tests/test_inbound_provider_contract.py, tests/test_inbound_recovery_store.py, tests/test_inbound_recovery_scorecard.py and tests/test_inbound_business_hours.py — offline evidence, JWT auth/tamper/replay, durable attribution, opening-hours and preview safety tests.

## Existing integration points

Current Voice Lab: /v1/voice-lab/vonage/answer and /vonage/event are primarily outbound B2B infrastructure, not a deployed multi-tenant receptionist. Preserve these while building an independent inbound number-to-tenant registry.

Existing CRM, predictive revenue, buyer intelligence, demand-calls, website and finance components remain owned by their respective teams. Future integrations should use explicit shared evidence contracts and no duplicated canonical tables.

## Demo, testing, and safety

To run focused tests from this worktree:

    PYTHONPATH=. /srv/empire_os/.venv/bin/python -B -m pytest -q tests/test_inbound_business_hours.py tests/test_inbound_recovery_scorecard.py tests/test_inbound_recovery_store.py tests/test_inbound_provider_contract.py tests/test_inbound_revenue_recovery.py tests/test_voice_gateway_api.py

To run replay against an authorized local JSONL file:

    PYTHONPATH=. /srv/empire_os/.venv/bin/python -B -m scripts.review_inbound_revenue_recovery_20261020 --events-jsonl /path/to/events.jsonl --tenant-id an-authorized-tenant --scorecard --read-only

To inspect an already-created offline SQLite file without writing or creating it:

    PYTHONPATH=. /srv/empire_os/.venv/bin/python -B -m scripts.review_inbound_revenue_recovery_20261020 --sqlite-db /path/to/offline.db --tenant-id an-authorized-tenant --scorecard --read-only

For a LOCAL test deployment only, enable EMPIRE_INBOUND_RECOVERY_PREVIEW_ENABLED and set a secret EMPIRE_INBOUND_RECOVERY_PREVIEW_TOKEN; send the header x-empire-preview-token to POST /v1/inbound-recovery/preview.

In production, keep the preview flag unset. No inbound telephony, external callback, message, booking, database mutation, live billing or payment action is performed by this candidate.

IMPORTANT: The offline JSONL verified flag simulates receipts from trusted adapters; it is not evidence of real calendar or payment-provider verification. The **standalone** Vonage verifier authenticates JWT HS256 + body hash, but there is no registered live webhook or real provider key. The SQLite signed-intake function is local/offline, not a deployed callback endpoint. Real live adapters must configure verified phone ownership and persist event proof under scoped DB authority, verify calendar and payment claims independently, and enforce legal/privacy safeguards before launch.

## Delivery phases

**P0, implemented:** deterministic receptionist policy, AI disclosure, no invented appointment confirmation, emergency/human escalation, opt-out behaviour, scoped event ledger, strict receipt requirements, money deduplication, protected preview and read-only replay.

**P1, partially implemented in offline form:** inbound DID/tenant mapping, canonical Vonage status normalization, signed JWT/payload verification, durable offline callback-replay storage, read-only reporting, verified-hours calculation, closure dates, and after-hours human-follow-up preview. Still pending: production signed webhook endpoint, real owner-verified number registry, Supabase persistence and authorization, customer-approved staffing schedules, operational SMS/callback transfer, authorized production deployment, supervised proof and monitoring. Preserve the current Lead Smart production routing without change.

**P2, pending:** real customer callback consent workflow, verified calendar availability and booking adapter, human approval, permitted follow-up delivery and suppression propagation.

**P3, pending:** CRM opportunity linkage, first-touch/last-touch campaign source, verified payment receipt reconciler, cost and gross margin dashboard, audit evidence chain and owner-approved finance integration.

**P4, partially prepared:** read-only offline scorecard and hours-aware preview are implemented. Pending: actual tenant provisioning, client-specific scripts, FAQs and structured knowledge, secure authenticated customer dashboard, usage invoices, operational alerts and missed-opportunity SLA analytics.

**P5, pending:** legal/privacy and UK PECR/GDPR review, recording notices, retention and erasure, signed webhook penetration tests, throughput/latency tests, genuine consented pilot, founder release approval and production monitoring.

## Metrics and product differentiation

Missed calls are provider-confirmed terminal missed dispositions, not guesses. Recovered calls require a later independently verified callback connection or calendar booking linked to that same tenant and call. Confirmed bookings require calendar receipts, not AI promises. Paid recovery requires a verified payment receipt after the recovery evidence; financial value is never inferred from booking value.

Also monitor speed-to-answer, verified contact rate, booked rate, paid recovery by currency, AI/human transfer outcomes, provider uptime, callback SLA, customer churn, support effort, voice model cost and gross margin. All synthetic/demo traffic is excluded from financial claims.

For commercial testing, hypothetical packages of £299, £499 and £999+ a month can be compared with unit economics, support cost, call minutes and buyer feedback. No package is yet an approved advertised price.

## Non-negotiable ownership and launch gates

Do not change the existing live Lead Smart pilot, Voice Lab outbound authorization, buyer discovery, Predictive Revenue production sources, DemandCalls live route, public flagship site or payment authority through this branch.

Before production activation: prove signed event authenticity, tenant identity/isolation, data minimization, consent/notice handling, callback suppression, human fallback, calendar and payment verification, retention deletion, cost monitoring and a separately approved supervised pilot.


## 20 October — Opportunity Intelligence and Source Attribution extension

**Milestone status:** Implemented as an **offline, read-only commercial intelligence layer**. No production customer contact, billing, campaigns or telecom routing has been enabled.

### New code
- empire_os/inbound_opportunity_intelligence.py: evidenced missed-call queue; configurable callback/booking/general response SLAs, deterministic urgency explanations, opt-out exclusion, protected tenant filtering, verified human intent signal handling, no customer outreach authority.
- empire_os/inbound_source_attribution.py: canonical call-linked, verified first/last acquisition touch; source categories include organic, paid search, social, marketplaces and referrals. Actual payment receipts are included only after independently verified recovery; receipt deduplication is global within the tenant report. Unknown sources remain unattributed.
- empire_os/inbound_recovery_patterns.py: verified provider call outcome distribution by weekday and local daypart. Configured minimum cohort and segment thresholds prevent unreliable alerts. Contradictory call dispositions are excluded; no money, ROI or causal prediction is fabricated.
- empire_os/inbound_recovery_store.py: safe tenant-scoped event retrieval for existing SQLite review.
- scripts/review_inbound_revenue_recovery_20261020.py: operator review modes for priorities, source attribution and pattern analysis, alongside earlier scorecard.

### Operational interface

All commands run from the isolated worktree using the project's Python environment, without provider/network writes.

Read prioritised, unresolved work from an existing local evidence database:

    PYTHONPATH=. /srv/empire_os/.venv/bin/python -B -m scripts.review_inbound_revenue_recovery_20261020 --sqlite-db /path/to/existing-evidence.db --tenant-id TENANT --read-only --opportunities --as-of 2026-10-20T13:00:00+01:00

Inspect first-party source linkage; unknown is a valid result rather than an invented channel:

    PYTHONPATH=. /srv/empire_os/.venv/bin/python -B -m scripts.review_inbound_revenue_recovery_20261020 --sqlite-db /path/to/existing-evidence.db --tenant-id TENANT --read-only --source-attribution --as-of 2026-10-20T13:00:00+01:00

Review enough events for repeated missed demand patterns using a named business timezone:

    PYTHONPATH=. /srv/empire_os/.venv/bin/python -B -m scripts.review_inbound_revenue_recovery_20261020 --sqlite-db /path/to/existing-evidence.db --tenant-id TENANT --read-only --patterns --timezone Europe/London --as-of 2026-10-20T13:00:00+01:00

With --events-jsonl, local fixtures can be read without database access. --signals-jsonl is allowed only in opportunity mode and --source-touches-jsonl only in source-attribution mode. These are test/review assertions, not trusted live data capture or provider-authenticated source-linking.

### Commercial intelligence safeguards

- Never treat several provider call IDs as several unique people unless identity is independently verified.
- Only real, verified provider-missed statuses create actionable internal tickets. Agent/model signals alone cannot escalate verified urgency. Human attestation is required and should eventually be tied to immutable reviewer audits.
- Ticket prioritisation is rules-based, not a predictive buyer or expected-revenue score. All operator recommendations are review-only; explicit consent/suppression verification remains a prerequisite for any subsequent contact.
- For source tracking, do not infer a paid click or organic source from message content. Provider/partner-backed call-tracking joins are required; revenue is limited to verified received-payment receipts after independently confirmed recovery.
- Insufficient history yields no staffing patterns. The analysis highlights observed pressure on a business, not a statistically calibrated revenue estimate or causal proof.
- Production integration still requires provider-signed intake, owner-authenticated tenants, durable provenance, customer-approved business-hours settings, consent and opt-out enforcement, true CRM/calendar/finance reconciliation and a supervised release.

## 20 October — Protected Tenant Management API and Membership Contract

Implementation branch: feature/inbound-revenue-recovery-20261020
Status: Built and tested locally; NOT deployed, NOT production-authenticated, and NOT an operating customer portal.

### Added modules

- empire_os/inbound_tenant_directory.py: durable local tenant profiles, timezone, category, review approval and suspension; no public write endpoints.
- empire_os/inbound_management_auth.py: issuer/audience-scoped HS256 authentication, short-lived tokens (maximum 15 minutes), required subject, tenant, JWT ID, expiry and permission scopes. No self-service issuance.
- empire_os/inbound_access_audit.py: HMAC-chained local access log with pseudonymous actors. Existing chain tampering blocks subsequent authorised reads. Tamper-evident, NOT immutable against a privileged administrator controlling both key and DB.
- empire_os/inbound_management_api.py: default-disabled GET profile, scorecard, opportunities and patterns, with tenant derived only from a bearer claim; explicit approved-tenant directory; read-only evidence database; separate mandatory audit logging and fail-closed dependencies.
- empire_os/hub.py: registers the protected management router without touching provider voice routes.
- supabase/migrations/20261020124501_inbound_recovery_tenant_access_prepared_20261020.sql: UNAPPLIED migration created by Supabase CLI and ordered after the earlier core recovery schema; adds auth.users-backed tenant memberships, member-only read policies and server-only audit table, while protecting raw provider/payment evidence.

### Local operation

This is a development adapter, NOT a substitute for production identity, membership provisioning, signing key rotation or revocation. Real customer onboarding must reconcile with the existing approved identity system; no module here issues tokens to a client. Do not use short-lived HMAC test tokens as customer credentials.

The API is OFF by default. A private test environment requires:
- EMPIRE_INBOUND_MANAGER_ENABLED=true (do not activate in production)
- EMPIRE_INBOUND_MANAGER_JWT_KEY (server-only 32+ byte key)
- EMPIRE_INBOUND_MANAGER_AUDIT_KEY (separate server-only 32+ byte key)
- EMPIRE_INBOUND_MANAGER_TENANT_DB (absolute existing local directory file)
- EMPIRE_INBOUND_MANAGER_EVIDENCE_DB (absolute existing offline evidence file)
- EMPIRE_INBOUND_MANAGER_AUDIT_DB (absolute server-owned path under an existing private directory)

Public response codes: 404 when disabled, 401 for invalid/scopeless tokens, 403 for unapproved tenant access, 503 for untrusted storage or audit. A manager GET writes only to the separate access audit database, never to the read-only evidence database. It returns Cache-Control: no-store. No user-supplied path or tenant override is accepted.

Reporting approval does not authorise making calls, sending messages, booking appointments, collecting live revenue or altering telecom routing.

### Prepared database release gates

The new membership SQL is NOT applied. Static security tests do not substitute for actual PostgreSQL RLS tests, migration verification or Supabase advisors. Before any production release:
1. Confirm ordered migrations and current database schema in the selected project.
2. Test authenticated reads for active members, revoked members, unrelated tenants and unauthenticated roles.
3. Verify no browser credential can write memberships, call evidence, signed provider receipts or audit logs.
4. Run security and performance advisors and isolated Postgres migration tests.
5. Integrate existing user identity and strict session/revocation workflow; use auth.uid() with server-issued memberships rather than user-editable metadata.
6. Verify key rotation, owner review, access monitoring and audit integrity.
7. Add retention, deletion, encryption and backup controls.
8. Complete GDPR, PECR, recording notice and cross-jurisdictional legal review before live call processing.

All commercial execution remains OFF, all backend provider and customer integrations remain unactivated, and no recovered revenue has been claimed.


## 20 October — Versioned Tenant Knowledge & Verified Answering

**Status:** Implemented offline; preview and read-only manager status connected. NOT deployed to production voice, customer administration or automatic learning.

### Implementation

- empire_os/inbound_tenant_knowledge.py: immutable-in-Python FAQ fact and pack contracts with tenant ownership, reviewer/source evidence, approval state, 180-day maximum review window, expiration and deterministic lexical matching. Never treats match coverage as a probability or AI accuracy measure.
- empire_os/inbound_knowledge_store.py: local SQLite version store for draft packs with explicit second-stage operator activation; activation requires all facts approved, non-synthetic, reviewed and unexpired. Customer-specific active-version pointer and old versions preserved. SQL file integrity hashing detects accidental/casual changes; it is NOT a cryptographic signature against a privileged adversary able to rewrite both data and hashes.
- empire_os/inbound_recovery_api.py: existing protected preview optionally accepts a simulated versioned FAQ pack, labels all operator-supplied knowledge as simulation and does not let FAQ override emergency or opt-out behavior.
- empire_os/inbound_management_api.py: GET knowledge-status requires the distinct recovery:knowledge scope, active tenant approval and audit chain; returns only counts/version/status, not arbitrary call content or raw answers.
- scripts/review_inbound_knowledge_20261020.py: read-only offline answer replay for an existing local knowledge store and specific tenant.

Example offline knowledge review (existing store only):

    PYTHONPATH=. /srv/empire_os/.venv/bin/python -B -m scripts.review_inbound_knowledge_20261020 --knowledge-db /path/to/local-knowledge.db --tenant-id TENANT --question "Do you install solar panels" --as-of 2026-10-20T13:00:00+01:00 --read-only

### Conservative answering rules

- General or service facts must be tenant-scoped, approved, current, non-synthetic for ordinary answers, and traceable to a recorded source.
- Contradictory equally matching facts cause an explicit abstention. Unknown questions cause refusal to invent an answer.
- Commercially sensitive topics (pricing, payment, refund decisions, availability, booking confirmation, regulated advice) are never completed by this static FAQ path, even if a fact is wrongly labelled as a general answer but contains obvious money/availability language.
- The sensitive-text guard is a conservative deterministic keyword/amount heuristic; it does not replace semantic QA, legal review, regulated-policy review, or execution gates.
- No model self-training, unapproved content rewriting, finance transaction, appointment booking, outbound campaign or human-contact authorisation is introduced.

### Release gates

Before any live knowledge use: customer permission to use the source, secure user-to-tenant provisioning, approved fact signer/reviewer identity, robust version approval and rollback, valid signed content provenance, tested semantic safety, locale-specific commercial disclaimers, data retention and explicit founder pilot approval.

The management knowledge database path is an optional extra server-side value EMPIRE_INBOUND_MANAGER_KNOWLEDGE_DB, required only for GET knowledge-status when the management API is enabled. It must refer to a private, existing offline SQLite file. No endpoint accepts a caller-supplied file path.

## 20 October — Appointment Lifecycle, Callback Consent, Suppression and Cancellation Reconciliation

Status: Built and tested offline. No production migration applied, no customer messages/calls, no calendar bookings made, and no verified revenues newly observed.

### New modules

- empire_os/inbound_booking_workflow.py: tenant-scoped appointment and callback lifecycle. Appointment request, calendar-confirmed status, cancellation/reconfirmation, verified callback connection, explicit consent grant/revocation and global opt-out. Opt-outs remain effective beyond normal operational lookback. Competing contact identifiers block review eligibility. Conflicting booking ownership is quarantined.
- empire_os/inbound_contact_identity.py: tenant-specific HMAC-SHA256 of E.164 phone, not a plaintext number. THIS IS PSEUDONYMISATION, NOT ANONYMISATION; private signing key and privacy review are essential.
- empire_os/inbound_booking_store.py: offline SQLite, idempotent event persistence, separate tenant read-only reports. SHA-256 detects naive corruption, not privileged tampering.
- empire_os/inbound_management_api.py: GET /v1/inbound-recovery/management/workflow; separate recovery:workflow scope, tenant approval, tamper-evident audit record, existing read-only workflow database and never any contact or booking authority. Server-side configuration EMPIRE_INBOUND_MANAGER_WORKFLOW_DB must be an existing absolute private SQLite file path.
- scripts/review_inbound_booking_workflow_20261020.py: read-only tenant and time-scoped command.
- supabase/migrations/20261020124502_inbound_booking_workflow_prepared_20261020.sql: CLI-created and version-ordered PREPARED database storage for workflow evidence and persistent tenant/contact suppression. FORCE RLS plus revoked browser roles; NO policy, provider webhook, trigger or live database change.

### Important cross-engine consistency fix

The canonical RecoveryEvent now supports booking_cancelled with calendar-origin evidence. The RecoveryLedger, opportunity queue and verified channel attribution use the latest calendar booking status rather than crediting previously confirmed appointments that have been cancelled. A cancellation can reopen a missed-call opportunity, and a payment does not become recovered revenue without an independently verified recovery path.

Canonical linkage convention: for an original opportunity, booking_confirmed and booking_cancelled must carry the same verified calendar appointment identifier as evidence_ref and the original call_id. The dedicated workflow records carry appointment_id and calendar_ref explicitly, and quarantine competing call ownership. This convention must be enforced by a genuine trusted calendar adapter in production.

### Safe offline review

    cd /home/ubuntu/empire_worktrees/inbound_revenue_recovery_20261020
    PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
      -m scripts.review_inbound_booking_workflow_20261020 \
      --workflow-db /path/to/existing_workflow.db --tenant-id AUTHORIZED_TENANT \
      --as-of 2026-10-20T13:00:00+01:00 --read-only

No public endpoint ingests workflow claims. verified=True in offline fixtures is NOT independent proof of a booking, caller consent or connected call. Production adapters must authenticate provider read-back, ownership, canonical IDs, replay, consent and cancellations. Current authorization makes records eligible for INTERNAL OPERATOR REVIEW ONLY; it does NOT permit calls, messages, purchases or bookings.

### Release gates

1. Verify real customer-owned calendar accounts, current availability, booking status and cancellation via authenticated provider read-back; never rely on AI assertions.
2. Connect purpose-limited caller consent and the canonical suppression system, with explicit legal and channel gates before any external contact.
3. Validate prepared schema in isolated Postgres with real RLS simulations and Supabase security advisors before applying.
4. Implement operator-approved scheduling, cancellations/no-show/reschedule reconciliations and provider retry handling.
5. Verify provider/webhook authenticity, tenant boundaries, key rotation, deletion/retention, cost monitoring and UK GDPR/PECR obligations before an explicitly approved supervised pilot.

No live calendar, messages, campaigns, customer-facing number routing or spending has been enabled.


## 20 October — Google Calendar Authenticated Read-Back Adapter (Development)

**Branch:** feature/inbound-revenue-recovery-20261020.
**State:** provider-compatible read-only integration CODE, mock-transport tests, private offline registry, management reporting, and unapplied schema. No real customer OAuth credentials, tenant calendar permissions, external API calls, live bookings, or production launch.

### Built

- empire_os/inbound_google_calendar_adapter.py: Google Calendar v3 events.get and freeBusy query allowlisted HTTP transport. Only read-only event GET and POST freeBusy are supported; no event insert, update, delete or send. Requests target a fixed Google host, redirect handling is disabled, timeouts and response size are bounded. Token lifecycle is deliberately left to an authorised credentials adapter.
- Backend-only ApprovedCalendarBinding and TrackedCalendarAppointment require exact tenant, calendar, event, call and approved source refs, with tenant-specific pseudonymous contact keys. These must originate in independent onboarding and verified calendar ownership; they are NOT publicly supplied.
- Booking read-back confirms Google event status, ID, calendar-private tenant/call/source metadata, timed start/end, opaque busy event and an updated provider revision. No other Google event can be counted simply because it exists on a connected calendar.
- Sparse cancelled event read-back is valid only when a previously verified identical appointment proof exists. Latest status, stale revision and cancellation/reconfirmation chronology guard against resurrecting an old booking.
- Proofs project into both RecoveryEvent and InboundWorkflowEvent using one canonical calendar-scoped booking reference. The existing recovery ledger and workflow summary then process confirmed, cancelled and newly reconfirmed states consistently. No revenue is inferred and payment still requires separate verified financial evidence.
- FreeBusy is independently verified for exact approved calendar, valid provider response, no calendar-level errors and bounded time interval. No calendar busy interval is not a bookable slot; available_slot_confirmed and booking_confirmed stay false.
- empire_os/inbound_calendar_registry.py: private offline SQLite owner/tenant registry, appointment mapping and read-back history, idempotent same-provider-revision reconciliation and tenant-scoped aggregate summary. This stores NO Google OAuth credentials.
- GET /v1/inbound-recovery/management/calendar-summary: default-off, recovery:calendar scope, approved tenant, mandatory audit and existing read-only local calendar database. Optional private env EMPIRE_INBOUND_MANAGER_CALENDAR_DB required for that endpoint.
- scripts/review_inbound_calendar_20261020.py: tenant-scoped read-only summary from an existing offline calendar registry.
- supabase/migrations/20261020124503_inbound_calendar_registry_prepared_20261020.sql: PREPARED, UNAPPLIED migration for owner-approved bindings, tracked appointment references and read-back records. FORCE RLS and direct client grants revoked.

### Source contract

Google Calendar Events.get:
https://developers.google.com/workspace/calendar/api/v3/reference/events/get

Google Calendar Freebusy.query:
https://developers.google.com/workspace/calendar/api/v3/reference/freebusy/query

Google Calendar Events resource status and extendedProperties.private:
https://developers.google.com/workspace/calendar/api/v3/reference/events

### Safe local review

    cd /home/ubuntu/empire_worktrees/inbound_revenue_recovery_20261020
    PYTHONPATH=. /srv/empire_os/.venv/bin/python -B -m scripts.review_inbound_calendar_20261020 --calendar-db /path/to/existing_calendar_registry.db --tenant-id AUTHORIZED_TENANT --read-only

### Production gates

1. Operator-approved Google OAuth onboarding of an actual customer-owned calendar with appropriate read-only/freebusy scopes, revocation, explicit calendar ACL verification, secure token storage and refresh. Do not use unrelated personal calendars or account tokens.
2. Trusted creation and immutable source linkage of Empire private event markers from a verified appointment-creation workflow. The current adapter will REFUSE unmarked events; this is deliberate.
3. Legitimate, explicit customer authorization for new calendar event writes and confirmation messages requires a distinct separately gated module; do not silently grant these rights to the read-only adapter.
4. Securely persist canonical proof events into the approved production evidence pipeline with transactional or idempotent cross-store reconciliation, provider retry tests and status-change monitoring.
5. Apply only after isolated PostgreSQL migration/RLS checks and coordinated production identity, privacy, retention and audit signoff.

The optional HTTP client has NOT been exercised against a live tenant calendar. Passing mocked provider tests is not a successful live calendar connection.

## 20 October — Google OAuth Read-Only Onboarding and Durable Calendar Evidence Projection

Status: isolated feature branch with offline fixtures. NO customer OAuth grant, account tokens, real calendar queries or production deployment. The OAuth callback handler, trusted token exchange/vault, database RLS integration and real-time monitoring are NOT live.

### Implemented

- empire_os/inbound_calendar_oauth_onboarding.py — ten-minute, one-time Google OAuth state and S256 PKCE challenge. Owner/tenant/admin/client/HTTPS callback binding; Calendar events.readonly and freebusy scopes only. PKCE verifier encrypted with a server-only Fernet key and cleared on successful one-time callback. Authorization codes are not persisted. This module does NOT exchange codes, issue tokens, or expose public callback routes.
- empire_os/inbound_calendar_oauth_boundary.py — read-only lease contract requiring exact account/tenant/calendar matching, restricted Google Calendar read-only scopes, approved owner, independently verified grant and unexpired access. Write-capable or unknown Google scopes are rejected before the provider transport is invoked. A self-declared boolean flag is NOT authoritative proof of provider permissions.
- empire_os/inbound_calendar_projection.py — operator-driven at-least-once calendar status projection into two independent local SQLite evidence stores. Both writes are idempotent, and the durable projection entry is acknowledged only after both succeed. If the second store fails, the first is retried safely without a duplicate event. This is NOT a distributed atomic transaction. The operator/customer reporting layer must label pending projections and never claim complete reconciliation when evidence delivery is unfinished.
- empire_os/inbound_calendar_registry.py — pending projection entries created transactionally with read-back proof. Tenant-scoped backlog and acknowledgment operations. SHA-256 corruption detection. Mixed UTC offset history is sorted chronologically.
- scripts/review_inbound_calendar_projection_20261020.py — read-only backlog inspection and an explicit opt-in LOCAL SQLite replay mode. No remote Google, telephone, customer messaging, payment or calendar changes.
- supabase/migrations/20261020124503_inbound_calendar_registry_prepared_20261020.sql — UNAPPLIED prepared server-only projection table with pending/complete tracking, tenant-bound foreign keys and FORCE RLS. No migration has been applied.

### Offline operator review

Read an EXISTING local calendar registry:
    PYTHONPATH=. /srv/empire_os/.venv/bin/python -B -m scripts.review_inbound_calendar_projection_20261020 --calendar-db /path/to/existing_calendar.db --tenant-id TENANT --read-only

Explicitly replay a verified LOCAL fixture, never a production dataset, into three distinct existing databases:
    PYTHONPATH=. /srv/empire_os/.venv/bin/python -B -m scripts.review_inbound_calendar_projection_20261020 --calendar-db /path/to/calendar.db --recovery-db /path/to/recovery.db --workflow-db /path/to/workflow.db --tenant-id TENANT --as-of 2026-10-20T13:00:00+01:00 --apply-local-evidence-replay

No fixture or claimed verified flag proves real recovered revenue. The local projection still has no production-backed provider credential authority.

### Next production release gates

1. Configure Google Cloud OAuth client and registered HTTPS callback; complete required consent-screen verification. Authorize only actual customer-owned calendars via existing EmpireOS tenant-admin identity.
2. Add server-owned OAuth code exchange, independently verified granted scopes, encrypted revocable token vault, refresh/revoke lifecycle and customer tenant binding. Never store bearer or refresh tokens in Git, SQLite calendar registry, logs or browser code.
3. Perform real authenticated, read-only Google event.get/freeBusy readbacks and verify appointment private source markers and tenant ownership. Free/busy never confirms availability or creates a booking.
4. Add a production-grade single-DB transactional outbox, idempotent reconciliation worker, retries/backoff, audit, source signatures, live authorization and PostgreSQL/RLS tests.
5. Perform customer consent, GDPR/PECR, retention, deletion, provider security and identity review before the supervised customer pilot. Live booking creation, calls, messaging and spending remain OFF.

Official contracts:
https://developers.google.com/workspace/calendar/api/auth
https://developers.google.com/identity/protocols/oauth2/web-server
https://developers.google.com/workspace/calendar/api/v3/reference/events/get
https://developers.google.com/workspace/calendar/api/v3/reference/freebusy/query
