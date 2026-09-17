# Phase 3E — Real Buyer Discovery

Status: OBSERVE-only selector and public-site decision-maker evidence layer local/tested.

## Canonical coverage snapshot — 2026-09-17
- prospects: 29,807
- prospects with website: 24,326
- prospects with phone: 13,423
- prospects with positive buy-signal score: 7,219
- active prospect→business-entity links: 12,184
- prospects with contact name + title: 127

The current bottleneck is decision-maker/contact resolution, not raw company discovery.

## Operating sequence
1. Rank real canonical businesses using observed company evidence.
2. Require a public website before enrichment.
3. Probe only public company pages and structured data.
4. Separate schema.org `Person` evidence from business identity.
5. Rank economic/functional buyers from explicit titles.
6. Validate names for personhood; page labels do not count as people.
7. Require site-domain integrity before accepting site contact evidence.
8. Verify discovered direct email separately from discovery.
9. Build an OBSERVE-only outbound intent plan with opt-out and postal footer.
10. Human approval remains mandatory before any provider send.

## Review-only proposal gate
- `scripts/outbound_proposal_preview.py` renders the exact governed `propose_outbound_intent` RPC payload.
- Output is always `mode=OBSERVE` and `write_authorized=false`.
- Requires a verified direct non-role email, canonical prospect UUID, opt-out wording, and configured postal address.
- It does not call Supabase, approve an intent, or contact Resend.
- Human approval remains a separate permission boundary before any send claim.

## Contact evidence rule

Official company-site emails and generated work-email patterns are different evidence classes.
Observed company-site emails may enter contact verification. Generated patterns remain candidates only and must not become outreach-ready without mailbox-level evidence.
The review-only proposal CLI never writes or sends; it only renders the exact governed `propose_outbound_intent` payload for human review.
