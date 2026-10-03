# Empire Digital Avatar — Architecture Contract V1

Date: 2026-10-02
Status: FOUNDATION / OBSERVE-ONLY
Change class: Architecture change

## Diagram

MEETING PROVIDER -> MEETING GATEWAY -> DIGITAL AVATAR
-> REALTIME CONVERSATION -> AVATAR ORCHESTRATOR
-> EMPIRE SPECIALIST AGENTS -> EMPIREOS INTELLIGENCE
-> AUTHORITY ENGINE -> RESPONSE / ACTION PREVIEW
-> COMMERCIAL OUTCOME EVIDENCE -> CORTEX

## Purpose

Digital Avatar is an authorised, disclosed AI representative of a real person.
It may eventually attend B2B meetings, listen, speak, demonstrate products,
negotiate within delegated limits, close governed deals and trigger follow-up.
V1 does not activate any external meeting or commercial execution.

## Canonical placement

Domain: `empire_os.digital_avatar`.
Owning business layer: Conversation OS / Revenue OS.
Inputs: verified human-avatar consent, meeting context, business evidence,
Predictive Revenue outputs, closer context and approved commercial terms.
Digital Avatar is distinct from Phase 14 `digital_twin`, which models markets.

## Truth and data contract

Identity, consent and authority are VERIFIED evidence or UNKNOWN.
Meeting utterances are OBSERVED provider evidence when later integrated.
Scores and next-action recommendations are INFERRED or FORECAST.
Actual revenue remains governed verified commercial evidence only.
V1 adds no database migration and no new source of canonical commercial truth.

## Authority contract

Runtime authority: OBSERVE.
V1 can validate identity, disclosure, meeting state and proposed actions.
External speech, meeting join, outbound follow-up, negotiation, contract
acceptance, payment request, funds movement and revenue recognition are blocked.
No avatar may expand its own authority.
Binding actions outside delegated policy require a founder/human gate.

## Identity and disclosure

Every human-linked avatar requires explicit owner consent evidence.
A meeting-facing avatar must disclose that it is an AI representative.
Raw voice/face training media is not stored in this domain model; provider
references and consent evidence are referenced by ID only.

## Execution model

Provider-agnostic deterministic core first.
Meeting transport, realtime voice/video and renderer are adapters.
Idempotency keys will be provider event IDs plus canonical meeting/session IDs.
Provider loss fails closed: no invented transcript, action or commercial state.

## Agent and tool ownership

Astra coordinates priorities; it does not gain new business authority.
Visible avatar may consult Closer, Pricing, Product, Technical, Evidence and
Predictive Revenue specialists, but one orchestrator owns the final response.
Builder lane: deterministic production code for V1.
Verifier lane: focused pytest, py_compile and git diff checks.
No mutating worker may overlap the current Search Command Centre file lease.

## Observability

Future events: avatar_session_opened, disclosure_recorded, turn_observed,
action_proposed, authority_blocked, human_takeover, session_closed.
Every commercial recommendation carries evidence refs and truth class.
No hidden action may be represented as executed.

## Verification and promotion

V1 DONE: architecture contract + deterministic domain + focused tests.
V2: read/preview API and meeting strategy packet.
V3: shadow-mode provider adapter with no speaking authority.
V4: copilot speech under explicit human control.
V5+: bounded represent/negotiate/close only after separate founder approval.

## Commercial fit

The avatar turns existing Empire intelligence into an interactive B2B surface.
Primary proof: “Meet Phil’s Digital Avatar” uses Empire intelligence to answer,
demonstrate, handle objections and prepare an approved commercial next step.
Killer-demo close: “Everything you’ve just experienced is what Empire AI can
deploy for your organisation.”


## Implemented foundation — 2026-10-02

Local/OBSERVE foundation now includes:
- provider-neutral Digital Avatar identity and meeting modes;
- deterministic action and delegated commercial authority gates;
- provider-neutral meeting observation gateway;
- evidence-preserving meeting memory;
- private shadow guidance using Predictive Revenue next-best-action value;
- verified Recall event normalisation and non-executing shadow bot plan;
- verified Recall event -> memory -> guidance -> response-task pipeline;
- grounded realtime response-task contract;
- structured private response-draft validation against approved evidence only;
- non-transmitting Copilot human-approval handoff packet;
- fail-closed single-step mode-transition policy.

All live meeting join, speech, chat send, contract acceptance, payment, funds
movement and revenue-recognition authority remains disabled.


## Promotion ladder

1. SHADOW — observe verified meeting evidence and advise owner privately.
2. COPILOT — prepare grounded response drafts for explicit human approval.
3. REPRESENT — future speaking representation after disclosure and authority proof.
4. NEGOTIATE — future bounded negotiation after delegated commercial authority.
5. CLOSE — future governed close only inside verified commercial terms.

