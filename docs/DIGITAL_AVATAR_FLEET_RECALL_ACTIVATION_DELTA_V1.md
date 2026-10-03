# Empire Digital Avatar — Fleet-Scoped Recall Activation Wrapper V1

Date: 2026-10-02
Status: ARCHITECTURE CONTRACT
Change class: Runtime activation architecture delta

## Purpose

Bind an already prepared tenant-scoped Clone Fleet Recall launch to the existing
time-bounded Recall SHADOW approval/activation packet without duplicating join,
provider, activation-store or execution logic.

This layer remains pre-execution. It does not persist activation state and does
not call Recall.

## Canonical owners reused

- AvatarFleetRecallLaunchPreparation owns tenant/avatar launch coherence.
- RecallShadowJoinApproval owns explicit time-bounded live-join approval.
- prepare_recall_shadow_join owns approval/region validation.
- RecallShadowActivationPacket owns the governed SHADOW activation packet.
- recall_shadow_activation_store owns materialization.
- recall_shadow_execution owns one-time provider execution.

No new provider client, approval format or activation persistence is introduced.

## Inputs

Required:
- zero-authority AvatarFleetRuntimeBinding;
- AvatarFleetRecallLaunchPreparation;
- RecallShadowJoinApproval;
- approved Recall region;
- current timestamp.

## Fleet coherence

The wrapper must prove:
- runtime.tenant_id == launch.tenant_id;
- runtime.avatar_id == launch.avatar_id;
- runtime.avatar_id == launch.bot_plan.avatar_id;
- runtime.avatar_id == launch.session_manifest.identity.avatar_id;
- runtime owner_name/consent match launch identity;
- launch.launch_ready == true;
- launch provider/session/join/output flags remain false;
- bot plan is SHADOW/no-output/no authority;
- approval meeting_id == launch.meeting_id;
- approval approved_by == runtime.owner_name;
- approval is active now;
- region is accepted by canonical Recall join policy.

## Output

AvatarFleetRecallActivationPreparation:
- tenant_id;
- meeting_id;
- avatar_id;
- activation_packet;
- approval_evidence_ref;
- approved_by;
- region;
- activation_ready=true;
- fleet_scope_verified=true;
- live_join_authorized=true;
- activation_persisted=false;
- provider_call_performed=false;
- bot_created=false;
- meeting_join_performed=false;
- speech/chat/commercial/payment/revenue execution=false;
- execution_authority=shadow_join_only_pending_execution.

The nested canonical activation packet retains its existing
execution_authority=shadow_join_only. The wrapper's authority label makes clear
that the permission is prepared but not yet executed.

## Irreversible gate

Creating this preparation does not itself approve a meeting. A valid
RecallShadowJoinApproval must already be supplied.

Execution remains exclusively owned by
execute_materialized_recall_shadow_activation after canonical materialization.
Do not call that execution function from this wrapper.

## Failure behavior

Cross-tenant/runtime mismatch -> deny.
Owner/consent mismatch -> deny.
Expired/future/incomplete approval -> canonical join validation rejects.
Approval owner mismatch -> deny.
Approval for another meeting -> deny.
Any launch/provider/execution state already active -> fail closed.
Any speech/chat/commercial authority -> fail closed.

## Verification

Required:
- matching fleet launch + active owner approval yields activation preparation;
- tenant/avatar/owner/consent mismatch denied;
- wrong/expired approval denied;
- approval owner mismatch denied;
- canonical region validation preserved;
- nested packet fingerprints same bot plan/session manifest;
- no activation store write;
- no provider call/join execution;
- full Fleet/Avatar/Recall regression remains green.
