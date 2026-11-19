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
