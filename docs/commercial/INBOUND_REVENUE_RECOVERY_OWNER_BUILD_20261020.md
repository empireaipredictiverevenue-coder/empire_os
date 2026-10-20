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
