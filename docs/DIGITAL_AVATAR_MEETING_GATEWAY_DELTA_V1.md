# Empire Digital Avatar — Meeting Gateway Delta V1

Date: 2026-10-02
Status: SHADOW FOUNDATION / OBSERVE-ONLY
Parent: DIGITAL_AVATAR_ARCHITECTURE_CONTRACT_V1.md

## Purpose

Add a provider-neutral meeting observation boundary so Digital Avatar can
consume genuine meeting events without coupling EmpireOS to Zoom, Meet, Teams,
Webex or any one bot/transport vendor.

## Flow

MEETING PLATFORM -> VERIFIED PROVIDER ADAPTER -> MEETING OBSERVATION
-> SHADOW MEETING STATE -> DIGITAL AVATAR STRATEGY
-> PRIVATE OWNER GUIDANCE

V1 has no provider credentials, no meeting join, no microphone/video control,
no speech injection and no persistence side effect.

## Canonical placement

- `empire_os.meeting_gateway`: transport-neutral meeting observation contract.
- `empire_os.digital_avatar_shadow`: private guidance composition.
- Conversation OS remains the canonical durable conversation domain.
- Provider-specific schemas stay outside the core until independently verified.
- Existing `digital_twin` market simulation remains unrelated and untouched.

## Truth

Transcript turns are OBSERVED only when accompanied by provider evidence refs.
The gateway does not infer emotion, intent, authority, budget or commitment.
A buyer utterance may be quoted as observed text; any commercial interpretation
remains a separate INFERRED/FORECAST layer.

Provider event IDs are idempotency keys. Conflicting reuse fails closed.
Missing timestamps, meeting identity or evidence refs fail closed.

## Authority

Runtime remains OBSERVE.
Allowed: normalize observations, construct shadow state, prepare private advice.
Forbidden: join meetings, record media, speak, chat, screen-share, invite users,
negotiate, accept terms, send follow-up, request payment or move funds.

## Privacy and identity

Only normalized transcript text and evidence references enter this V1 model.
Raw audio/video and biometric training media are outside this slice.
The owner-visible shadow guidance is private and cannot be emitted to attendees.

## Verification

- deterministic normalization/state tests;
- duplicate/conflict tests;
- private-guidance tests;
- existing Digital Avatar tests;
- py_compile and git diff --check.

Promotion to a real provider adapter requires separate verification of provider
webhook/media schemas, consent/disclosure handling and an explicit live gate.
