# Outbound Review Visibility Architecture Delta V1

Date: 2026-10-02
Class: Pure corrective maintenance / bounded architecture delta
Owner: Governed Outbound / Control Fabric
Commercial purpose: restore qualified first-touch revenue outreach without weakening buyer-review gates

## Diagram

canonical buyer evidence
-> buyer_candidate_reviews (approved + reviewed_at)
-> RLS SELECT policy for empire_outbound_approver
-> PostgresStandingAuthorityApproverRpc preflight
-> auto_approve_outbound_intent
-> existing daily-cap / suppression / personhood / contact-evidence gates
-> approved outbound intent
-> governed sender
-> buyer reply
-> closer / terms / order / USDT BSC / fulfilment / realized margin

## Root cause

The outbound approver already has table-level SELECT on
public.buyer_candidate_reviews, but RLS is enabled and no SELECT policy exists
for empire_outbound_approver. The SECURITY INVOKER standing-authority RPC
therefore sees the bound approved review as NOT FOUND and raises the generic
"fresh approved buyer candidate review required" error.

Two live pending managed-service intents were independently verified on
2026-10-02 to have fresh approved reviews and to pass every downstream
standing-authority check. No buyer-evidence refresh is required for those rows.

## Truth contract

Migration 030 adds only a SELECT RLS policy for empire_outbound_approver.
It does not create, approve, refresh, update or delete buyer reviews.

The outbound transport also verifies the RLS visibility contract before calling
standing authority. Missing policy/grant or unexpected review-write privilege
fails closed with an explicit authority-contract error.

## Authority contract

No new outbound standing authority is granted.
No daily cap is changed.
No scoring threshold is changed.
No suppression/personhood/contact-evidence rule is changed.
No generic app role inherits outbound authority.
No email is sent by this migration or preflight.
Database activation remains founder-gated.
A resulting live outbound send remains governed by the existing approved
standing-authority configuration.

## Execution / failure behavior

The preflight is synchronous and read-only inside the dedicated approver
connection after SET LOCAL ROLE empire_outbound_approver.
Authority drift fails closed before the approval RPC.
Migration 030 is idempotent and HELD until explicit founder approval.

## Verification

1. Disposable PostgreSQL proves RLS hides the review before migration.
2. Migration 030 proves the approver can read approved reviews after migration.
3. The same test proves UPDATE and DELETE remain denied.
4. Transport tests prove missing RLS policy fails with a precise error.
5. Adjacent governor/transport/personhood tests remain green.
6. Read-only live preflight verifies current production is missing only the
   required review SELECT policy and that candidate gates remain satisfied.
7. After founder approval: apply migration, verify policy/grants, run governor,
   verify canonical approval/send events, and update checklist only from live
   evidence.

## Rollback

Drop only policy:
buyer_candidate_reviews_empire_outbound_approver_select

No data rollback is required because migration 030 mutates no business rows.
