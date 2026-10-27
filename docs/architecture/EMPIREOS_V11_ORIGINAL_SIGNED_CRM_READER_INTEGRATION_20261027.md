# EmpireOS V11 — original signed CRM order to revenue case bridge

**Date:** 27 October 2026
**Release:** original PR #119 review branch only; **not deployed**.

## Original components reused

- `empire_os.crm_scoped_lineage_reader.review_signed_scoped_lineage` verifies the original Ed25519-signed tenant bearer, current membership, dedicated CRM login, session_user tenant binding, and the exactly scoped `public.empire_crm_exact_lineage(uuid,uuid,uuid,text)` function's SECURITY DEFINER provenance. It reads a single existing order; no direct raw order table access.
- `empire_os.revenue_crm_transport.PostgresRevenueCrmRepository.prospect` uses the original protected `revenue_crm_prospects` view, restricted role and session_user-resolved tenant. It is used only after the original signed order RPC has succeeded. The returned prospect's exact tenant, prospect, buyer and fulfilment order UUIDs MUST agree.
- `empire_os.crm_revenue_case_bridge.review_signed_crm_revenue_case` returns the existing `review_one_canonical_revenue_case` object with the original CRM's **reported** fulfilment state, a signed source scope indication and all five downstream V7–V10 stages marked `NOT_OBSERVED` until their original independent review receipts are actually read.

A view row marked `paid` or `settled` is NOT proof of buyer agreement, delivery, blockchain finality, completed reversal census, revenue, model learning or capacity. No V7–V10 receipt is guessed from the view's `fulfilment_state`. No caller-supplied receipt injection, production connector injection, new SQL privileges or extra credential transport is introduced.

## Current explicit gate

`docs/architecture/CRM_SCOPED_LINEAGE_RPC_HELD_20261026.sql` begins with **NOT A MIGRATION / DO NOT RUN/APPLY**. It requires the original CRM owner and privileged release reviews, independent fixture and rollback/privilege audit before its exact RPC may be applied. This PR DOES NOT apply it, set role grants, alter production, or bypass the missing reader by selecting restricted tables directly.

Until the original exact-order RPC is approved and installed, calls to the bridge fail closed. Therefore **no actual production tenant/order has been read or displayed**, and this is **not** a live Founder Console integration.

## Original founder console integration owner handoff

Existing interface: `apps/search-command-centre/src/app/founder/page.tsx`, which uses `apps/search-command-centre/src/lib/founder-api.ts`. Do not replace or fork it. After the CRM owner approves and verifies the SQL RPC under the original dedicated login, the original founder API owner may introduce one authenticated existing-order detail read, calling the V11 bridge server-side with the signed CRM bearer and existing restricted connection. Only the unprivileged, non-PII view-model fields should be returned. Do not expose tokens or DSNs to client-side JavaScript, a public URL, an unscoped list endpoint, or a new service.

The actual accepted terms, delivered outcomes, BSC receipt, costs, reversals and Economic Memory still require the original per-owner receipts before their respective V11 stages can advance. A CRM prospect view is not their substitute.

## Test evidence

`PYTHONPATH=.:tests /srv/empire_os/.venv/bin/python -B -m pytest -q tests/test_crm_revenue_case_bridge.py tests/test_crm_scoped_lineage_reader_20261026.py tests/test_canonical_revenue_case_progress.py` — **77 passed, one known Starlette/anyio deprecation warning**. These are offline fixtures and are not proof that the held production SQL exists or that a real order was checked.

A wider source/CRM integration selection also passed **449 tests with one existing Starlette/anyio deprecation warning**; this is not the whole-repository suite or a real production RPC acceptance check.

No database writes, payments, outbound, recognition events, trainable labels or live UI route changes are part of this feature.