Transitions must be single-step. Direct SHADOW -> REPRESENT/NEGOTIATE/CLOSE
promotion is blocked. Any mode may fail safe back to SHADOW.

The current codebase implements stages 1 and the non-transmitting preparation
surface for stage 2. It does not activate stage 2 speech or stages 3-5 execution.


## Recall ingress security — verified 2026-10-02

Production Recall ingress must use the raw HTTP body and workspace verification
secret to verify the Recall HMAC headers before parsing or processing payloads.
Unverified requests fail closed and must not reach meeting state.

Prepared modules:
- `recall_webhook_verification.py`: HMAC-SHA256 verification evidence;
- `recall_verified_ingress.py`: verify -> parse -> normalize ordering;
- `recall_webhook_api.py`: minimal verify -> enqueue -> immediate response API.

The webhook router is intentionally not mounted or activated in production yet.
Secret provisioning, public route activation and service restart remain explicit
production gates.


## End-to-end SHADOW pre-production proof — 2026-10-02

Verified in one integrated test:
1. prepare a meeting-bound SHADOW activation packet;
2. include canonical Empire meeting/avatar/platform metadata in the Recall bot plan;
3. verify a signed raw Recall webhook before parsing;
4. enqueue only verified payloads into a private atomic spool;
5. asynchronously normalize the event into OBSERVED meeting evidence;
6. apply only explicit participant-role bindings;
7. refresh Predictive Revenue meeting guidance;
8. produce a private response task requiring human approval.

The integrated path performs no speech, chat send, commercial action, payment,
canonical revenue write or live Recall API call.

Current production activation blockers observed on the server:
- RECALL_REGION missing;
- RECALL_API_KEY missing;
- RECALL_WORKSPACE_VERIFICATION_SECRET missing;
- public gateway Recall route not loaded in the running gateway process;
- Recall webhook unit not installed in /etc/systemd/system;
- Recall SHADOW worker unit not installed in /etc/systemd/system.

The Cloudflare/public tunnel itself is present. Privileged systemd installation
and restart operations are staged but were not executed by the remote relay.

## SHADOW activation ledger and deduplication — 2026-10-02

Approved meeting preparation is now split from provider execution.

- `shadow-activation/preview` remains read-only.
- `shadow-activation/materialize` may persist only the private session manifest
  and a tamper-evident activation record.
- The activation fingerprint covers the full Empire meeting manifest, Recall
  Create Bot body and time-bounded owner approval.
- A conflicting plan under the same meeting ID fails closed and cannot overwrite
  the previously materialized session.
- Provider API credentials are never stored in the activation record.
- Live Create Bot execution is not exposed through the Founder API.

Provider execution uses a two-phase local ledger:
`prepared -> in_flight -> completed`.
If the provider outcome is ambiguous, state becomes `reconciliation_required`
and automatic re-execution is blocked.

Recall direct Create Bot does not provide automatic bot deduplication, so Empire
uses its own meeting-bound activation record and bot metadata mapping. Ambiguous
outcomes can be reconciled using Recall List Bots filtered by
`empire_meeting_id` and `empire_avatar_id`:
- exactly one bot -> `completed_reconciled`;
- zero bots -> `reconciliation_no_bot_found`;
- multiple bots -> `reconciliation_conflict`.

No reconciliation path automatically creates another bot.

## Architecture delta — Grounded Copilot + governed Presence — 2026-10-02

Change class: Architecture delta within the existing Digital Avatar domain.
Canonical business database: EmpireDB PostgreSQL. Supabase is not used as
Digital Avatar commercial truth.

### End-to-end diagram

```text
SIGNED MEETING PROVIDER EVENTS
  -> VERIFY RAW WEBHOOK
  -> PRIVATE VERIFIED SPOOL
  -> MEETING OBSERVATION / LIFECYCLE
  -> PRIVATE MEETING STATE
  -> PREDICTIVE REVENUE / NEXT-BEST ACTION
  -> RESPONSE TASK
  -> BUYER-SAFE EVIDENCE RESOLUTION
  -> GROUNDED PRIVATE DRAFT
  -> HUMAN REVIEW / APPROVAL
  -> VOICE RENDER
  -> ONE-TURN SPEECH TICKET
  -> PRESENCE OUTPUT MEDIA
  -> PLAYBACK ACK / FINALIZE
  -> OUTCOME EVIDENCE / CORTEX
```

### Canonical truth boundaries

Meeting speech and bot lifecycle are OBSERVED only after provider signature
verification. Signed Recall bot metadata binds provider events to the Empire
meeting/avatar/session and must remain SHADOW/zero-authority for shadow ingress.

