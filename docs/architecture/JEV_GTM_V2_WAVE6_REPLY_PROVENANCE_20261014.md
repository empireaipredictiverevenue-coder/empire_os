# JEV GTM V2 — Wave 6 Original Reply Candidate Boundary

Date: 2026-10-14
Worktree: `/home/ubuntu/empire_worktrees/jev_gtm_v2_20261014`
Branch: `feature/jev-gtm-v2-20261014`
Starting commit: `10f099fd`
Mode: OBSERVE; **no production migration, no live DB reads, no outbound action, no new login, no additional server**.

## Production truth identified

- Existing `empire_os.conversation_read_transport` performs global conversation/events reads under `empire_conversation_reader`; migration `016_active_runtime_authority.sql` authorises that role with RLS `USING (true)`. This does not independently establish a tenant-bound original inbound reply.
- Canonical Revenue CRM view `040_revenue_crm_tenant_reader_views.sql` intentionally projects NULL for conversation, closer, fulfilment and buyer linkage pending independently proven joins.
- Existing `conversation_reply_binding_review` already identifies *structurally reviewable, not authenticated* provider chains.
- A real prospect identity is not a genuine buying signal. The existence of an outbound reply row alone is not independently verified provider receipt, sender contact identity, buyer intent, or consent.

## Implementation

### Migration 051 — PREPARED ONLY (not applied)
`migrations/empiredb/051_jev_crm_reply_candidates.sql`

Adds a bounded, static `public.empire_read_crm_reply_candidates(uuid,integer)` SECURITY DEFINER **metadata-only** function that uses the existing `empire_revenue_crm_reader` role.

- Guard verifies the canonical database, restricted reader role, owner SELECT privileges, trusted existing tenant and prospect authorization functions and absence of an existing conflicting RPC.
- Scope resolved exclusively from `public.empire_current_tenant_id()` using the real `session_user` principal. `public.empire_crm_prospect_authorized(p_prospect_id)` must return true.
- Only one requested prospect, matching email intent, 1–100 sorted rows.
- Joins existing `outbound_replies`, `outbound_intents` and counts structurally matched `empire_conversations` with matching prospect IDs.
- Returns reply/intent UUID references, timestamps, declared classification, intent status, boolean presence of provider reference and conversation match cardinality. Excludes message bodies, email addresses, untrusted metadata and raw receipt IDs.
- Hardcodes `original_provider_authenticated=FALSE`, `contact_binding_verified=FALSE`; neither a provider message ID nor a matched conversation proves original sender authentication.
- Revokes PUBLIC/general-role RPC execution; grants only to the existing restricted CRM reader group. The role receives no direct table reads.
- No role creation, membership grant, table writes, changes to the old unscoped reader, or live activation.

### Python reader

`empire_os/jev_gtm_reply_candidate_reader.py`

- Reuses `PostgresRevenueCrmRepository._fetch_all`, which already starts READ ONLY, checks session-user tenant, uses existing CRM group role and applies a bounded query timeout.
- Checks the response tenant, requested prospect, unique reply identity, chronology, supported classification, cardinality and explicit non-authority.
- Produces deterministic, privacy-minimal review packets with unverified classification labels and reason codes. A row saying `positive` is **never** treated as a verified buyer conversation.
- Missing migration or wrong DB permissions produce sanitized fail-closed errors; no fallback to unscoped conversation queries.

### Founder API and dashboard

`empire_os/founder_jev_api.py` conditionally adds:

`GET /v1/founder-jev/crm-prospects/{prospect_id}/reply-candidates?limit=25`

This is registered **only** when the host injects BOTH an independent founder authorizer and the existing authenticated tenant-scoped CRM resolver. Absent these, no data route is exposed. The endpoint returns 401/403/503 for failed scope/authorization/source and rejects unexpected response fields or any attempt to label replies authenticated.

`/v1/founder-jev/status` exposes truthful prepared/unknown flags (migration 051 live-application state is UNKNOWN, verified replies unavailable), and `/founder/jev` shows a pending provenance gate. Neither is deployed to production in this wave.

### Verification

Unit and route suites:
- `tests/test_jev_gtm_reply_candidate_reader.py`: wrong scope, duplicates, clock, unsupported classes, unbound/wrong tenant, no PII, missing RPC, non-authority.
- `tests/test_founder_jev_reply_candidates_api.py`: real role-type resolver, independent authorization ordering, scope denial, response allowlist, no spoofed provider proofs.
- `tests/test_jev_reply_051_ephemeral.py`: **real, disposable PostgreSQL 18 instance** created under temporary directory, PostgreSQL logins for tenants A and B, canonical-bound session, SQL migration applied ONLY in the disposable fixture, role/RPC grants, cross-tenant denials, direct private body table denial, exact data-scope checks and end-to-end real psycopg adapter read.
- TypeScript type-check with existing installed dependencies: `tsc --noEmit --incremental false -p tsconfig.json`.

All data in these tests is synthetic and fictional. The **real SQL/role semantics** are exercised in a completely separate disposable DB; these are not production queries or real buyer outcomes.

## Why this is not a buyer-response activation

The current provider mail ingestion must independently prove provider identity, signed original receipt / authenticated transport metadata, RFC parent linkage, canonical contact relationship and suppression status. Without that, **verified original reply count remains NULL**, even when source tables contain apparent positive replies. Do not treat model class confidence as conversion probability.

## Next release gate

1. Founder separately approves migration 051 and independently checks it against the current live EmpireDB schema/roles before applying. No approval is implied by code generation or passing synthetic tests.
2. Authorised read-only live tenant session proves dedicated CRM login and scoped actual reply candidate counts. No fallback if DB denies scope.
3. Integrate original mailbox/provider attestation using existing first-party mail transport, canonical contact authority and the identity adjudicator. Never use the unscoped Conversation OS reader as tenant proof.
4. Calibrate JEV against independently reviewed genuine buyer replies and outcomes, then authorise any operational promotion separately.

No database or sender was modified by this worktree release. The first genuine buyer conversation and realised revenue remain externally verifiable commercial outcomes, not a test result.
