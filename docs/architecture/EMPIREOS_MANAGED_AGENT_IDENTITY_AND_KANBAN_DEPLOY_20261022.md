# EmpireOS — Managed-worker identity proof & pinned CRM Kanban release

22 October 2026. Existing EmpireOS integration. **No new company, agent,
scheduler, shared DB, outbound sender or A2A public endpoint.**

## What the runtime genuinely does

`empire_os/agent_runtime_identity_evidence.py` maps TWO known canonical
systemd jobs to existing department roles/capabilities:

- `empire-coder-worker.service` → existing `empire_coder`,
  engineering/coder, `empire_coder` capability
- `empire-department-cycle.service` → existing ephemeral Department
  Executive, strategy/executive_operations, `astra_executive` capability

The read-only process observer checks the allowlisted unit's exact
systemd-reported Id, active MainPID, expected service user, kernel UID
from `/proc/<pid>/status`, and exact cgroup membership from
`/proc/<pid>/cgroup`. It does **not** read `/proc/*/environ` or
`cmdline`, or any DSN, token or email content. It intentionally returns
false when the short-lived job is not running.

A separate `preflight_local_managed_binding` is for invocation **inside
the real service main process** by a trusted bootstrap. It additionally
checks its actual PID (no caller PID in production), pinned agent role and
single permitted component, explicit unbound tenant scope, and a private
256-bit credential. This is a **credential shape + process provenance**
test, not trusted broker registration. It does not store keys, issue keys
or activate a peer mailbox. Broker-side key registration and isolation
from other `ubuntu`-UID processes are STILL REQUIRED.

`review_existing_agent_collaboration(...,
include_managed_runtime_identity=True)` enables read-only observation
on demand; the default stays offline/pure for callers and tests.

**Not falsely counted as local agents:** JEV is a model provider; Laya
is a model sidecar; Hermes is not activated as a Department agent; no
managed Research-agent process has been identified/attested for this
protocol. Existing worker role definitions do not prove connected agents.

## Protected CRM reader release

The current first-party CRM service at port 8783 uses the original pinned
release at:
`/opt/empire-ai/crm-pilot-releases/win-plans-solar-console-20261019v1`

The reviewed candidate lives at:
`/home/ubuntu/empire_releases/agent_kanban_crm_pilot_candidate_20261022`

It differs in exactly one modified file and one added file; current live
`GET /v1/revenue-crm/department-kanban` still returned 404 when checked.
No live CRM service restart was performed.

The checked-in script
`scripts/deploy_pinned_agent_kanban_crm_20261022.sh` enforces a read-only
preflight by default. Dry-run preflight **passed** on this server (pinned
sha256, file inventory, running original release and HTTP health/404).
An approved existing root release owner can run its separately gated
`--apply-founder-approved` path; that path requires current original
hash and exact two-file candidate delta, copies to a protected `/opt`
release, writes a NEW highest-priority unit drop-in, reloads/restarts
the existing service and verifies 200 health + 401 unauthenticated board.
On failure after installing the drop-in, it attempts to roll back the
original pinned working directory.

The paired
`scripts/rollback_pinned_agent_kanban_crm_20261022.sh` validates the
original release's exact hash and its own drop-in before restoring the
original live service. The new release directory remains available for
forensic review; rollback never deletes another agent's work.

**Not yet executed:** root-owned release staging, systemd switch, 401
against the live changed service, authenticated founder token 200,
cross-tenant real HTTP canary. The remote operator's privilege path was
restricted; do not report activation without those receipts.

## Identity activation order

1. Root release-owner performs the protected CRM release, with health,
   unauthenticated 401 and authorized existing founder-tenant read canary.
2. Establish trustworthy service-specific process identities and dedicated
   signing keys provisioned with service-private permissions; ensure
   long-lived processes cannot reuse keys across roles even though the
   legacy service processes currently share Unix UID `ubuntu`.
3. Pin authorized worker identity → tenant → exact allowed component
   and publish trust to the existing Collaboration broker only. A self-
   declared SOUL/persona or task message cannot grant permissions.
4. Integrate `DepartmentCollaboration` HMAC send/pickup/yield with the
   existing managed worker loop. Verify replay rejection, tenant isolation,
   lease transitions, audit trails, and independent completion review.
5. Do not attach an unverified Agent OS control panel to the public Hub
   or to the generic loopback Founder Console without auth.

This is one canonical queue + one existing runtime stack.
