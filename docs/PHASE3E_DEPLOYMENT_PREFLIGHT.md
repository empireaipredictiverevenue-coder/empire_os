# Phase 3E Production Deployment Preflight

Status: ready for explicit production approval; no Phase 3E production mutation has been performed.

## Verified local state — 2026-09-17
- Intelligence Fabric DB tests: 6/6 passed.
- Governed outbound DB tests: 7/7 passed.
- Supabase closer state-machine tests: 7/7 passed.
- Dedicated runtime identity tests: 3/3 passed.
- Buyer candidate review-gate tests: 6/6 passed.
- Total database checks: 29/29 passed in disposable PostgreSQL.

## Production read-only preflight
- No Phase 3E target tables, functions, or roles currently exist in production.
- buyers: 1,057
- prospects: 29,807
- business_entities: 1,451
- fulfilment_orders: 0

The zero fulfilment-order count is a hard commercial blocker. The closer cannot legitimately reach proposal/payment states until a genuine priced order with real commercial terms exists.
## Required migration order
1. `20260917183000_empire_intelligence_fabric.sql`
2. `20260917190000_governed_outbound_reply_capture.sql`
3. `20260917193000_supabase_closer_state_machine.sql`
4. `20260917194500_phase3e_runtime_identities.sql`
5. `20260917201500_buyer_candidate_review_gate.sql`

## Post-migration secret provisioning
Provision out of band; never commit credentials to the repository:
- proposer/runtime login password
- outbound approver login password
- outbound sender login password
- reply-ingest login password
- closer approver login password
- Resend API key
- Resend webhook signing secret

Do not enable sending simply because migrations are applied. Runtime identities start passwordless/unusable by design until secrets are provisioned.
## Safe activation sequence
1. Apply the five migrations in order after explicit approval.
2. Verify roles remain least-privilege and direct table writes are denied.
3. Provision runtime passwords outside Git.
4. Start the isolated Resend inbound receiver on loopback only.
5. Register/enable the signed Resend webhook only after receiver health checks pass.
6. Perform a controlled send to a user-controlled address first.
7. Verify signed reply ingest, suppression, and append-only events.
8. Nominate the first real candidate into the human review queue.
9. Human approves candidate; service may create a pending outbound intent.
10. Human separately approves the outbound message before sender claim.

## First-revenue path after activation
- Use real buyer evidence only; no synthetic lead/buyer/payment rows.
- Obtain genuine commercial terms and create the first canonical priced fulfilment order.
- Keep autonomous execution in OBSERVE until explicit policy changes are approved.
- Verified escrow funding is not revenue; only independently verified release/payment evidence can become revenue-eligible.
- Phase 3F outcome feedback starts only after genuine delivery/conversion/payment outcomes exist.