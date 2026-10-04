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


## Buyer Scout integration

The first channel feed is the existing Phase 4 Buyer Acquisition Scout snapshot:

`runtime/buyer_acquisition/scout_latest.json`

The adapter intentionally separates three evidence classes:

- **verified buying-committee member** — requires upstream `person_id`,
  `name`, and `evidence_ref`;
- **observed decision-maker candidate** — may preserve a first-party name/title
  for later verification but cannot become the primary contact automatically;
- **observed contact candidate** — first-party email/phone evidence may be shown
  for verification but is not person-bound or send-authorized by this layer.

Observed trigger terms from Buyer Scout can become channel signals only when the
source snapshot has a valid non-future observation timestamp and a first-party
website evidence reference.

## Review packet output

The snapshot exposes:

- ranked account opportunities;
- ICP fit and trigger evidence;
- verified and unverified decision-maker states;
- observed contact candidates;
- signal count, signal diversity and freshest-signal age;
- canonical Expected Revenue Value when evidence is complete;
- evidence-led first-touch drafts;
- content briefs;
- suppression/fatigue/reply sequence state;
- deterministic next research action;
- review-ready counts and predicted ERV totals.

Predicted ERV totals remain forecasts, not booked or recognized revenue.

## Prepared runtime

Source-controlled runtime units are prepared at:

- `deploy/systemd/empire-linkedin-revenue-department.service`
- `deploy/systemd/empire-linkedin-revenue-department.timer`

The service writes only under `/srv/empire_os/runtime`, runs as `ubuntu`,
uses `ProtectSystem=strict`, and does not invoke an outbound provider or
LinkedIn endpoint.

The timer is intentionally bounded to a 30-minute internal refresh cadence.
Adding these unit files to the repository does **not** install, enable, start or
restart them in production. Production activation remains a separate governed
step.
