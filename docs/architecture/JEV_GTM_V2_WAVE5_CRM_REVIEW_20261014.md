# JEV GTM V2 — Wave 5 Canonical CRM Review

Date: 2026-10-14
Isolated branch: `feature/jev-gtm-v2-20261014`
Start commit: `751749b5`
Status: OBSERVE / no production merge, reader activation, outbound sending, payment or database change

## Why this release

The current canonical Revenue CRM view `public.revenue_crm_prospects` was inspected in
`migrations/empiredb/040_revenue_crm_tenant_reader_views.sql`.
Its tenant-bound prospect identity/status/name/niche/metro exist, but **conversation,
closer, fulfilment, linked buyer capacity, deal probability and price fields are
intentionally NULL**. There is no trusted original buyer reply in that view.

Thus JEV must distinguish **canonical CRM prospects** from **original customer
replies** and **qualified, verified buyers**. This release makes that
distinction operational rather than treating NULL as a successful handoff.

## What is implemented

### Reuse authenticated CRM repository, no new database code
`empire_os/jev_gtm_crm_review.py` invokes the existing
`PostgresRevenueCrmRepository.prospects(limit)` implementation from
`empire_os/revenue_crm_transport.py`.

The existing reader already executes `SET TRANSACTION READ ONLY`,
`SET LOCAL ROLE empire_revenue_crm_reader`, derives the tenant from
`public.empire_current_tenant_id()` and verifies returned row scopes.
No other SQL, DSN, role, table grant, scheduler or account is introduced.

- Strict 1–100 record bound, canonical UUID identities, mixed-tenant and duplicate rejection.
- Reuses `derive_next_action` for canonical deterministic commercial hints,
  and `review_crm_reply_qualification` for original inbound proof blockers.
- Reports `CANONICAL_IDENTITY_RESEARCH` for unlinked prospects and
  `REPLY_EVIDENCE_REVIEW` only for an independently reported conversation
  reference; **neither lane proves a buyer replied**.
- Projects bounded, privacy-minimal prospect ID, niche, metro, status and
  blockers; never emits original message body, email or company name.
- `scanned_count` describes the bounded reader result, not whole-tenant
  prospect totals. A full inventory is *never* claimed. Exact-limit responses
  mark `more_rows_possible=true`.
- Independently verified buyer and inbound reply counts stay null/unavailable,
  not fictional zeros. No conversion probability or recognized revenue.
- All outputs are review-only with no contact permission, outbound authority,
  payments, fulfilment or CRM writes.

### Existing Founder Read API optional integration

`empire_os/founder_jev_api.py` conditionally mounts:

`GET /v1/founder-jev/crm-prospects/review?limit=25`

**Only if** the hosting service explicitly injects BOTH:

1. An independent server-side founder authorizer.
2. The existing CRM's request-scoped `AuthenticatedRevenueCrmRead`
   resolver, returning the concrete `PostgresRevenueCrmRepository`
   and a matching canonical tenant.

The authorizer runs **before** resolver/database calls. Anonymous requests
403; no tenant binding 401; invalid role/scope/reader/schema 503 with no PII.
Request query cannot select a tenant, supply arbitrary SQL or exceed 100 rows.

The API imposes an **exact no-PII response allowlist** and rejects unexpected
fields or attempts to assert verified buyer identity, inbound proof, contact
clearance or outbound authority. The default Founder service injects neither
resolver nor authorizer and therefore **does not mount this route**.

### Founder Console

Standalone `/founder/jev` now displays a canonical CRM reader configuration
gate alongside the existing economic reader and model-calibration gates.
The existing `/founder` page and shared `founder-api.ts` remain untouched
to avoid disturbing concurrent agents. The page remains an isolated branch
artifact and is NOT deployed.

## Verification

- `tests/test_jev_gtm_crm_review.py`: source bounds, identity scope,
  duplicate detection, unlinked conversation, deterministic next-action
  preservation, no private contacts and no invented reply evidence.
- `tests/test_founder_jev_crm_api.py`: paired auth, DB-only after authorizer,
  wrong tenant, untrusted repository, route gating, response allowlist,
  oversized queries and sanitized failures.
- Existing `tests/test_revenue_crm_transport.py`,
  `tests/test_revenue_crm_reply_qualification.py` and
  `tests/test_founder_jev_api.py` regression remain mandatory.
- Frontend TypeScript validation completed with
  `tsc --noEmit --incremental false -p tsconfig.json`.
- Fixtures simulate canonical CRM data; **no live EmpireDB records were read**.

## The remaining real-revenue blocker

Current view cannot assert genuine buyer replies, so a future authenticated,
tenant-scoped, original-provider Conversation OS linkage must be tested before
JEV can count positive conversations. In particular, avoid relabelling the
existing unbound `conversation_read_transport.py` projection as verified
tenant authority without independent proof and governance.

Production reader configuration, actual tenant authentication, live readback,
representative outcome-labelled calibration, review staffing and deployment
remain gated. This commit does **not** create a live CRM action system or an
automatic sender.

Next step should be integrating already-authorised original reply evidence
and measuring whether the model changes genuine conversion outcomes; avoid
building another parallel CRM, mailbox or agent runtime.
