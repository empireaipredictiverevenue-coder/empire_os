# Phase 3E — Governed Outbound / Reply Capture

Status: local implementation tested; production activation gated.

## Current position
- Canonical outbound intent/approval/send/reply/suppression schema is live in canonical Supabase.
- Dedicated sender runtime identity is provisioned and the governed sender transport is live/tested.
- First real buyer outbound intent has passed governed review and approval; no send has occurred yet.
- Resend sender domain `mail.empire-ai.co.uk` is verified for sending and receiving.
- Fail-closed Resend provider adapter, Outbound Governor, executor, bounded worker queue, reply classifier and signed webhook service are local/tested.
- Three forward-only Phase 3E hardening migrations are staged and isolated-Postgres tested: reply sender binding, Governor context/work queue, and provider lifecycle events.
- Existing Resend webhooks remain disabled; inbound reply/delivery capture is not live.
- Reply-ingest and approver login credentials still need local provisioning.
- Supabase-backed closer state machine remains local/tested and separately gated.
- Legacy outreach timers/services remain inactive.
- Empire execution remains OBSERVE globally. The Outbound Governor can evaluate OBSERVE, ASSIST, and GUARDED_EXECUTE policy modes, but mutation stays fail-closed unless that workflow is explicitly promoted.

## Outbound Governor
`empire_os/outbound_governor.py` is the deterministic policy layer for Phase 3E. It evaluates the current intent plus evidence context and returns one of: `HOLD`, `REPAIR_REQUIRED`, `AUTO_REPAIR`, `ESCALATE`, `READY_FOR_HUMAN_APPROVAL`, `AUTO_APPROVE_ELIGIBLE`, `READY_FOR_SEND_GATE`, or `AUTO_SEND_ELIGIBLE`.

Modes are deliberately separated:
- `OBSERVE`: evaluate only; no mutations.
- `ASSIST`: deterministic repairs may be authorized, but approval/send remain gated.
- `GUARDED_EXECUTE`: auto-approval/send can become eligible only when explicitly enabled and every hard/evidence/compliance check passes.

The governor never sends email or writes commercial state itself. `empire_os/outbound_governor_executor.py` is the separate execution adapter: it accepts only `GUARDED_EXECUTE` decisions with explicit mutation authorization, routes approvals only through the approver transport, and routes sends only through the sender transport plus the existing fail-closed Resend provider. Existing role-separated transports remain the mutation boundary.

## Security boundaries
1. `service_role` may propose an outbound intent; it cannot approve or send it.
2. `empire_outbound_approver` may approve; it cannot send.
3. `empire_outbound_sender` may review Governor context/work, claim sends and record sender-side delivery only; it cannot approve.
4. `empire_reply_ingest` may ingest/classify replies and verified provider lifecycle events only; it cannot approve or send.
5. `empire_closer_approver` may advance governed closer states only.
6. No closer role can mark a deal won, activate a buyer, record payment or revenue.

## Reply correlation
Outbound emails use a unique reply alias derived from the approved intent UUID:

`reply+<intent-uuid>@mail.empire-ai.co.uk`

The inbound service accepts only signed Resend webhooks, fetches plain-text email,
resolves the exact intent from that alias, and writes inert reply data. Email body
content is explicitly untrusted and never receives execution authority.

## Runtime environment names
Required only when the provider edge is activated:
- `RESEND_API_KEY`
- `RESEND_WEBHOOK_SECRET`
- `EMPIRE_REPLY_TO`
- `EMPIRE_OUTBOUND_FROM`
- `EMPIRE_OUTBOUND_SENDER_DSN`
- `EMPIRE_OUTBOUND_APPROVER_DSN` (required only for governed auto-approval)
- `EMPIRE_REPLY_INGEST_DSN`
- `EMPIRE_OUTBOUND_GOVERNOR_MODE`
- `EMPIRE_OUTBOUND_AUTO_APPROVE`
- `EMPIRE_OUTBOUND_AUTO_SEND`

Secrets must be provisioned out of band. Do not commit credentials or print `.env`.

## Production activation order
1. Apply the three staged Phase 3E hardening migrations to canonical Supabase.
2. Provision dedicated approver and reply-ingest LOGIN credentials into local secret files; never use postgres/service-role DSNs.
3. Install/enable `empire-outbound-governor.timer` with OBSERVE defaults.
4. Install `empire-resend-inbound.service` using `.env.resend_inbound`.
5. Route only the signed webhook path to loopback port 8097 through the existing public gateway/tunnel.
6. Verify local and public health checks.
7. Register/enable Resend events for `email.received`, `email.delivered`, `email.delivery_delayed`, `email.bounced`, `email.complained`, `email.failed`, `email.suppressed`, `email.opened`, and `email.clicked`.
8. Use Resend test addresses plus a controlled inbound reply to verify delivery, bounce, reply classification and suppression.
9. Keep the Governor in OBSERVE until the observed event/reply path is proven; promote only the outbound workflow to GUARDED_EXECUTE when explicitly approved.
10. Complete the Supabase closer-state-machine production gate, then move directly into Phase 3F outcome feedback.

## Release gates
- No production migration without explicit approval.
- No autonomous sends while execution mode is OBSERVE.
- No inbound email may directly call an agent or mutate commercial/payment state.
- No synthetic reply, buyer, order, payment or revenue records in production.
