---
name: empire-ai-receptionist-revenue-recovery
description: Reuse and finish the existing Empire AI AI-receptionist, missed-call intelligence, consented appointment/callback enquiry, tenant CRM handoff, Calendar and recovered-revenue evidence pipeline. Trigger when working on AI receptionist, phone answering, missed revenue, revenue leakage, recovered calls, or inbound customer conversions. Never rebuild these systems or confuse a simulated enquiry with recognised revenue.
license: Internal EmpireOS authored instructions; ownership review required before redistribution.
---

# Empire AI Receptionist + Missed Revenue Recovery

## Mission

**Finish the existing commercial AI product, not a new infrastructure initiative.**

Customer calls → authenticated tenant-owned DID and Voice event → AI-disclosed receptionist conversation → approved business knowledge/service and time preference → explicit callback permission → **tenant-scoped CRM review** → customer-authorised follow-up and independently verified connection/calendar appointment → verified settlement → genuine recovered revenue and attribution.

Two distinct cases must remain distinct: (1) **answered** AI receptionist appointments/enquiries; (2) **unanswered** provider-confirmed missed calls subsequently recovered. A simulated appointment request, signed webhook, CRM draft, or answer to a call does **not** prove a missed recovery or payment.

## Before making anything new

1. Inspect git status and latest commit in the existing feature worktree `/home/ubuntu/empire_worktrees/inbound_revenue_recovery_20261020`, branch `feature/inbound-revenue-recovery-20261020`. If unavailable, locate the same modules in the current authorised checkout rather than creating a replacement.
2. Read `docs/commercial/INBOUND_REVENUE_RECOVERY_OWNER_BUILD_20261020.md` and `docs/commercial/EMPIRE_AI_RECEPTIONIST_SIGNED_CALL_CONTROLLER_20261020.md`. Those are history/technical handoffs; verify their claims against **current code, tests and deployed runtime**.
3. Follow [references/existing-system-map.md](references/existing-system-map.md) to locate canonical modules and ownership. Reuse them, not parallel tables, CRM, scheduler or Voice routes.
4. Identify the *next uncompleted customer outcome* and implement it in a narrowly scoped isolated worktree. Keep the actor owner explicit. Do not spend a session rebuilding backup readiness after its last verified pass unless fresh failure blocks a named release.
5. Use native **EmpireDB PostgreSQL** as the canonical DB and existing CRM tenant/membership authority. **Do not switch to Supabase or reuse legacy Supabase migrations**, despite stale historic code/doc wording. Version 057 is HELD/UNAPPLIED until separately approved.
6. Distinguish `TESTED` synthetic signed HTTP / in-process session from `DEPLOYED` dark staging and from an actually **LIVE** verified phone call. Verify served code/ports, not just source files.

## Existing owned components — extend, do not rebuild

- Receptionist conversation: `empire_os/inbound_reception_call_flow.py`, `inbound_reception_intake.py`, `inbound_reception_voice_api.py`, `inbound_revenue_recovery.py`.
- Vonage number ownership, signature and signed offline receipts: `inbound_provider_contract.py`, `inbound_signature_verification.py`, `inbound_recovery_store.py`. The existing `OfflineRecoveryStore` also hosts a **local dark-stage** tenant-scoped receptionist draft table, idempotent durable insert and restart-safe read. SQLite is not the canonical EmpireDB CRM. No production customer activation or inferred live call receipt.
- Verified missed-call recovery and results: `inbound_opportunity_intelligence.py`, `inbound_recovery_scorecard.py`, `inbound_source_attribution.py`, `inbound_recovery_patterns.py`, `inbound_booking_workflow.py` and `inbound_booking_store.py`. The read-only cross-link to existing RecoveryLedger is `inbound_reception_recovery_bridge.py`; it does not create or submit canonical CRM prospects.
- Customer voice/FAQ/hours: `inbound_business_hours.py`, `inbound_tenant_knowledge.py` and existing `voice_gateway_api.py` / `voice_lab.py` **without editing their currently live outbound call route**.
- Existing tenant CRM/read-only owner surfaces: `revenue_crm_api.py`, `revenue_crm_transport.py`, and EmpireDB `public.empire_crm_tenant_memberships`; use only independently authenticated dedicated CRM tenant reader. The optional private, default-off, same-engine owner-review endpoint `inbound_reception_crm_owner_review.py` displays consented requests but **does not** persist or promote CRM prospects. Own-account authorisation must be proven, not inferred from a caller-provided tenant.
- Google Calendar completion/registry/vault: existing `inbound_google_calendar_*.py`, `inbound_calendar_*.py`, only when owner OAuth and booking receipt gates independently pass.
- Prepared native RLS only: `migrations/empiredb/057_inbound_recovery_native_schema_held.sql`; **do not apply just to satisfy this skill**.

## Required integration rules

