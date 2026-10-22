# EmpireOS internal Agent Kanban — pinned CRM release reconciliation

22 October 2026 — OBSERVE-only production deployment handoff.

## Existing canonical work and security boundary

The core internal collaboration library is committed to existing EmpireOS
(`7ea86d5bf`) and the authenticated CRM Kanban reader is committed at
`2cbb96aef`. There is no new agency, agent scheduler, database, business,
public endpoint or autonomous outbound.

Live read-only CRM uses **a frozen release**, not the mutable repo:

- Installed production release:
  `/opt/empire-ai/crm-pilot-releases/win-plans-solar-console-20261019v1`
- Existing service: `empire-revenue-crm-pilot.service`, loopback port 8783
- Canonical EmpireOS repo: `/srv/empire_os` (EmpireDB remains the canonical DB)

**Live state on inspection:** service active, unauthenticated GET
`/v1/revenue-crm/department-kanban` returned **404**. This is evidence the
running service has NOT loaded the new route, regardless of the repository
commit. Do not present the Kanban as accessible through CRM yet.

## Isolated compatible release candidate

`/home/ubuntu/empire_releases/agent_kanban_crm_pilot_candidate_20261022`

Built by copying the exact currently pinned release and applying a minimal
backward-compatible addition, not a wholesale replacement from the mutable
repository. The comparison of all 2,370 original files found:

- Only **one original file changed**:
  `empire_os/revenue_crm_api.py` — added
  `GET /v1/revenue-crm/department-kanban` using its EXISTING verified CRM
  resolver and bounded dedicated Postgres session check.
- Only **one file added**:
  `empire_os/department_collaboration.py` — existing EmpireOS
  canonical-queue Kanban projector, no new task state or auth server.
- **Zero original files deleted**. No changes to login, token signing,
  membership, DSNs, worker runtime, scripts, scheduler or startup unit.

Pinned original `revenue_crm_api.py` SHA-256:
`05fcd04cdd326cb4101d04de022abf0fde40e28fd4a238704c8b1cac25fb15ab`

Candidate `revenue_crm_api.py` SHA-256:
`34ecda4b2c2b86540daa9c4d74c420b8d67add94267308d721d2e405c6b21a15`

## Auth and test evidence

- **121/121** relevant tests passed in the canonical repository after the
  source changes.
- **21/21** relevant authentication and tenant-isolation tests passed using
  the pinned candidate's module imports (not the mutable repo's CRM API).
- A direct offline candidate test confirmed the source path was the
  candidate and the *legacy unauthenticated* API variant returned 503.
- The authenticated CRM variant requires its original signed login, verified
  dedicated tenant DB session, and same-tenant queue records. A request
  lacking a valid signed session must return 401, with forged tenant headers
  unable to widen its scope. **No real founder credential was accessed or
  used** in this candidate review.
- The tenant CRM view intentionally excludes unbound EmpireOS-internal tasks.
  Full internal founder Kanban requires a separate owner-authenticated gate.

## Deployment gate and rollback

This candidate has **not** replaced the installed release and no service
restart was done during this work.

Before activation, verify the real original release's current file hashes
and effective systemd override precedence; obtain explicit release-owner
approval of the two-file delta. Then stage the candidate at a protected
approved immutable production path, update the existing service's
`WorkingDirectory` and `PYTHONPATH` together (do NOT activate from a
writable worktree) and perform a controlled restart in an approved window.
The existing startup still requires `APPROVED_READ_ONLY_PILOT` and its
private complete configuration.

Required runtime proof is a healthy service, 401 without a signed tenant
session, proper 200 tenant-filtered reads with a separately verified
existing founder-tenant login, cross-tenant denial, unchanged previous CRM
API health and routes, and unchanged payment/outbound authority. Only a
verified protected rollback to the original pinned release should be used
to reverse the deployment. Preserve all concurrent owner work.

Further genuine orchestration requires per-agent process identity,
provisioned and isolated signing credentials, explicit approved skill
digests, recipient-specific handoff permissions and bounded peer wakeups.
Role catalogues and a task-board endpoint are NOT proof of these capabilities.