Business knowledge supplied to a response model is resolved, not prompted from
memory. Production-safe evidence classes are:
- signed meeting observations;
- verified commercial price evidence from EmpireDB;
- verified public commercial-product projection from EmpireDB;
- approved buyer-facing commercial terms from EmpireDB;
- specific canonical commercial outcomes with provenance.

Internal acquisition cost, fulfilment cost, expected margin and other internal
economics are never part of buyer-facing Avatar evidence packs.

### Response and inference contract

Realtime ingestion remains deterministic and model-free. Private drafting is a
separate asynchronous lane so meeting event acknowledgement is never coupled to
LLM latency or availability.

A response task contains only approved evidence refs. The production evidence
resolver must resolve every required ref before model drafting. Missing or
invalid evidence produces `blocked_evidence` and zero model calls.

Generated drafts are validated after inference. Model citations outside the
approved evidence set fail closed. A valid draft remains private to the owner,
requires human approval, performs no transmission and grants no speech or
commercial authority.

Unchanged task + evidence content is content-addressed and deduplicated to avoid
repeated inference spend.

### Presence and one-turn speech authority

Recall Output Media is the transport for future meeting audio/video Presence.
The Presence webpage is not an authority source and cannot request or mint a
speech turn.

Speech authority is granted only by a short-lived, meeting/avatar/bot-bound,
text/audio-bound one-turn ticket created after explicit owner approval.
The ticket binds exact PCM SHA-256, byte length and sample rate. It is claimed
before audio delivery and cannot be reused.

Presence may receive server-pushed PCM only for an already-claimed in-flight
ticket. Browser completion acknowledgement must bind the same ticket and audio
hash. Completed delivery finalizes the ticket; ambiguous delivery becomes
`reconciliation_required` and never returns to reusable state.

A speech ticket grants `approved_turn_audio_only`. It grants no negotiation,
commercial terms, payment, outbound, database-write or revenue authority.

### Execution ownership / worker leases

Canonical owners for this delta:
- Recall ingress/lifecycle: `recall_webhook_*`, `recall_*ingest_worker.py`;
- meeting read state: `recall_meeting_*state.py`;
- grounded evidence: `digital_avatar_*evidence*.py`;
- private drafting: `digital_avatar_private_draft_*.py`;
- owner read surfaces: `digital_avatar_runtime_read.py`, `digital_avatar_api.py`;
- voice/render identity: `digital_avatar_voice_*.py`, visual profile modules;
- speech authority: `digital_avatar_speech*.py`;
- Presence transport: `digital_avatar_presence_*.py` and Recall Output Media
  adapters.

No second implementation may own these same responsibilities. Concurrent agent
work must extend the canonical owner or stop and reconcile before mutation.

### Failure / recovery behavior

Provider-signature failure: reject before parsing.
Queue/spool unavailable: return retryable failure; do not process inline.
Model unavailable: preserve observations/guidance; no draft is fabricated.
Evidence unresolved: block drafting; do not weaken evidence requirements.
Presence disconnected/ambiguous: do not transmit audio.
Playback timeout/failure: mark transmission reconciliation-required.
Lifecycle events arriving out of order: preserve monotonic newest state.
Ambiguous Create Bot result: reconcile by canonical signed metadata; never
blindly create another bot.

SHADOW remains the universal fail-safe mode. Loss of any external dependency
must not grant broader authority or create alternate truth paths.

### Promotion gates

Current permitted build state remains pre-production / OBSERVE unless separately
approved. Promotion is sequential:
1. SHADOW ingress and Founder state verified live;
2. private grounded Copilot draft verified live with no transmission;
3. one controlled owner-approved speech turn with disclosed AI identity;
4. repeated bounded Copilot speech shadow period with latency/error evidence;
5. REPRESENT only after a separate founder authority decision;
6. NEGOTIATE/CLOSE only after separate delegated commercial-authority approval.

Live Recall credentials, service installation/restart, meeting join and speech
remain explicit production gates. Binding terms, payment/funds movement and
revenue recognition remain outside speech authority.

### Definition of DONE for this delta

DONE requires architecture + scoped code + focused/adjacent/negative tests +
compile/static checks + clean diff checks + live runtime verification + Founder
read surface verification. A prepared systemd unit, passing test or local
rehearsal is not production completion.

Required production evidence before calling Copilot speech live:
- deployed intended HEAD;
- signed provider webhook observed;
- correct meeting/avatar/bot binding;
- private state visible through Founder surface;
- grounded draft cites canonical evidence only;
- explicit owner approval evidence;
- one-turn ticket consumed exactly once;
- Presence playback acknowledgement or reconciliation state;
- zero commercial/payment/revenue authority throughout.
