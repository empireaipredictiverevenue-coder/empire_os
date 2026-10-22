# EmpireOS CRM Kanban — failed release forensic and guarded retry

22 October 2026. Continue the EXISTING authenticated CRM pilot and
existing Agent OS queue. No new agent, company, timer, database or service.

## Verified incident, not an inferred successful deployment

An approved operator ran:
`sudo bash /srv/empire_os/scripts/deploy_pinned_agent_kanban_crm_20261022.sh --apply-founder-approved`.

The preflight succeeded, then printed rollback twice. Read-only checks
of the real service showed:
- The original `win-plans-solar-console-20261019v1` release is active.
- `GET /health` returned HTTP **200**.
- `GET /v1/revenue-crm/department-kanban` returned **404**.
- The originally pinned CRM API hash remains
  `05fcd04cdd326cb4101d04de022abf0fde40e28fd4a238704c8b1cac25fb15ab`.
- A protected root-owned staged release was left at
  `/opt/empire-ai/crm-pilot-releases/agent-kanban-crm-20261022v1`.
  A complete 2,371-file audit confirmed it matches the reviewed candidate:
  zero modified/missing/extra files, zero symlinks. That stage is preserved.
- The candidate service was reversed within approximately one second,
  before Uvicorn logged a completed candidate startup. Immediate HTTP
  probing before readiness is therefore a *likely* reason for the failure,
  not an independently proven traceback.

## Defects corrected

1. The original script checked HTTP health immediately after starting
   the service. Revised script performs bounded readiness polling for
   both HTTP 200 health and **401** on the unauthenticated Kanban route.
2. Original preflight used a bash `test ! -e "$NEW" && ...` chain.
   Under `set -e` a false non-terminal command in an `&&` list need not
   terminate the function. Fixed with explicit fail-closed checks. A
   correctly staged **root-owned identical** release can now be reused;
   any altered/incomplete/unowned stage is denied.
3. The previous ERR trap returned, producing duplicate rollback output
   and allowing misleading exit codes. Revised error trap records the
   exact failed step/line/exit code, disables recursive ERR trapping, and
   explicitly exits nonzero after one rollback attempt.
4. The rollback removes only this release's exact override content.
   If another owner changed the override, it refuses to remove it.
   Other owner's pinned releases are never overwritten or deleted.
5. The script is still opt-in: no arguments/`--check` do not touch the
   service; protected activation requires the exact explicit founder-
   approved argument and root. No agent credentials or new model/network
   permissions are issued.

## Evidence and operator path

Tests: `tests/test_agent_kanban_release_recovery.py` mock delayed
startup, denial of wrong HTTP status, no-switch failure, exactly-once
rollback and changed-override refusal. Tests use only synthetic commands,
not the live service.

Current live read-only verification:
`bash /srv/empire_os/scripts/deploy_pinned_agent_kanban_crm_20261022.sh --check`

If current protected prerequisites still match and the release owner
approves, the **same existing** `--apply-founder-approved` invocation
attempts a controlled switch. Do not run the previous script revision.

Success requires explicit service status, HTTP 200 health, HTTP 401 for
unauthenticated Kanban, correct pinned release path and an independently
authenticated CRM tenant 200 read followed by cross-tenant denial.
Absent those, DO NOT claim the Kanban is live or that existing agents
are authenticated. The independent agent-to-agent identity/credential
binding remains a separate governance gate.
