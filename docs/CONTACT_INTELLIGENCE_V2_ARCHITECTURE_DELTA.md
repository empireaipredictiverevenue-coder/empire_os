# Contact Intelligence V2 — Architecture Delta

Date: 2026-10-01
Status: IMPLEMENTATION-READY / OBSERVE-FIRST

## Diagram

```text
Discovery / Registry / First-party Site / Existing Canonical Evidence
        -> Company + Person Identity Resolution
        -> Contact Evidence Normalization
        -> Contact Resolution Waterfall
        -> Freshness / TTL / Conflict / Confidence Gate
        -> Enterprise Contact Intelligence / Buyer Review Proposal
        -> Signal + Opportunity Evidence
        -> Opportunity Value / Predictive Revenue
        -> Buyer Capacity / Revenue Distribution
        -> Verified Outcomes -> Cortex / Economic Memory
```

## Purpose

Create one canonical evidence contract for contact resolution so EmpireOS can
combine first-party, registry, historical and provider evidence without creating
a parallel lead database or treating inferred contact data as verified truth.

The component extends the existing evidence-enrichment and enterprise-contact
paths. It does not replace identity resolution, buyer review, outreach,
Predictive Revenue, buyer capacity or Economic Memory.

## Canonical placement

Owner: Predictive Revenue / Lead Intelligence.
Truth store: EmpireDB remains canonical business-data authority.
Upstream: identity_resolver, evidence_enrichment_planner, first-party probes,
registry evidence and already-observed contact evidence.
Downstream: enterprise_contact_intelligence, buyer review proposal, opportunity
evidence and Predictive Revenue scoring.

This slice introduces no database migration and no new external provider.

## Truth contract

Each contact observation carries:
- field/value;
- method and source;
- evidence refs;
- observed_at and optional verified_at;
- expires_at or TTL-derived freshness;
- confidence;
- semantic class: OBSERVED, INFERRED, or VERIFIED;
- conflict information.

Unknown remains unknown. An inferred pattern is never equivalent to a verified
mailbox or a person-bound first-party observation.

## Resolution waterfall

1. Fresh canonical verified person-bound evidence.
2. Fresh first-party person/contact evidence.
3. Fresh authoritative registry evidence where the source supports contact data.
4. Existing observed provider evidence with provenance.
5. Pattern inference as INFERRED only, never as VERIFIED.
6. Expired or conflicting evidence is retained for audit but cannot win.

Resolution is deterministic and evidence-first. Higher confidence cannot bypass
freshness, person binding or semantic-class restrictions.

## Authority

Allowed:
- OBSERVE;
- deterministic internal computation;
- bounded internal-write proposal artifacts in isolated builder worktrees.

Forbidden:
- prospect fabrication;
- person fabrication;
- direct canonical identity mutation;
- buyer approval;
- live outreach;
- terms acceptance;
- allocation or fulfilment;
- payments, settlement or revenue recognition;
- authority expansion.

## Execution model

Pure deterministic library first. No network and no database writes in the core
resolver. Callers provide evidence. Provider adapters remain outside the core.

Idempotency is by normalized observation identity plus evidence refs.
Conflicts fail closed where multiple eligible person-bound values tie.

## Worker assignment

Mutating builder: Empire Coder structured-patch lane.
Owned paths:
- empire_os/contact_resolution.py
- tests/test_contact_resolution.py

Independent verification remains separate from the mutating worker.
The currently modified empire_os/signal_resolver.py is explicitly out of scope.

## Verification

Required:
- focused resolver tests;
- evidence-enrichment regression;
- enterprise-contact regression;
- opportunity-value regression;
- py_compile;
- git diff --check;
- authority/fabrication negative tests.

## Promotion / live verification

Initial live verification is read-only against existing runtime evidence.
No service restart, migration, outbound send or revenue action is required.

DONE evidence for this slice:
architecture delta + scoped implementation + focused/adjacent tests +
independent review + read-only live evidence exercise.

## Commercial fit

The resolver improves usable contact coverage and evidence quality but is not
itself a revenue claim. Economic prioritization remains owned by existing
Opportunity Value / Predictive Revenue contracts. Buyer Capacity Learning stays
recommendation-only and cannot raise verified capacity automatically.
