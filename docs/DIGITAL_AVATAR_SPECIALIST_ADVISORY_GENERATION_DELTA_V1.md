# Empire Digital Avatar — Grounded Specialist Advisory Generation V1

Date: 2026-10-02
Status: ARCHITECTURE CONTRACT
Change class: Architecture delta

## Purpose

Generate private specialist advisory summaries for an active Digital Avatar
meeting from approved evidence, while preserving one visible avatar and keeping
specialist reasoning separate from evidence/truth.

This layer may perform bounded internal inference. It performs no meeting,
external, commercial or financial action.
## Inputs

Required:
- AvatarSpecialistConsultationPlan;
- AvatarRealtimeResponseTask with matching meeting/avatar identity;
- fully resolved AvatarEvidencePack built from the task's approved refs;
- bounded specialist inference provider.

No unresolved evidence pack may reach inference.
No specialist may receive evidence outside the approved pack.
## Advisory semantics

A generated specialist summary is reasoning guidance, not evidence.

Every advisory must contain:
- domain;
- source component/department;
- concise summary;
- truth_class limited to INFERRED or FORECAST for model-generated reasoning;
- one or more underlying evidence refs drawn only from the supplied evidence
  pack;
- availability/blockers;
- no private chain-of-thought.

OBSERVED/VERIFIED belong to the underlying evidence items, not to the generated
specialist synthesis.
## Telemetry separation

The advisory packet distinguishes:
- inference_performed: whether bounded specialist inference ran;
- inference_provider_key: provider used for reasoning;
- meeting_provider_call_performed=false;
- external_action_performed=false.

Inference is never reported as a meeting-provider action.

Downstream response-context attachment may accept internal inference, but must
continue rejecting meeting-provider actions, speech authority, commercial
authority, financial authority or execution authority.
## Provider contract

The provider receives:
- specialist domain;
- department mission / roles;
- meeting objective;
- buyer/question evidence ref;
- the resolved evidence array.

It returns structured JSON only:
- summary;
- truth_class (INFERRED or FORECAST);
- evidence_refs.

No tool calls, outbound actions, provider meeting calls or chain-of-thought
persistence are permitted.

Provider failure yields an unavailable advisory with a bounded blocker and does
not fabricate a summary.
## Evidence validation

Every returned evidence ref must exist in the resolved evidence pack.
Missing refs, unknown refs or empty summaries make that specialist advisory
unavailable.

The advisory summary itself is never appended to approved_evidence_refs.
Only the advisory's underlying canonical refs may be merged into the response
task.

Unresolved required specialist domains keep specialist_context_ready=false and
the private draft worker must make zero response-model calls.
## Authority

Output is private to owner, single-visible-avatar advisory context.

Always false/none:
- meeting_provider_call_performed;
- external_action_performed;
- specialist_speech_execution_allowed;
- commercial_authority;
- financial_authority;
- execution_authority.

This layer cannot promote SHADOW/COPILOT authority.
## Verification

Required:
- complete evidence pack permits bounded specialist inference;
- incomplete evidence pack results in zero inference calls;
- output truth class restricted to INFERRED/FORECAST;
- unapproved evidence citation blocks advisory;
- provider failure produces unavailable advisory;
- multi-lane plan produces one advisory per selected lane;
- unresolved lane blocks response context;
- internal inference telemetry does not trip meeting-provider action guards;
- full grounded-draft and Avatar regressions remain green.
