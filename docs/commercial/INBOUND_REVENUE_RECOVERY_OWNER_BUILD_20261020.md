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
