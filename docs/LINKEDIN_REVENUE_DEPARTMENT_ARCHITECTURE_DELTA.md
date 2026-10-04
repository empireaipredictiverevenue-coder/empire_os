# LinkedIn Revenue Department — Architecture Delta V1

Status: **IMPLEMENTATION — OBSERVE / REVIEW-ONLY**

## Purpose

Reverse-engineer the useful operating model behind the common "LinkedIn
department" pattern without cloning another product and without creating an
uncontrolled LinkedIn bot.

The channel loop is:

`ICP -> ACCOUNT RESEARCH -> DECISION MAKER -> OBSERVED SIGNALS -> PRIORITY -> DRAFT -> CONTENT -> FOLLOW-UP -> REPLY -> VERIFIED COMMERCIAL OUTCOME`

This is a channel-specific orchestration layer over existing EmpireOS
intelligence. It is not a second commercial truth system.

## Architecture contract

The implementation MUST reuse canonical EmpireOS primitives:

- ICP / trigger intelligence:
  `empire_os.icp_buyer_trigger_intelligence`
- account / person strategy:
  `empire_os.outreach_account_strategy`
- message optimisation:
  `empire_os.outreach_message_optimizer`
- Predictive Revenue economics:
  `empire_os.predictive_revenue_formula`
- reply classification:
  `empire_os.reply_classifier`
- verified commercial truth remains in EmpireDB and existing commercial
  event/payment/fulfilment paths.

The LinkedIn layer MUST NOT:

- fabricate account, person, signal, contact, budget, intent or revenue evidence;
- turn a public signal into binding buyer intent;
- create a second Predictive Revenue formula;
- send a LinkedIn message, connection request, email, SMS or voice call;
- post content;
- bypass suppression, cooldown, identity or human approval controls;
- mutate the canonical database merely because a channel score is high.

## Nine governed plays

1. **ICP** — assess an observed account against existing ICP profiles.
2. **Account research** — carry source evidence and observed account context.
3. **Decision maker** — rank only explicitly observed people.
4. **Buying signals** — retain only timestamped, evidenced, non-future signals.
5. **Priority** — prefer canonical Expected Revenue Value when available;
   otherwise expose fit/evidence for review without inventing economics.
6. **Personalised outreach** — prepare an evidence-led draft only.
7. **LinkedIn content** — prepare an evidence-only content brief; never auto-post.
8. **Follow-up** — respect suppression, reply state and contact-fatigue policy.
9. **Replies** — classify inbound text without treating content as authority.

## Priority design

V1 deliberately does **not** introduce a new scalar revenue model.

Ranking order:

1. canonical Expected Revenue Value availability;
2. Expected Revenue Value descending;
3. existing ICP fit score;
4. observed signal count;
5. verified-contact readiness;
6. deterministic business-name tie-break.

This keeps channel planning subordinate to Predictive Revenue rather than
creating another uncalibrated "magic score".

## Truth labels

Every packet preserves the following distinctions:

- observed signal != binding buyer intent;
- forecast != revenue;
- reply != revenue;
- meeting != revenue;
- a draft != permission to send;
- a LinkedIn profile != verified contact authority;
- unknown != zero;
- suppression overrides channel recommendations.

## Execution authority

V1 authority is fixed at:

`OBSERVE / REVIEW-ONLY / execution_authority=none`

Future live channel adapters, if ever approved, must remain separate from the
intelligence layer and must add provider/platform policy checks, account-health
controls, rate/cadence limits, suppression enforcement, audit evidence and an
explicit founder authority gate.

## Verification

Focused tests cover:

- fail-closed unknown evidence;
- verified-person + observed-signal drafting;
- future/unevidenced signal rejection;
- unsubscribe/suppression stop behavior;
- canonical ERV-first ranking;
- evidence-only content briefs;
- no live outbound or posting authority.
