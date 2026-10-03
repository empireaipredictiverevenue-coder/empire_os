# Empire Digital Avatar — Clone Fleet Continuity Memory Delta V1

Date: 2026-10-02
Status: ARCHITECTURE CONTRACT
Change class: Architecture delta

## Purpose

Give each authorised clone continuity across meetings without creating a second
memory database, leaking other tenants, or promoting observed conversation
history into verified commercial proof.

This layer projects existing evidence-preserving meeting outcomes into a bounded
tenant/avatar-specific continuity context.
## Canonical sources

Reused sources:
- Digital Avatar meeting observations/memory;
- Digital Avatar meeting outcome packets;
- canonical commercial outcomes / Cortex / Economic Memory for separately
  verified outcome-conditioned learning.

Clone continuity does not write Cortex, Economic Memory, commercial outcomes or
revenue truth.

Because current Recall session manifests are not tenant-keyed, a trusted fleet
control-plane wrapper must explicitly bind each source packet to tenant_id and
avatar_id before it may enter continuity memory.
## Truth separation

Meeting history is OBSERVED continuity evidence.

It may contain:
- meeting/account identity;
- conversation/opportunity references;
- buyer utterance count;
- close-ready-at-end observation;
- human-takeover flag;
- recommended follow-up/predictive refresh;
- evidence and verification refs.

It is NOT automatically:
- a verified customer result;
- a case study;
- recognized revenue;
- proof of causal effectiveness;
- permission to retrain model weights.

Only an outcome already marked verified by the canonical commercial-outcome
lane may be flagged commercial_proof_eligible.
## Tenant / clone isolation

Memory retrieval requires:
- active authenticated TenantMembership with operate permission;
- matching validated AvatarFleetRuntimeBinding;
- source tenant_id == runtime.tenant_id;
- source avatar_id == runtime.avatar_id.

Other-tenant/different-avatar sources are ignored.
The same avatar_id observed under another tenant is an integrity conflict and
fails closed.

Other avatars in the same tenant do not bleed into clone-specific continuity.
## Privacy and bounded context

V1 stores/projects no raw audio and no raw transcript text.
It uses outcome metadata and evidence refs only.

Default maximum continuity entries is bounded by caller policy; V1 accepts
1..100 entries.

Projection is deterministic, newest-first by evidence observation time, with
stable meeting_id tie-break.
## Authority

Output:
- mode=OBSERVE;
- private_to_owner=true;
- truth_class=OBSERVED_CONTINUITY;
- raw_transcript_included=false;
- model_inference_performed=false;
- canonical_write_performed=false;
- speech/commercial/payment/revenue authority=false;
- execution_authority=none.

Continuity memory may inform future grounded response tasks but cannot itself
authorize a factual claim; material claims must still resolve through the
canonical evidence pack.
## Verification

Required:
- own clone history projected newest-first;
- own tenant other-avatar history excluded;
- other-tenant history excluded;
- same avatar_id under another tenant fails closed;
- disabled/viewer membership cannot build runtime continuity;
- runtime tenant/member mismatch denied;
- raw transcript content absent;
- observed history not marked commercial proof;
- explicitly verified commercial outcome may be flagged proof-eligible;
- bounded max entries enforced;
- full fleet/Avatar regressions remain green.
