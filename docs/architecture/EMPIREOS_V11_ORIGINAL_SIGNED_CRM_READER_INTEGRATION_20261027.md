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

## 27 October — Founder Console display and owner security release review

- The original CRM pilot service is **active** and its private loopback `/health` reports approved read-only pilot mode, no outbound or payments. Health does NOT confirm the separate exact-order SQL RPC is installed.
- The original production checkout's `empire_os/revenue_crm_transport.py` has an UNCOMMITTED CRM-owner-only `CRM_LOGIN_AUTHORITY_SQL` hardening delta. The V11 PR's branch deliberately does not copy or commit that owner's private work. Without the original owner releasing its login proof, `review_signed_scoped_lineage` fails closed with `ORIGINAL_CRM_LOGIN_ATTESTATION_UNRELEASED`.
- The `CRM_SCOPED_LINEAGE_RPC_HELD_20261026.sql` release candidate remains explicitly **DO NOT RUN/APPLY**. V11 did not install/grant it and did not inspect raw tenant/customer tables. Owner sign-off and exact role/tenant-RLS, catalog, rollback and independent production privilege checks are outstanding.
- The existing `apps/search-command-centre/src/lib/founder-api.ts` gets founder overview via a general no-store API fetch without a user-bound CRM bearer at that call site. Private order details must NEVER be put into that overview or a publicly reachable route.
- The V11 bridge now emits a **whitelisted `founder_case_view`**, limited to the hashed case reference, reported order state, source-stage status and next owner/action, with no tenant/order/prospect/buyer UUID, token, DSN or payment refs. It remains a formatter, NOT a separate authentication control.
- A presentational `apps/search-command-centre/src/app/founder/revenue-case-panel.tsx` component is staged. It takes ONLY that redacted view, has NO browser fetch, session management or route, and displays a hold when no signed order view exists. It is NOT currently imported into the original founder page; the console owner must first provide a server-side session-authorised order-detail route.
- Additional negative tests deny spoofed authentication/profit statuses and check that the display DTO contains no secret bearer, full entity UUIDs or connection details. No live order was read, no signed founder session was impersonated and no founder-console deployment was performed.

### Exact release sequence for the original CRM and console owners

1. **CRM transport owner:** finish/review/commit the in-progress dedicated-login attestation in the original checkout; validate the dedicated login's fixed role membership, no inherited/wider privileges and exact session_user binding.
2. **CRM SQL/security owner:** independently review the held exact-order `SECURITY DEFINER` RPC, enforce safe search path, public execute revocation, strict role-only EXECUTE, tenant binding and zero raw-table grants; run disposable staging SQL/security tests and retain rollback. Explicitly approve release before deployment.
3. **First-party CRM owner:** authenticate a real founder CRM session with the existing signed Ed25519 tenant token and current canonical membership; pass one existing exact order/prospect/opportunity UUID triplet through the original restricted login and prove the RPC's one-row tenant/order match. No fake fixture or global order scan.
4. **Existing Founder API owner:** wire the authenticated **server-side** owner reader to the private case-detail route and `founder_case_view` only, with no-store/no-cache, session-scoped access, no tokens or DSN client-side; attach the staged component inside the existing founder console. Run security and visual checks before a separate approved production release.
5. **RevenueRecognition and FulfilmentOperations:** independently attach original V7–V10 receipt evidence by the same order, verify contracted payer, provider/buyer delivery, BSC/escrow, reversal census and invoice/cost proof before any revenue or learning promotion.

Validated in the isolated review worktree: **458 selected Python tests passed**, one existing Starlette/anyio deprecation warning, and the staged TSX component passed **strict TypeScript compilation** with the original console's installed toolchain. This is not an end-to-end browser/session test, privileged production SQL audit or live order verification. The production console still does NOT show an actual V11 order.

This PR cannot certify owner approval, live authenticated order availability or production data; those remain UNKNOWN / HELD.
