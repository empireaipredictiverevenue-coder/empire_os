# Empire Digital Avatar — Tenant-Scoped Multimodal Media Binding V1

Date: 2026-10-02
Status: ARCHITECTURE CONTRACT
Change class: Identity/control-plane architecture delta

## Purpose

Bind an already validated tenant/avatar runtime to existing immutable Digital
Avatar voice and visual registrations without allowing a voice/face profile to
bleed across tenants, avatars or owners.

This layer does not create clone media, register profiles, upload raw media,
speak, render video or call a meeting provider.

## Canonical owners reused

- DigitalAvatarIdentity owns avatar/person/disclosure identity.
- AvatarFleetRuntimeBinding owns tenant/avatar/owner-consent coherence.
- AvatarVoiceRegistration owns immutable voice-profile registration.
- AvatarVisualRegistration owns immutable visual-profile registration.

This layer only composes those facts into a tenant-scoped multimodal binding.

## Supported shapes

V1 supports:
- voice-only;
- visual-only;
- voice + visual.

At least one media registration is required.

## Required invariants

For every supplied media registration:
- registration.avatar_id == runtime.avatar_id;
- registration.avatar_id == identity.avatar_id;
- registration.owner_consent_evidence_ref ==
  runtime.owner_consent_evidence_ref;
- registration.owner_consent_evidence_ref ==
  identity.owner_consent_evidence_ref;
- registration execution_authority == none;
- registration meeting_transmission_authority == false;
- raw_reference_media_stored == false;
- profile hash is present;
- supplied profile_ref matches identity.voice_profile_ref or
  identity.visual_profile_ref respectively.

Identity owner_name must match runtime.owner_name.

## Tenant isolation / uniqueness

A MultimodalMediaBinding is explicitly tenant-scoped.

When multiple existing bindings are supplied for conflict review:
- the same voice profile_ref may not belong to another tenant/avatar;
- the same visual profile_ref may not belong to another tenant/avatar;
- the same engine_voice_id may not be bound to a different tenant/avatar;
- the same engine_avatar_id may not be bound to a different tenant/avatar.

Exact duplicate bindings are idempotent.

V1 does not support shared voice/visual identities across tenants. A future
explicit media-sharing contract would require a separate architecture gate.

## Output

AvatarFleetMediaBinding:
- tenant_id;
- avatar_id;
- owner_ref;
- owner_name;
- owner_consent_evidence_ref;
- voice_profile_ref / voice_profile_sha256 / engine_voice_id when present;
- visual_profile_ref / visual_profile_sha256 / engine_avatar_id when present;
- multimodal_ready;
- voice_ready;
- visual_ready;
- binding_key;
- raw_reference_media_stored=false;
- provider_call_performed=false;
- media_generation_performed=false;
- meeting_transmission_authority=false;
- speech_execution_allowed=false;
- commercial_execution_allowed=false;
- payment_execution_allowed=false;
- execution_authority=none.

## Idempotency

binding_key is deterministic from:
tenant_id + avatar_id + voice profile/hash + visual profile/hash.

This is an identity binding key only. It is not a provider token and grants no
meeting or rendering authority.

## Failure behavior

Missing all media -> fail closed.
Runtime/identity mismatch -> deny.
Consent mismatch -> deny.
Voice or visual profile mismatch -> deny.
Authority-bearing registration -> deny.
Cross-tenant/avatar reuse of profile/engine identity -> fail closed.
No fallback to another avatar/profile is permitted.

## Verification

Required:
- voice-only binding succeeds;
- visual-only binding succeeds;
- voice+visual binding succeeds;
- runtime/identity/owner/consent mismatch denied;
- profile ref mismatch denied;
- authority-bearing registration denied;
- same profile reused cross-tenant fails closed;
- same engine id reused cross-avatar fails closed;
- exact duplicate is idempotent;
- output contains no raw media and zero execution authority;
- full Fleet/Avatar regression remains green.
