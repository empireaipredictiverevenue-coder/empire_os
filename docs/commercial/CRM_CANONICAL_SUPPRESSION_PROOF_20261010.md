# CRM suppression evidence reader — 10 October 2026

State: CODE PREPARED, NOT PRODUCTION ACTIVE.

## Delivered

The existing authenticated CRM channel-evidence endpoint now has a separately testable read-only PostgreSQL adapter in `empire_os/revenue_crm_suppression_evidence_reader.py`. The adapter does not query raw contact information or the global suppression table. It authenticates the tenant-bound dedicated CRM reader login, verifies the database tenant, checks the presence and provenance of a narrowly scoped canonical database function, and accepts only `SUPPRESSED` or `UNKNOWN` for an exact prospect's SMS channel.

A confirmed hit is reported as blocked. Unknown, missing proof, unavailable function, login/tenant mismatch or driver failure can never become suppression clearance. Email and web-push remain unknown. The channel classifier separately retains unknown marketing opt-in and identity binding; no send authority is ever issued. The CRM API receives a contact-free status only.

## Explicit production dependency

The database function `public.empire_crm_prospect_suppression_hit(uuid,text)` does **not** exist as a deployed verified capability. The adapter deliberately refuses to query the canonical suppression ledger until a separately reviewed and founder-approved, tenant-safe, no-contact-disclosure database implementation is deployed. No migration or role privileges were applied in this change.

That function's contract must return only SUPPRESSED or UNKNOWN, never ALLOWED or NOT_FOUND. It must prove tenant-scoped prospect access using the existing trusted server/database identity, not a browser header or unverified caller string. Because the canonical CRM view has no explicit, person-bound channel consent, even a verified suppression no-hit cannot establish eligibility.

Do not connect an external message provider or enable sending based on this reader. Do not change the concurrent uncommitted `empire_os/revenue_crm_transport.py` work without the other worker's review.

## Completion evidence

Run `PYTHONPATH=. ./.venv/bin/python -m pytest -q tests/test_revenue_crm_suppression_evidence_reader.py tests/test_revenue_crm_channel_evidence.py tests/test_revenue_crm_api.py tests/test_revenue_crm_authenticated_router.py tests/test_revenue_crm_journeys.py`.

Deployment acceptance requires separately reviewed canonical database function ownership, permissions, tenant/RLS scope, actual positive suppression-hit test on a permitted fixture, a negative unknown test, and authenticated production CRM proof. Only then can the source be marked CANONICAL_READER_VERIFIED. Current tests use no production database.
