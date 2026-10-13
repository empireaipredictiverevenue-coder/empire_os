# Enterprise £100k/month programme — contact execution and diagnostic gate
**13 October 2026 · OBSERVE / no new sent message / no customer commitment**

## What was executed
- Reconciled existing canonical `runtime/predictive_revenue/enterprise_activation_latest.json`: 34 enterprise targets, only **2** with `person_contact_verified=true` and `review_ready=true` (Redwood, Sila). `outreach_authorized=false` for both.
- Cross-checked the two original Gmail conversations; both have a founder **SENT** message on 24 September 2026, no inbound reply in the inspected two-message threads, and an unsent follow-up from 29 September.
- **Updated the two EXISTING Gmail follow-up drafts in place on 13 October** with a precise, research-grounded question and a low-friction email response CTA. Preserved the original thread; **no email was sent**, no duplicate first touch created.
- Exact verified contact identity:
  - **Redwood Services — Richard Lewis, CEO/Founder, `richard@redwoodservices.com`.** His official bio publishes both: https://redwoodservices.com/team-member/richard-lewis-chief-executive-officer-founder/ . Redwood's 2026 Sierra expansion is official: https://redwoodservices.com/news/redwood-services-expands-national-footprint-with-acquisition-of-sierra-platform-from-se-capital/ . Existing Gmail sent message `1a0d5cdf953936f4`, existing thread `1a0d5cdf953936f4`, refreshed draft `1a13691bc34bcc6a`, Gmail draft ID `r-5531695642421530293`.
  - **Sila Services — Kyle Martin, VP Corporate Development, `kmartin@sila.com`.** Sila's official https://silaservices.com/leadership/ publishes both; the title is corp-dev **not** proof of budget authority for revenue intelligence. Existing Gmail sent message `1a0d5ce150bb1a71`, original thread `1a0d5ce150bb1a71`, refreshed draft `1a13691c96c42703`, Gmail draft ID `r-3112428770958438914`.
- Sila's official leadership page also describes CRO Ryan Flaherty, CMO Lara Drake and CTO Keith Chisholm, but does NOT publish their person-bound business emails. Do not infer or invent those addresses or open parallel duplicate approaches without a founder decision.
- TurnPoint: named CMO but no verified direct vendor email; no outbound. Apex: `info@apexservicepartners.com` is a public **general** email. Apex's `/partner-with-us/` form is aimed at owners selling/joining home-services companies, NOT software procurement; no unsolicited form send.

## Reusable existing-governor gating — no automatic lift
The existing outbound governor already treats unknown suppression as a hold. The separate `runtime/control_plane/consent_suppression_effectiveness_latest.json` observation says `semantic_effectiveness=INEFFECTIVE_IDENTITY_BINDING` while `safety_effectiveness=EFFECTIVE_FAIL_CLOSED`. Neither is address-level clearance.

**One-shot narrow read-only canonical recipient check** is staged at `scripts/inspect_enterprise_followup_recipients_readonly.py`:
- Exact two-person allowlist, parameterised SQL, a single `BEGIN READ ONLY` PostgreSQL transaction and four-second statement timeout.
- Reports only exact/domain suppression hits and per-recipient canonical intent/delivery-event counts, with known Gmail prior-contact and draft flags.
- Missing DB credentials, incomplete rows, unknown status or SQL error **fail closed**. It NEVER marks send authorised even with zero suppression hits, because separate Gmail recent-reply, actual sender identity, approved founder send, existing outbound governor and recipient route checks remain.
- Run under an approved already-configured EmpireDB reader/operator; do not embed passwords/DSNs in source or logs and do not source protected credentials from this review-only file.

## The actual next commercial decision
1. Obtain canonical exact suppression evidence for **both** `richard@redwoodservices.com` and `kmartin@sila.com`, including domain and `@domain` matches, and independently check latest bounce, opt-out and any other sender/reply system.
2. If eligible, review the exact **existing** follow-up drafts, founder approval, required approved mailbox identity, and no-repeat/cadence rules **before** any send. Do not mislabel draft as SENT.
3. If either buyer replies with a real business problem, ask about one brand/market, how demand-to-booking and booking-to-realised gross profit are measured, existing analytics, data/control owner, permitted data access, measurable decision criteria and economic authority. Do not send fabricated case studies, generic AI promises or a $100k pitch on first touch.
4. Prepare the founder-approved **$25,000 one-time** Predictive Revenue Diagnostic only **after** this buyer-led discovery and a verified delivery feasibility assessment. Proposed nonbinding diagnostic focus: evidence inventory, forecast-readiness baseline, conversion and revenue-leakage review, risk/opportunity prioritisation, accuracy/uncertainty limitations, and decision memorandum. The exact deliverable scope, cost and data-processing/contract terms are unverified. Explicitly separate any future optional monthly managed intelligence from one-time fees.
5. Only after completed verification and independent financial release may a binding contract, approved payment request, fulfillment and reconciled revenue be reported. The £100k target means **recognised GBP recurring monthly revenue**, not a one-time USD deployment.

**Execution authority:** NONE for new sends, database mutation, payment, deployment, live traffic and contractual acceptance. The update to Gmail drafts is review-only and separate from server-run automatic outbound.
