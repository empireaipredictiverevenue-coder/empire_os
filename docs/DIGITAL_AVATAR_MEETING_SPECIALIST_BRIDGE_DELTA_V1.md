# Empire Digital Avatar — Meeting Specialist Bridge Delta V1

Date: 2026-10-02
Status: PLANNING / OBSERVE-ONLY
Change class: Architecture delta

## Purpose

Let one visible Digital Avatar use Empire specialist intelligence during a B2B
meeting without creating multiple speaking agents or parallel authority paths.

The visible avatar remains the sole response owner. Specialists provide internal
structured advisory summaries only.
## Flow

```text
DISPATCH-READY AVATAR
  -> EXPLICIT REQUIRED ADVISORY DOMAINS
  -> EXISTING EMPIRE SPECIALIST OUTPUTS
  -> SPECIALIST SAFETY / EVIDENCE VALIDATION
  -> SINGLE MEETING ADVISORY PACKET
  -> GROUNDED RESPONSE TASK / DRAFT
  -> ONE VISIBLE AVATAR RESPONSE
```

Existing specialist modules remain canonical owners of their intelligence.
This bridge does not duplicate Predictive Revenue, Product, Pricing, Closer,
Technical or Cortex logic.
## Advisory contract

Each specialist advisory contains:
- domain;
- source_component;
- concise audit-safe summary;
- truth_class;
- evidence_refs;
- available/unavailable state;
- blockers when unavailable;
- execution_authority=none;
- external_action_performed=false.

Available advisory content must carry at least one evidence ref.
Private chain-of-thought is never accepted or persisted.
## Single-voice rule

Exactly one avatar_id owns the meeting-facing response.

Specialists may not:
- speak to the meeting;
- send chat;
- call a meeting provider;
- accept terms;
- quote outside the existing commercial evidence path;
- request payment;
- move funds;
- recognize revenue;
- expand their own authority.

The bridge may only prepare internal response context for the selected avatar.
## Domain ownership and ambiguity

Required advisory domains are explicit input, never guessed from sensitive
personal traits.

V1 accepts at most one canonical advisory packet per domain. Duplicate packets
for one domain fail closed as specialist_owner_ambiguous.

A requested domain that is missing or unavailable is returned as unresolved.
The bridge may still emit partial internal context, but response_context_ready
is false until all required domains are available.
## Truth and safety

Allowed truth classes:
- OBSERVED;
- VERIFIED;
- INFERRED;
- FORECAST.

INFERRED/FORECAST summaries must remain labelled and evidence-backed.
No specialist summary upgrades itself to VERIFIED.

Any packet claiming external action, commercial authority, financial authority,
or non-none execution authority is rejected before it reaches the avatar.
## Verification

Required:
- all requested domains available -> response_context_ready;
- missing/unavailable domain -> unresolved;
- duplicate domain -> fail closed;
- advisory without evidence -> invalid;
- authority-bearing advisory -> rejected;
- truth class preserved;
- deterministic domain ordering;
- single visible avatar invariant;
- no speech/provider/commercial side effects;
- adjacent Avatar/Fleet regressions remain green.
