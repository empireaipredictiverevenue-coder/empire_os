# Phase 3E — Governed Outbound / Reply Capture

Status: local implementation tested; production activation gated.

## Current position
- Canonical outbound intent/approval/send/reply/suppression migration is local and tested.
- Supabase-backed closer state machine is local and tested.
- Resend provider adapter is fail-closed and OBSERVE-first.
- Isolated Resend webhook FastAPI service is local and tested.
- `empire-ai.co.uk` is verified for Resend sending and receiving.
- Existing Resend webhooks are disabled; reply capture is not live.
- Dedicated Phase 3E runtime LOGIN-role migration is local/tested; passwords remain unprovisioned.
- Legacy outreach timers/services are inactive/not installed.
- Empire execution remains OBSERVE globally. The new Outbound Governor can evaluate OBSERVE, ASSIST, and GUARDED_EXECUTE policy modes, but mutation stays fail-closed unless that workflow is explicitly promoted.

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
3. `empire_outbound_sender` may review, claim and record provider delivery only.
4. `empire_reply_ingest` may ingest/classify replies only.
5. `empire_closer_approver` may advance governed closer states only.
6. No closer role can mark a deal won, activate a buyer, record payment or revenue.

## Reply correlation
Outbound emails use a unique reply alias derived from the approved intent UUID:

`replies+<intent-uuid>@empire-ai.co.uk`

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
- `EMPIRE_REPLY_INGEST_DSN`

Secrets must be provisioned out of band. Do not commit credentials or print `.env`.

## Production activation order
1. Apply the governed outbound/reply migration to canonical Supabase.
2. Apply the Supabase closer-state-machine migration.
3. Create dedicated LOGIN identities; grant each only its matching NOLOGIN role.
4. Provision role credentials into server secret storage; never use postgres/service-role DSNs.
5. Install `empire-resend-inbound.service` but keep the Resend webhook disabled.
6. Route only the signed webhook path to loopback port 8097.
7. Verify health locally and through the intended provider route.
8. Configure/enable a Resend webhook for `email.received`, delivery failure and bounce events.
9. Use Resend test addresses and a controlled reply before any buyer outreach.
10. Keep sending manual/human-approved until observed delivery/reply/error behavior is proven.

## Release gates
- No production migration without explicit approval.
- No autonomous sends while execution mode is OBSERVE.
- No inbound email may directly call an agent or mutate commercial/payment state.
- No synthetic reply, buyer, order, payment or revenue records in production.