- Inbound phone `to` DID must resolve an *existing owner-verified tenant*; provider-signed Voice callbacks must pass JWT issuer, API/application, body digest, freshness and durable JTI replay checks. Do not trust `tenant_id` from a webhook. No unauthenticated public webhook.
- Do not retain raw speech, audio, name, ANI or contact details in general-purpose debug logs/CRM drafts. Obtain explicit, narrow callback consent, respect STOP/deletion/human escalation and store contact identity only in its authorised encrypted/retained tenant workflow when separately released.
- Intake order: disclose AI → identify approved service/intent → ask preferred broad window (not availability) → ask unambiguous *permission for business follow-up* → produce a single idempotent **PENDING_HUMAN_REVIEW_NOT_SUBMITTED** enquiry. No/STOP/unverified DID/unknown tenant creates no authorised CRM lead.
- An in-memory or locally SQLite-persisted `CRMEnquiryDraft` is not a canonical prospect, a live staffed transfer, a booking or delivered follow-up. Prove owner-authenticated, tenant-scoped, idempotent CRM acceptance and its original receipt before changing that status. Never insert arbitrary third-party prospect rows under a guessed tenant.
- Missed calls need **provider-authenticated terminal missed status**. Recovery needs a subsequently verified provider callback connection or a real independently confirmed, non-cancelled calendar booking to the same tenant/call. Revenue needs a later independently verified payment receipt. Deduplicate calls, appointments, payments and replay identifiers.
- Do not treat an answered receptionist enquiry as `verified_recovered_calls` or `verified_paid_recovery_minor_by_currency`. Unknown source/channel, revenue, margins and customer contact identity remain unknown.
- Human review precedes follow-up delivery, CRM promotion and outbound. No automatic customer SMS, dialling, recording, paid traffic, transfers, settlement, binding terms or public routing based on this skill alone.
- Preserve Lead Smart/Ringba roofing buyer route and its consent/recording restrictions; it is a **separate** revenue campaign, not the receptionist's test number.
- Failure/cancellation/opt-out/suppression must remove eligibility without deleting legitimate audit evidence. All per-tenant queries must be scoped and independently verified under native CRM authority.

## Existing local repeatable checks

From the isolated feature worktree; **synthetic only**, no external provider contact:

```bash
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B -m scripts.demo_ai_receptionist_call_20261020 --synthetic-only appointment
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B -m scripts.demo_ai_receptionist_call_20261020 --synthetic-only callback
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B -m pytest -q tests/test_inbound_*.py tests/test_voice_gateway_api.py
```

Use `scripts/review_inbound_revenue_recovery_20261020.py` only on an authorised, existing local evidence file in `--read-only` mode; check its own flags/help first. Never produce a first-party revenue claim from synthetic fixtures.

## Current gap-first engineering order

1. Reconcile the existing consented-receptionist `CRMEnquiryDraft` and signed event with the **existing RecoveryLedger**, without calling it a missed recovery. Build a tenant-scoped, authenticated, idempotent owner-review handoff with no live CRM write until native authority is verified.
2. The **offline** local enquiry has restart persistence in `OfflineRecoveryStore`; this does not make the voice-session/JTI cache durable. Replace those **in-process-only** session/JTI paths with the previously approved native tenant-isolated backend as permitted; verify replay and restarts without permitting unauthorised events.
3. Complete independently authorised real DID/Voice answer and input pilot, staffed fallback and privacy/suppression checks; avoid any change to existing active buyer campaign routes.
4. Reuse existing Calendar source/booking receipt validators; review appointment/callback → verified outcome → correctly attributed revenue in existing scorecard.
5. Package a clear customer view of actual missed calls, appointments, recovered outcomes, verifiable payment and support load. Make pricing/usage decisions only from defensible cost and accepted terms.

## Evidence contract

Every run must return a source-backed evidence ledger with: current feature commit and source hash, exact verified test command/result, runtime/service source and timestamp, inbound DID/provider attestation state, caller consent/opt-out decision, CRM owner/handoff receipt (or `NOT_SUBMITTED`), calendar and callback receipts (or `NOT_VERIFIED`), real payment evidence (or `NONE`), environment and execution authority. Preserve missing prerequisites and uncertainty explicitly. Any claimed outcome must be attributable to the same verified tenant, provider call, appointment and settlement identity. Synthetic results stay labelled synthetic even if all tests pass.

For unsafe/missing proof return `HOLD` with the smallest exact blocker and safe next test. No permission to contact a customer, submit a CRM lead, confirm an appointment or call revenue recovered is inferred from this skill.

## Required closeout

Give a compact handoff with: exact committed files and branch/commit; tests and synthetic-demo evidence; `STAGED / TESTED / DEPLOYED / LIVE / PROVEN` truth; pending owner/DBA approval; first remaining customer-revenue blocker and the **next action inside this same build**. Do not drift into unrelated backups, website redesign, lead marketplace or new architectures.

**Authority:** This skill is reusable engineering and evidence guidance, not an approval to activate live telephony, write canonical DB, send messages, record callers, move funds or state revenue. Explicit scoped authority and independent evidence are required.
