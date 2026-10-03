# Empire Digital Avatar — Specialist Response Context Delta V1

Date: 2026-10-02
Status: PLANNING / COPILOT-PREVIEW ONLY
Change class: Architecture delta

## Purpose

Feed validated internal specialist advice into the Digital Avatar response
pipeline without allowing a specialist summary to masquerade as canonical
evidence.

Specialists may guide reasoning. Buyer-facing factual claims must still cite
underlying approved evidence resolved through the existing evidence pack.
## Flow

```text
MEETING ADVISORY PACKET
  -> IDENTITY / AUTHORITY CHECK
  -> ATTACH ADVISORY SUMMARIES TO RESPONSE TASK
  -> UNION UNDERLYING SPECIALIST EVIDENCE REFS
  -> RESOLVE ALL APPROVED EVIDENCE
  -> PRIVATE GROUNDED DRAFT
  -> CLAIM VALIDATION AGAINST APPROVED REFS
  -> HUMAN REVIEW
```

No specialist summary receives its own evidence ref in this adapter.
## Response-task extension

AvatarRealtimeResponseTask gains:
- specialist_context: structured audit-safe advisory summaries;
- specialist_context_ready: boolean;
- specialist_context_blockers: unresolved required domains.

The existing approved_evidence_refs field remains the only allowlist for factual
claim citations. Specialist advisory evidence refs are added to that allowlist,
then must resolve through canonical evidence adapters before drafting.
## Drafting rules

If specialist_context_ready is false:
- private draft status becomes blocked_specialist_context;
- provider/model call count remains zero;
- no draft is produced.

When ready, the grounded provider receives specialist_context separately from
the resolved evidence array. The system prompt explicitly treats advisory
summaries as reasoning guidance only.

Every material buyer-facing claim still requires evidence_refs from the resolved
approved evidence set. Invented specialist-summary refs fail normal draft
validation.
## Authority and truth

Specialist truth labels remain OBSERVED / VERIFIED / INFERRED / FORECAST.
No adapter upgrades a truth class.

This delta performs no:
- speech;
- chat send;
- provider call;
- commercial mutation;
- payment;
- funds movement;
- revenue recognition.

Execution authority remains none.
## Verification

Required:
- ready advisory packet attaches summaries and underlying evidence refs;
- unresolved advisory packet blocks before model call;
- meeting/avatar mismatch rejected;
- advisory summary is not turned into an evidence item/ref;
- grounded provider receives both separate advisory context and resolved evidence;
- model citation outside approved refs remains blocked;
- dedupe digest changes when specialist context changes;
- existing private-draft and Avatar regressions remain green.

## Optional guidance integration

The Recall SHADOW guidance builder may accept an already-validated
AvatarMeetingAdvisoryPacket object. It does not discover or load specialist
state by itself in V1. Absence of a packet preserves the existing response-task
path unchanged. Runtime storage/discovery of specialist packets requires a
separate architecture delta.
