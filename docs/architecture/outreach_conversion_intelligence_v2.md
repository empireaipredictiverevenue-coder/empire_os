# Outreach Conversion Intelligence V2 — offline architecture delta

Diagram: canonical evidence → conversation_value freshness gate → existing
message optimizer (structure + persuasion + alignment) → existing GTM copy
selection → governed outbound gates (unchanged).
Canonical classified replies → existing adaptive snapshot → engagement learning.
Existing verified outcome feedback → existing validator → downstream learning.

Contract: proof is not timing evidence. Missing/stale/future timing evidence
remains unknown; proof-backed drafts remain permitted. Alignment unknowns are
reported and limit persuasion; explicit contradictions block experiments.
Scores never confer send or commercial authority. Thresholds remain 8 per arm,
16 per segment, 20% exploration. Existing Economic Memory owns outcome memory.
Worker assignment: Codex implements the existing owners and focused offline tests.
Independent verification: regression tests, authority boundary tests, diff review.
Live verification: excluded by task; no production improvement claim.

## Verification and checklist

- 22 new offline test cases; 162 existing related regressions: 184 passed.
- Changed Python owners compiled; git diff --check passed.
- AST comparison against HEAD: only build_outbound_payload changed in GTM;
  runtime authority functions unchanged. Recovery, follow-up worker, classifier,
  mailbox, outbound governor and executor have no diff against HEAD.
- Migration 018 SHA256 remains
  e7edcfe1d0f94c3898437e68db0714557370b7b86f9b21ee76cc04be60bc3c21.
- No production send, database write, service/timer restart, staging, branch
  switch, reset or clean. Existing dirty work preserved.
- Live verification intentionally excluded by CODE + TEST ONLY scope.

Behavior: eight quality dimensions; score retains structural compatibility;
commercial_persuasion_score is independently capped at 74 without timing and
79 with unknown alignment. Alignment support needs a supplied evidence reference;
explicit contradictions and unsupported urgency/intent block experiments.
Timing provenance retains canonical timestamps, freshness, confidence and
observed/inferred state; omitted states remain unknown.

Proof-backed copy remains eligible. Freshness continues through the existing
conversation_value gate. Commercial engagement, positive intent, negative reply
and unsubscribe counts are distinct. Downstream counts accept the existing
verified outcome feedback validator, tenant scope and explicit order attribution;
raw flags, predictions and reply labels never supply revenue evidence.
Repeated identified intents/outcomes cannot inflate verified outcome counts.

Known data-quality gaps: the current runtime snapshot reader does not supply
verified downstream feedback or qualified-conversation/commercial-terms records.
Those counts are observed verified counts, not assertions that no real outcomes
exist. unavailable_stage_sources explicitly reports unsupported stage sources.
Existing Economic Memory and Predictive Revenue remain the canonical economic
learning owners; no new memory, event bus or live query path was added.
Alignment absent from canonical context stays UNKNOWN; the scorer does not
invent buyer problems, offer fit, Empire differentiation or purchase timing.
Locale/timezone and supplied problem/trigger/proof context extend segment keys;
CTA and follow-up dimensions are accepted only when supplied. Subject/body
strategies remain the existing arm IDs. Sparse evidence falls back globally.

OUTREACH CONVERSION INTELLIGENCE V2 = PROVEN OFFLINE / CODE LEVEL.
Production conversion improvement remains unproven.
