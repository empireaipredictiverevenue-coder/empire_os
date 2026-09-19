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
2. Require a first-party company website before enrichment; directory/social platform URLs do not count as company-site evidence.
3. Probe only first-party public company pages and structured data.
4. Separate schema.org `Person` evidence from business identity.
5. Rank economic/functional buyers from explicit titles.
6. Validate names for personhood; page labels do not count as people.
7. Require site-domain integrity before accepting site contact evidence.
8. Verify discovered direct email separately from discovery.
9. Build an OBSERVE-only buyer-candidate review proposal.
10. Human approval is required before a reviewed outbound intent can be proposed.
11. Message approval remains a separate human gate before any provider send.

## Review-only proposal gate
- `scripts/outbound_proposal_preview.py` renders a `propose_buyer_candidate_review` payload first.
- Only when an approved review UUID is explicitly supplied can it render `propose_reviewed_outbound_intent`.
- Output is always `mode=OBSERVE` and `write_authorized=false`.
- Requires a verified direct non-role email and canonical prospect UUID; outbound copy additionally requires opt-out wording and configured postal address.
- It does not call Supabase, approve a candidate/message, or contact Resend.
- Candidate approval and message approval are separate human permission boundaries.

## Contact evidence rule

Official company-site emails and generated work-email patterns are different evidence classes.
Observed company-site emails may enter contact verification. Generated patterns remain candidates only and must not become outreach-ready without mailbox-level evidence.
The review-only proposal CLI never writes or sends. It renders the candidate-review payload and, only with an explicit approved review UUID, the reviewed-outbound payload for human review.
## Bounded batch review
- `scripts/buyer_discovery_preview.py` supports optional `--niche` and `--metro` filters using the canonical niche-family/metro normalization, so review can be scoped to a real target market before ranking or probing.
- Directory/social URLs are stripped from buyer candidates, contribute no website score, cannot seed generated work-email patterns, and are never sent to the public-site probe.
- `scripts/buyer_discovery_preview.py --probe N` isolates each public-site probe in a child process.
- `--probe-timeout` applies a hard per-site deadline so broken websites cannot stall the batch or remote bridge.
- Results include explicit rejection reasons such as `site_timeout`, `no_decision_maker`, `no_bound_contact`, `role_address_only`, and `contact_not_verified`.
- DNS-only contact validation is used in preview mode; no email is sent and no SMTP mailbox probe is required.
## Current-role reconciliation
- Canonical contact/title fields are not trusted indefinitely.
- Current official-site person evidence is reconciled against the canonical decision maker before outreach readiness.
- A materially lower current role (for example, canonical `Owner` but current official site `Project Manager`) sets `review_required=true` and blocks outreach.
- Equivalent economic-buyer authority can confirm the candidate.
- Public-web validation on 2026-09-17 exposed a real stale-role example, proving this gate is necessary.
## Public-web corroborated contact evidence
- Explicit public business-directory contact evidence may bind to a decision maker only when the person identity matches exactly and the role is independently corroborated.
- Unsupported sources, mismatched names, and uncorroborated third-party records are rejected.
- DNS-valid public contact evidence can make a candidate `review_ready` without making it `outreach_ready`.
- First real canonical prospect reached `review_ready=true` on 2026-09-17; it remained `outreach_ready=false` pending stronger mailbox-level evidence.
- Later the same day, Jake Montgomery / Silverado Construction Services became the first canonical prospect to reach both `review_ready=true` and `outreach_ready=true` using an exact email published in a 2025 government permit record, current founder/owner corroboration, same-domain identity, and valid MX.
- SMTP probing is treated as optional supporting evidence because network policy can block port 25; recent exact public publication plus current role corroboration is accepted as a stronger provenance path than inferred email patterns.
- No production row was created and no email was sent.

