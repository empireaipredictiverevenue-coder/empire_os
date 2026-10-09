# EmpireOS Outbound Department V1

Status: ISOLATED BUILD CANDIDATE / NO LIVE SEND / NO AUTHORITY EXPANSION

## Purpose

Outbound is a first-class operating department whose job is to turn verified prospects into trusted commercial conversations.

Canonical commercial flow:

VERIFIED PROSPECT → RESEARCH → RELEVANCE → RAPPORT → VALUE → NURTURE → ENGAGEMENT → CONVERSATION → EXISTING CLOSER → EXISTING COMMERCIAL PROCESS

## Canonical reuse

This coordinator does not create another sender, CRM, reply ledger, conversation store, scheduler, adaptive optimizer, governor, mailbox provider, Economic Memory or revenue engine.

It reuses:
- Buyer Review for prospect/review evidence.
- Outbound Governor for external-action authority.
- Conversation OS and existing reply/closer paths for engagement.
- Outreach Message Optimizer's existing human-copy gate.
- Adaptive Outreach Optimizer for copy-arm learning.
- Astra as advisory director intelligence.

## Authority

The planner is pure and side-effect-free.

Astra may propose a next action but cannot grant send authority, terms authority, payment authority or revenue-recognition authority.

Every V1 plan returns execution_authority=none.

## Relationship states

COLD_VERIFIED
RAPPORT_STARTED
RAPPORT_BUILDING
VALUE_ESTABLISHED
ENGAGED
CONVERSATION
COMMERCIAL_READY
SUPPRESSED

## Next actions

RESEARCH
WAIT
DRAFT_RAPPORT_TOUCH
DRAFT_VALUE_TOUCH
DRAFT_NURTURE_TOUCH
DRAFT_SOFT_CONVERSATION_OPENER
HANDOFF_TO_CLOSER
SUPPRESS
BLOCK

## Messaging rules

First touch is rapport/relevance only. No CTA, price, meeting, calendar or demo ask.

Touch 2 and Touch 3 require genuinely new verified account-bound evidence.

A soft conversational opener is permitted only after the deterministic VALUE_ESTABLISHED process state.

Any substantive real reply stops nurture and hands the account to the existing closer.

## Hard copy blockers

GENERIC_OPENER
EMPTY_PERSONALIZATION
AI_SLOP_PHRASE
UNSUPPORTED_CLAIM
FAKE_FAMILIARITY
REPEATED_INSIGHT
PREMATURE_CTA
PREMATURE_PRICE
ROLE_INBOX_PERSONHOOD_CLAIM
UNVERIFIED_COMPANY_SHORTENING

Early touches require the exact verified company name.

A company-routed inbox remains person_bound=false. A routing target may be named, but the mailbox must never be represented as that person's personal address.

## Evidence

Personalised claims require fresh, verified, account-bound evidence with an evidence reference.

Missing, stale, contradicted or already-used evidence routes to RESEARCH rather than invented copy.

## Learning

The planner exposes strategy_id, relationship_stage, touch_number, touch_purpose, evidence refs and contact route for downstream verified-outcome learning.

Opens, clicks, replies and meetings are not recognized revenue.

## Canonical reply branching

The canonical reply classifier uses positive, negative, question, objection,
later, unsubscribe, bounce and other states.

positive/question/objection progress to the existing closer.
later/negative/unclassified genuine replies stop automated nurture and wait for
the canonical reply/conversation path rather than inventing closer work.
unsubscribe suppresses.

## Company-name progression

Touches 1-3 require the full verified company name.

After rapport exists, natural references such as "your team" or "the business"
are permitted. A shortened brand name remains blocked unless canonical evidence
or the prospect's own language verifies that shortening.

## Runtime boundary

V1 is an offline-proven planning and copy-governance coordinator. It does not
create a scheduler, sender or live runtime bridge. Runtime activation remains a
separate governed integration step after this implementation candidate passes
promotion review.

## Soft conversation CTA boundary

VALUE_ESTABLISHED does not permit a hard sales CTA.

The permitted next step is a low-friction conversation opener such as:
"If useful, I can show you what we're seeing."

Meeting requests, booking links, calendar asks, demo asks, timed-call asks and
similar hard CTAs remain blocked until the existing conversation/closer path
owns the interaction.
