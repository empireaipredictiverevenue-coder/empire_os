# OpenManus / Vane owner handoff — Revenue Recovery Google Calendar connection

**20 October 2026 — source-review / supervised test assignment only.**

This is a request for the existing OpenManus/Vane research/execution owner, NOT authorisation to install another OpenManus runtime, open a browser against a customer calendar, deploy an API, use Gmail credentials, or change production systems.

## Purpose

Review the existing **Revenue Recovery Engine** customer-owned Google Calendar connection journey and produce evidence-backed, bounded operator test tasks that the Revenue Recovery owner can implement and verify.

**Revenue Recovery owner code branch:** feature/inbound-revenue-recovery-20261020

**Read-only files to inspect:**
- empire_os/inbound_calendar_connection_identity.py — tenant-authorised owner/admin token with a dedicated Ed25519 audience; checks existing canonical EmpireDB membership every time
- empire_os/inbound_calendar_oauth_onboarding.py — one-time OAuth state and PKCE bound to tenant, administrator and browser session
- empire_os/inbound_google_oauth_exchange.py — Google token exchange and read-only scope validation
- empire_os/inbound_calendar_token_vault.py — encrypted staging-only credential vault, revocation, key rotation
- empire_os/inbound_google_calendar_credentials.py — owner-approved calendar role check and read-only token lease
- empire_os/inbound_google_calendar_enrollment.py — fail-closed owner/customer calendar registration
- empire_os/inbound_google_calendar_adapter.py — read-only events.get, calendarList.get and freeBusy
- empire_os/inbound_calendar_projection.py — offline evidence delivery into the recovery ledger and appointment status
- tests/test_inbound_calendar_connection_identity.py — signed tenant role and audience boundary
- tests/test_inbound_google_calendar_credential_flow.py — simulated end-to-end pathway

## Delegated OpenManus activities

1. Use the existing bounded research and browser-inspection profiles to review published Google Calendar OAuth + API documentation, citing official page URLs, retrieval date and each relevant permission limitation.
2. Produce an **operator-review checklist** for normal and failure UX: tenant account wrong, expired/replayed state, rejected consent, revoked Google grant, unapproved calendar, missing source marker, cancelled booking, OAuth refresh denied, duplicate callback, cross-tenant account, permission downgrade.
3. Validate that the customer sees explicit consent wording for *reading* events/free-busy, never implied authority to create bookings. Confirm exact HTTPS callback/redirect origin and cookie SameSite choices against the intended real frontend.
4. Supply a Playwright/browser-test PLAN compatible with the existing authenticated UI (do not execute real logins unless the owner separately authorises a dedicated isolated test account). No copy of browser cookies/tokens or personal/customer data.
5. Return a machine-readable evidence-gap report and recommendations. Label findings as SOURCE_VERIFIED, TEST_FIXTURE_ONLY or UNKNOWN. Nothing is a production acceptance receipt without real owner verification.

## Explicit exclusions

- Never modify Revenue Recovery source, CRM identity, the canonical membership database, credentials vault, Google Cloud console or production routes.
- Never mint identity tokens or OAuth grants; never handle access tokens, refresh tokens, Google client secrets, caller PII or private calendar content.
- No event creation, customer contact, outbound calls, business profile changes, payments or deployment.
- Do not duplicate the worker/runtime. Existing ASTRA orchestration retains the execution and approval boundary.
- Any proposed execution outside public documentation and static review needs an explicit owner-approved ticket, restricted environment, scope, timeout, and read-back.

## Completion deliverables

A concise markdown review and an optional JSON evidence-gap artifact with: exact file/contract, risk, independent source, proposed bounded validation, expected safe failure, owner, and current state. Do not claim an agent or browser test has run until its output is independently observed.

**Integration status:** This document is a handoff contract; an actual running OpenManus worker has not been verified here, and no tasks have been dispatched.
