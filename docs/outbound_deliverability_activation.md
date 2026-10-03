# Ringleader Deliverability Activation Runbook

## Status

This runbook prepares the Empire-owned outbound deliverability observer for production.
It does **not** authorize any production action.

Current safe state:

- Ringleader code: staged on `agent/outbound-deliverability-v1`
- execution mode: OBSERVE only
- EmpireDB migration 033: staged, not applied
- dedicated deliverability DB roles: not provisioned
- observer systemd unit/timer: staged, not installed or enabled
- DNS: unchanged
- transports: unchanged
- outbound send authority: unchanged
- live sends: not enabled by Ringleader

## Gate 0 — reconcile production truth

Before any activation:

1. Fetch the current production branch and preserve uncommitted work.
2. Verify the actual latest `migrations/empiredb/` migration number on the server.
3. If production already uses migration number 033 or later, renumber this migration before applying it.
4. Verify the canonical data backend is EmpireDB/PostgreSQL.
5. Verify the outbound governor remains the only component with live-send authority.
6. Run the complete outbound CI family and compile checks.

Do not infer migration numbering from GitHub when the live repo is ahead.

## Gate 1 — EmpireDB schema approval

Requires explicit founder approval.

Candidate migration:

`migrations/empiredb/033_outbound_deliverability_control_plane.sql`

Properties:

- append-only deliverability evidence
- append-only Ringleader decisions
- sender-pool history
- provider-policy snapshots
- reputation-economic history
- contact-pressure history
- no send authority
- no UPDATE/DELETE of existing commercial data
- no role grants embedded in migration 033

Before apply:

- review SQL against current production schema
- run in a transaction against a non-production verification database where available
- verify constraints and indexes
- verify rollback procedure
- verify no namespace collision with newer production migrations

## Gate 2 — least-privilege role approval

Requires explicit authority-expansion approval.

Provision dedicated roles only after migration approval:

- `empire_outbound_deliverability_reader`
- `empire_outbound_deliverability_writer`

Reader contract:

- SELECT only on deliverability evidence/read-model tables
- no DDL
- no commercial/outbound intent mutation
- transaction read-only

Writer contract:

- INSERT only on approved append-only deliverability evidence tables
- no UPDATE
- no DELETE
- no outbound-intent approval
- no send RPC execution
- no suppression removal
- no commercial term/payment authority

Create separate DSNs; never reuse a broad migrator credential.

## Gate 3 — provider evidence binding

No send approval required because this is read-only evidence collection, but secret/config
installation is still a production configuration change.

Runtime secret file:

`/srv/empire_os/runtime/secrets/outbound-deliverability.env`

Required safe values:

`EMPIRE_OUTBOUND_RINGLEADER_MODE=OBSERVE`

`EMPIRE_OUTBOUND_SCOPE_KEY=empire`

Optional after DB role activation:

`EMPIRE_OUTBOUND_DELIVERABILITY_READER_DSN=<dedicated reader>`

`EMPIRE_OUTBOUND_DELIVERABILITY_WRITER_DSN=<dedicated append-only writer>`

Provider keys remain secret and must never enter Git.

## Gate 4 — observer installation

Requires explicit production service-install/enable approval.

Stage:

- `deploy/systemd/empire-outbound-ringleader-observer.service`
- `deploy/systemd/empire-outbound-ringleader-observer.timer`

Verify before enable:

- unit contains OBSERVE mode
- no `--execute`
- no live-send module
- no secret values embedded
- `ProtectSystem=strict`
- `ProtectHome=true`
- only runtime path writable

First run should be a manual one-shot OBSERVE smoke before timer enablement.

## Gate 5 — OBSERVE acceptance criteria

The observer can be considered operational only when:

- provider evidence is read successfully
- rolling 1d/7d/30d health is produced
- Ringleader returns FLEET scope
- `mutation_authorized=false`
- canonical evidence persists idempotently in EmpireDB
- Reputation Passport chain verifies
- Founder API can read the latest canonical decision/history
- repeated run does not create duplicate evidence for the same evidence hash
- provider outage fails closed and does not alter outbound authority
- no send count changes as a consequence of observer execution

## Gate 6 — seed placement and domain observers

After OBSERVE is stable:

- checkdmarc -> Auth Observer
- parsedmarc/RFC 9990 -> DMARC aggregate intelligence
- DNSControl -> desired DNS state / drift evidence
- Google Postmaster v2 -> Gmail destination evidence where volume supports it
- Microsoft/Yahoo/Apple -> SMTP/NDR + controlled seed evidence
- Mailpit -> deterministic local transport tests

These feed Ringleader as evidence. They do not gain send authority.

## Gate 7 — no automatic promotion to live sending

There is deliberately no step in this runbook that turns Ringleader into a sender.

A future live action must remain separately bound to:

- canonical suppression clearance
- verified recipient/person/company evidence
- provider-policy compatibility
- healthy sender/domain/MX pool
- existing Outbound Governor decision
- applicable founder/live-send approval

Ringleader supervises reputation. The Outbound Governor controls send eligibility.
