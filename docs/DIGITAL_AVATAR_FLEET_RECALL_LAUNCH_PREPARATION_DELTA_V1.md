# Empire Digital Avatar — Tenant-Scoped Recall Launch Preparation V1

Date: 2026-10-02
Status: ARCHITECTURE CONTRACT
Change class: Runtime preparation architecture delta

## Purpose

Prepare one already selected tenant-scoped Clone Fleet avatar for a Recall-backed
SHADOW meeting by composing existing canonical bot-plan and session-manifest
owners.

This layer proves the launch inputs are coherent. It does NOT call Recall,
persist the session, create a bot, join a meeting, start output media, speak,
send chat or write canonical commercial truth.

## Inputs

Required:
- trusted zero-authority AvatarFleetRuntimeBinding;
- dispatch-ready AvatarFleetDispatchDecision;
- matching DigitalAvatarIdentity;
- MeetingPlatform;
- public HTTPS meeting_url;
- public HTTPS realtime_webhook_url;
- recording_consent_evidence_ref;
- webhook_verification_evidence_ref;
- account_name;
- objective.

Optional:
- join_at;
- conversation_id;
- opportunity_id;
- proof_refs;
- commercial_terms_ref;
- predictive_inputs;
- action_candidates;
- participant_roles.

V1 accepts SHADOW dispatch only. COPILOT/REPRESENT/NEGOTIATE/CLOSE launch remains
outside this Recall shadow preparation contract.

## Coherence rules

- dispatch.tenant_id == runtime.tenant_id;
- dispatch.selected_avatar_id == runtime.avatar_id;
- dispatch.dispatch_ready == true;
- dispatch requested_mode == shadow;
- dispatch has zero provider/join/speech/commercial/payment authority;
- identity.avatar_id == runtime.avatar_id;
- identity.owner_name == runtime.owner_name;
- identity.owner_consent_evidence_ref == runtime.owner_consent_evidence_ref;
- identity disclosure must explicitly identify AI;
- meeting_id from dispatch is canonical across bot plan + session manifest.

## Canonical composition

1. Build AvatarMeetingSession in SHADOW mode, provider=recall.ai,
   disclosure_announced=false.
2. Build RecallShadowSessionManifest using the canonical session owner.
3. Build RecallShadowBotPlan using the canonical Recall bot-plan builder.
4. Bot name comes from identity.display_name and must visibly identify AI.
5. Validate plan and manifest identities match exactly.

No new Recall request-body construction is allowed in this layer.

## Output

AvatarFleetRecallLaunchPreparation:
- tenant_id;
- meeting_id;
- avatar_id;
- bot_plan;
- session_manifest;
- launch_ready=true;
- recording_consent_evidence_ref;
- webhook_verification_evidence_ref;
- ai_disclosure_required=true;
- disclosure_announced=false;
- recommendation_only=true;
- session_persisted=false;
- provider_call_performed=false;
- bot_created=false;
- meeting_join_performed=false;
- output_media_start_performed=false;
- speech_execution_allowed=false;
- commercial_execution_allowed=false;
- payment_execution_allowed=false;
- revenue_recognition_allowed=false;
- execution_authority=none.

## Media

SHADOW launch does not require voice or visual media. That is deliberate:
observation/transcript intelligence must not be blocked by rendering assets.

Future COPILOT presence activation must separately require
AvatarMultimodalActivationReadiness and its own approval/execution gate.

## Failure behavior

Non-dispatch-ready -> fail closed.
Non-SHADOW dispatch -> fail closed.
Tenant/avatar/owner/consent mismatch -> deny.
Missing recording consent/webhook verification -> canonical builder rejects.
Non-HTTPS meeting/webhook URLs -> canonical builder rejects.
AI-hidden bot name/disclosure -> canonical identity/bot-plan validation rejects.

## Verification

Required:
- valid SHADOW dispatch builds coherent bot plan + manifest;
- dispatch/runtime tenant mismatch denied;
- selected avatar mismatch denied;
- identity owner/consent mismatch denied;
- COPILOT or higher mode rejected;
- AI disclosure preserved in bot name + identity;
- recording/webhook evidence required;
- invalid URL rejected by canonical bot-plan builder;
- no provider/session persistence/join/speech execution;
- full Fleet/Avatar/Recall regression remains green.
