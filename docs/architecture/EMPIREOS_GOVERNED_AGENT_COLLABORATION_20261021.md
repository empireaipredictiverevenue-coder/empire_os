# EmpireOS existing-agent collaboration — 21 October 2026

## Decision

Integrate Agent-OS-like persona and coordination **into existing EmpireOS**.
Do not create separate AI companies, autonomous identities, schedulers,
databases, queues, SaaS dashboards or external-facing A2A agents.

Core collaboration code was selectively integrated into the existing production
repository at commit `7ea86d5bf` and passed 57 scoped regression tests.
The collaboration runtime remains **not activated**: no trusted agent keys
were provisioned, no agent model adapters were connected, and no public
Kanban endpoint, new worker or scheduler was started.

- Existing `empire_os/departments.py` is the authoritative catalogue of
  departments and roles. Registration fails if an agent claims a new department
  or role, or components outside that department's published components.
- `empire_os/department_collaboration.py` models existing-agent SOUL-style
  profiles (purpose, individual style, success criteria, specialties) while
  enforcing immutable backend rules. Style text cannot grant capabilities,
  overwrite policy or imply the runtime agent is registered/healthy.
- Existing `DepartmentWorkQueue` remains the **sole source of task truth**.
  Scoped `claim_next` is still atomic and filters by department, explicit
  allowed components, exact tenant, and internal/observe authority.
  Pre-existing unscoped worker callers retain their existing semantics.
  The new `release_claim` operation uses exact current worker+lease binding;
  it returns an unfinished job to READY, never marks it DONE.
- Signed, task-linked internal conversation: help request, blocker, update,
  evidence and handoff messages; recipients can reply to a verified message
  without becoming owner of the source task. All messages are untrusted
  evidence/context. No message can start outbound, make a DB migration, activate
  a provider, deploy, confirm payment or self-certify task completion.
- The Kanban board **projects canonical existing queue states**:
  READY / RUNNING / REVIEW / BLOCKED / DONE / FAILED. No separate Kanban state,
  drag-to-DONE authority, shadow job creation or board-to-DB write capability.

## Agent lifecycle and conversation

1. Existing trusted operator injects an explicit **already-authorised** agent
   identity with 256-bit secret, role, tenant and component allowlist. There
   are NO default agent credentials and no implicit auto-enrolment.
2. Role-dependent persona card and SOUL text are guidance only. Backend rules
   and owner-approved SkillForge digests remain authoritative.
3. Actor submits a signed pickup request; nonce is reserved atomically before
   canonical queue claim; a replay can never pick up a second job.
4. A signed, scope-bound help request may go to another department's existing
   trusted agent. A reply must reference the original authentic message,
   reverse the sender/recipient pair and preserve task + tenant identity.
5. Agent may yield only a currently held lease belonging to that agent; a
   stale lease cannot yield another agent's task.
6. An eventual executor/independent reviewer must use the already governed
   Department worker and review pipeline. This prototype does **not** add an
   executor, let chat complete tasks, or bind model providers automatically.

## Security properties

- All local credentials are injected by caller and NEVER persisted or logged.
  Agent IDs and roles alone provide zero authority.
- HMAC-SHA256 authenticates exact operation+payload. Nonces prevent repeat
  pickup and duplicate messages; replay or tampering fails closed.
- Message and nonce files are private to the local process user (0700/0600);
  messages are bound to canonical tasks and exact tenant scope.
- Reply chain and inbox verify the original signature before accepting text.
  Source bodies remain explicitly untrusted.
- No unauthenticated public API endpoints or third-party webhooks.
- Kanban default returns only tenant-unbound work, and only compact metadata.
  Tenant board exposure requires independently verified Founder Console auth
  and tenant scope: this is not yet wired into the browser UI.
- No new systemd service, timers, hosted components or network dependencies.
- Existing external A2A commerce, money and authority remain separate.

## What is genuinely implemented vs remaining

Implemented and tested on synthetic isolated queue roots: role/persona
validation, static SOUL contracts, scope-bound signed peer messages and
two-way reply chains, tamper evidence, atomic scoped task pickup, replay
protection, exact-lease yield, fail-closed tenant/scope enforcement, and
read-only Kanban projection.

NOT implemented/NOT live: actual agent credential provisioning/rotation,
trusted connection to installed Jev/OpenManus/Hermes/SkillForge runtimes,
per-agent model invocation and tool adapter, independent work review,
authenticated Founder Console Kanban route, cross-process notifications/
wakeups or measured throughput improvement. **Don't describe these as
activated or full orchestration yet.** Keep the original Department
cycle/worker authoritative.

## Recommended next safe integration

Connect **only authorised existing runtime identities** to the signed inbox
and claim port; test role/tenant provenance and recovery in a separated
private canary. Then mount the read-only board *inside the existing
authenticated Founder Console*, with its actual session/tenant gate proven
before any endpoint goes live. Do not attach collaboration to the public
`empire_os.hub` simply because a read router exists there.
