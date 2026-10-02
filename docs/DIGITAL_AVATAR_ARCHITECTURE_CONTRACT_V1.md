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
