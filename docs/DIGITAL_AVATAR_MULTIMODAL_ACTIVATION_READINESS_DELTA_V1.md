# Empire Digital Avatar — Multimodal Activation Readiness V1

Date: 2026-10-02
Status: ARCHITECTURE CONTRACT
Change class: Runtime-readiness architecture delta

## Purpose

Determine whether one selected tenant-scoped Digital Avatar clone has the
required validated media identity and compliant local engine capabilities for a
future meeting/render activation.

This layer is readiness only. It performs no rendering, meeting-provider call,
join, output-media start, speech transmission or visual transmission.

## Inputs

Required:
- AvatarFleetMediaBinding;
- requested meeting_id;
- required_media: voice, visual, or multimodal;
- available voice-engine map;
- available visual-engine map.

Optional capability maps may override the current default voice/visual engine
capability registries for tests or controlled deployments.

No raw voice/image media is accepted.

## Voice readiness

Voice is ready only when:
- media binding voice_ready=true;
- profile/hash/engine/engine_voice_id are present;
- selected voice engine exists in the canonical capability registry;
- engine is local_self_hosted=true;
- engine streaming=true;
- clone-capable zero_shot_clone=true for Clone Fleet voice;
- runtime availability map marks the engine available.

This readiness layer does not build a VoiceRenderPlan because that requires a
human-approved speech render task.

## Visual readiness

Visual is ready only when:
- media binding visual_ready=true;
- profile/hash/engine/engine_avatar_id are present;
- selected visual engine exists in the canonical capability registry;
- engine is local_self_hosted=true;
- realtime=true;
- audio_driven=true;
- model_commercial_use=true;
- commercial_ready_by_default=true OR an explicit commercial override is true;
- runtime availability map marks the engine available.

This readiness layer does not build a VisualRenderPlan because that requires an
actual pre-transmission rendered audio artifact.

## Media requirement

- voice: only voice readiness is required.
- visual: only visual readiness is required.
- multimodal: both voice and visual readiness are required.

No fallback engine is silently selected here. The bound engine identity is
validated exactly. Engine fallback remains owned by the canonical render-plan
builder after an approved render task exists.

## Output

AvatarMultimodalActivationReadiness:
- tenant_id;
- avatar_id;
- meeting_id;
- required_media;
- voice_ready;
- visual_ready;
- activation_ready;
- blockers;
- voice_engine;
- visual_engine;
- media_binding_key;
- media_identity_verified=true;
- recommendation_only=true;
- render_execution=false;
- provider_call_performed=false;
- meeting_join_performed=false;
- output_media_start_performed=false;
- speech_execution_allowed=false;
- visual_execution_allowed=false;
- commercial/payment/revenue authority=false;
- execution_authority=none.

## Failure behavior

Unknown required_media -> fail validation.
Missing required profile -> blocker.
Unsupported/unavailable/noncompliant bound engine -> blocker.
Binding authority invariant violation -> fail closed.
Readiness never substitutes another avatar or profile.

## Verification

Required:
- voice-only ready with compliant available clone engine;
- visual-only ready with compliant available commercial engine;
- multimodal requires both;
- unavailable engine blocks;
- generic non-clone TTS blocks Clone Fleet voice;
- noncommercial/non-audio-driven visual engine blocks;
- media binding authority violation blocks;
- no provider/render/speech execution;
- full Fleet/Avatar regression remains green.
