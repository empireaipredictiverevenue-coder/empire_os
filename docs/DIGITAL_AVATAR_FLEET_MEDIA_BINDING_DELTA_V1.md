# Empire Digital Avatar — Tenant-Scoped Multimodal Media Binding V1

Date: 2026-10-02
Status: ARCHITECTURE CONTRACT
Change class: Security/control-plane architecture delta

## Purpose

Bind existing consent-verified Digital Avatar voice and visual registrations to
a validated tenant/avatar fleet runtime so multimodal clone assets cannot bleed
between tenants or identities.

This layer does not clone media, store raw media, render speech/video or grant
meeting transmission authority.

## Existing owners reused

Canonical profile-registration owners remain:
- digital_avatar_voice_registry.py
- digital_avatar_visual_registry.py
- DigitalAvatarIdentity

Clone Fleet adds only a tenant/avatar binding above those immutable
registrations.

## Input contract

Required:
- validated AvatarFleetRuntimeBinding;
- matching DigitalAvatarIdentity;
- zero or one AvatarVoiceRegistration;
- zero or one AvatarVisualRegistration.

At least one media registration is required.

For each supplied registration:
- registration.avatar_id == runtime/identity avatar_id;
- registration.profile_ref == matching identity profile ref;
- registration.owner_consent_evidence_ref == identity consent ref;
- modality-specific consent evidence ref is non-empty;
- profile SHA256 is non-empty;
- raw_reference_media_stored == false;
- meeting_transmission_authority == false;
- execution_authority == none.

If identity declares a voice/visual profile ref, the corresponding registration
must be supplied. A registration may not be supplied when identity has no
matching ref.

## Output contract

Tenant-scoped media binding may expose:
- tenant_id;
- avatar_id;
- owner_name;
- owner-consent evidence ref;
- voice profile ref/hash/engine/language;
- visual profile ref/hash/engine/target_fps;
- consent_verified flags.

It does not expose:
- reference audio refs;
- transcript refs;
- source image refs;
- raw media bytes;
- meeting/provider secrets.

## Reuse/isolation

V1 profile ownership key is the immutable profile_ref.

The same voice_profile_ref or visual_profile_ref may be repeated only for the
same tenant + avatar + identical media binding.

Reusing the same profile ref for another avatar or another tenant fails closed.

If one human needs multiple business roles, use one avatar identity with
multiple validated capability labels rather than silently duplicating protected
voice/face assets across avatar IDs.

A future explicit shared-identity contract may relax this; V1 does not.

## Authority

Always:
- media_binding_only=true;
- raw_reference_media_included=false;
- render_execution=false;
- meeting_transmission_authority=false;
- speech_execution_allowed=false;
- visual_execution_allowed=false;
- commercial/payment/revenue authority=false;
- execution_authority=none.

The existing one-turn speech ticket and Presence runtime remain the only
governed speech path.

## Persistence

V1 is deterministic/in-memory only.
No tenant database schema, Migration 018 change, legacy SQLite fallback or raw
media persistence is introduced.

## Verification

Required:
- voice-only binding valid;
- visual-only binding valid;
- voice+visual binding valid;
- runtime/identity avatar or owner-consent mismatch rejected;
- profile-ref mismatch rejected;
- missing declared registration rejected;
- raw-media/transmission/authority-bearing registration rejected;
- protected refs not exposed in output;
- exact duplicate binding idempotent;
- profile reuse across avatar/tenant fails closed;
- full Fleet/Avatar regression remains green.
