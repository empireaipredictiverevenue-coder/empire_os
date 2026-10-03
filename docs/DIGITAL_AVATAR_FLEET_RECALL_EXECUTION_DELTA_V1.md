# Empire Digital Avatar — Fleet-Scoped Recall Live Execution Adapter V1

Date: 2026-10-02
Status: ARCHITECTURE CONTRACT
Change class: External-execution architecture delta

## Purpose

Provide the tenant-aware final adapter into the existing one-time Recall SHADOW
executor.

This is the first Clone Fleet layer capable of causing a real external meeting
join when invoked. Building/testing it does not authorize production execution.

## Required gates

Execution requires ALL of:
- AvatarFleetRecallActivationPreparation;
- matching AvatarFleetRecallMaterialization;
- explicit live_execution_requested=true;
- non-empty Recall API key;
- still-active meeting-bound RecallShadowJoinApproval embedded in the packet;
- canonical materialized execution_state=prepared;
- exact activation plan fingerprint match.

The boolean is an accidental-execution guard only. It does not replace or weaken
the existing owner approval evidence/time window.

## Tenant/materialization coherence

Before calling the canonical executor:
- preparation tenant/meeting/avatar must equal materialization;
- materialization tenant_scope_key must equal deterministic hash of tenant_id;
- activation_root must end at that exact tenant scope;
- activation record plan_sha256 must equal canonical activation_plan_sha256;
- record must still be prepared and not provider-called/joined.

## Canonical execution

Delegate to execute_materialized_recall_shadow_activation().

Do not duplicate:
- provider API request logic;
- approval revalidation;
- retry handling;
- one-time state transition;
- reconciliation-required behavior.

## Output on successful fake/real provider completion

AvatarFleetRecallExecutionResult:
- tenant_id;
- meeting_id;
- avatar_id;
- tenant_scope_key;
- bot_id;
- provider_status;
- activation_plan_sha256;
- execution_state=completed;
- provider_call_performed=true;
- meeting_join_performed=true;
- speech/chat/commercial/payment/revenue execution=false;
- execution_authority=shadow_join_only_completed.

## Failure behavior

live_execution_requested != true -> block before provider.
Tenant/scope/fingerprint mismatch -> block before provider.
Expired approval -> canonical provider boundary blocks before transport.
Missing API key -> canonical provider boundary blocks.
Second execution -> canonical materialized executor blocks.
Ambiguous transport failure -> canonical record becomes reconciliation_required;
never blind retry.

## Production gate

Do not invoke this adapter against live Recall from a generic "continue".
A live execution requires an explicit meeting-bound approval supplied through the
existing RecallShadowJoinApproval evidence path.

## Verification

Use fake transport only:
- default-off execution performs zero provider calls;
- valid scoped activation executes exactly once;
- replay blocked;
- scope/fingerprint mismatch blocked before transport;
- expired approval rechecked before transport;
- ambiguous failure writes reconciliation_required;
- speech/chat/commercial authority stays false;
- full Fleet/Avatar/Recall regression remains green.
