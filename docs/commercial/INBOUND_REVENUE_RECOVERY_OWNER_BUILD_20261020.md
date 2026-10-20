# Empire AI — Inbound Revenue Recovery Engine

**Owner:** inbound voice / commercial recovery integration
**Branch:** feature/inbound-revenue-recovery-20261020
**Scope:** Upgrade the existing EmpireOS Voice Lab, Conversation OS, CRM and Revenue Intelligence; do not replace Lead Smart, Predictive Revenue, or their existing owners.

## Product goal

Sell verified business outcomes, not merely an AI receptionist. Businesses should see: provider-proven missed calls, independently verified callbacks, calendar-confirmed appointments, and actually paid recovery. Neither an enquiry nor an appointment request is paid revenue.

## Components implemented in the feature branch

- empire_os/inbound_revenue_recovery.py — deterministic receptionist response policy, tenant profiles, deduplicated recovery ledger, verified outcome and payment attribution.
- empire_os/inbound_recovery_api.py — dedicated token-gated preview surface disabled unless an explicit environment flag is enabled.
- empire_os/hub.py — registers only the preview router; leaves existing Vonage live call routes untouched.
- scripts/review_inbound_revenue_recovery_20261020.py — offline JSONL replay, read-only aggregates and tenant filtering.
- supabase/migrations/20261020124500_inbound_revenue_recovery_prepared.sql — prepared migration for default-deny tenant profiles and events (not applied).
- tests/test_inbound_revenue_recovery.py — isolated tests for attribution, synthetic exclusions, idempotency, receptionist claims and preview security.

## Existing integration points

Current Voice Lab: /v1/voice-lab/vonage/answer and /vonage/event are primarily outbound B2B infrastructure, not a deployed multi-tenant receptionist. Preserve these while building an independent inbound number-to-tenant registry.

Existing CRM, predictive revenue, buyer intelligence, demand-calls, website and finance components remain owned by their respective teams. Future integrations should use explicit shared evidence contracts and no duplicated canonical tables.

## Demo, testing, and safety

To run focused tests from this worktree:

    PYTHONPATH=. /srv/empire_os/.venv/bin/python -B -m pytest -q tests/test_inbound_revenue_recovery.py tests/test_voice_gateway_api.py

To run replay against an authorized local JSONL file:

    PYTHONPATH=. /srv/empire_os/.venv/bin/python -B -m scripts.review_inbound_revenue_recovery_20261020 --events-jsonl /path/to/events.jsonl --tenant-id an-authorized-tenant --read-only

For a LOCAL test deployment only, enable EMPIRE_INBOUND_RECOVERY_PREVIEW_ENABLED and set a secret EMPIRE_INBOUND_RECOVERY_PREVIEW_TOKEN; send the header x-empire-preview-token to POST /v1/inbound-recovery/preview.

In production, keep the preview flag unset. No inbound telephony, external callback, message, booking, database mutation, live billing or payment action is performed by this candidate.

IMPORTANT: The verified flag in offline replay simulates receipts from an authorized adapter. It is not proof of signature verification. Real live adapters must validate the provider signature and ownership of the phone line, calendar item, invoice and tenant, then persist the evidence chain. Do not pass arbitrarily submitted JSON into commercial attribution.

## Delivery phases

**P0, implemented:** deterministic receptionist policy, AI disclosure, no invented appointment confirmation, emergency/human escalation, opt-out behaviour, scoped event ledger, strict receipt requirements, money deduplication, protected preview and read-only replay.

**P1, pending:** signed inbound Vonage adapter; inbound DID to tenant registry; duplicate/retry reconciliation; durable event persistence; business opening-hours logic; timezone and holiday handling; fallback to human transfers. Preserve the current Lead Smart production routing without change.

**P2, pending:** real customer callback consent workflow, verified calendar availability and booking adapter, human approval, permitted follow-up delivery and suppression propagation.

**P3, pending:** CRM opportunity linkage, first-touch/last-touch campaign source, verified payment receipt reconciler, cost and gross margin dashboard, audit evidence chain and owner-approved finance integration.

**P4, pending:** tenant provisioning and scripts, service-specific guardrails, FAQs and structured knowledge, security-scoped customer dashboard, accurate usage invoices, alerts and missed-opportunity SLA analytics.

**P5, pending:** legal/privacy and UK PECR/GDPR review, recording notices, retention and erasure, signed webhook penetration tests, throughput/latency tests, genuine consented pilot, founder release approval and production monitoring.

## Metrics and product differentiation

Missed calls are provider-confirmed terminal missed dispositions, not guesses. Recovered calls require a later independently verified callback connection or calendar booking linked to that same tenant and call. Confirmed bookings require calendar receipts, not AI promises. Paid recovery requires a verified payment receipt after the recovery evidence; financial value is never inferred from booking value.

Also monitor speed-to-answer, verified contact rate, booked rate, paid recovery by currency, AI/human transfer outcomes, provider uptime, callback SLA, customer churn, support effort, voice model cost and gross margin. All synthetic/demo traffic is excluded from financial claims.

For commercial testing, hypothetical packages of £299, £499 and £999+ a month can be compared with unit economics, support cost, call minutes and buyer feedback. No package is yet an approved advertised price.

## Non-negotiable ownership and launch gates

Do not change the existing live Lead Smart pilot, Voice Lab outbound authorization, buyer discovery, Predictive Revenue production sources, DemandCalls live route, public flagship site or payment authority through this branch.

Before production activation: prove signed event authenticity, tenant identity/isolation, data minimization, consent/notice handling, callback suppression, human fallback, calendar and payment verification, retention deletion, cost monitoring and a separately approved supervised pilot.
