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
