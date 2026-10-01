# EmpireOS Production Health Recovery — Closeout Evidence

Date: 2026-10-01
Status: LIVE OPERATIONAL / ONE EXPLICIT RESTART GATE REMAINS
Branch: agent/data-cloud-wave4

## Scope

This closeout covers the morning production-health objective:
Founder read API compatibility -> Pi execution-plane recovery -> timer/control-plane recovery -> self-heal policy correction -> independent verification -> live verification.

## Founder read API

Root cause: FastAPI 0.141.1 / Starlette 1.6.0 preserve included routers as nested router objects, so tests that assumed every top-level app.routes item exposed .path were stale.

Fix: tests/test_founder_dashboard_service_routes.py now verifies the public OpenAPI contract rather than framework-internal route flattening.

Live evidence:
- /health -> HTTP 200
- /v1/founder-execution-plane/status -> HTTP 200
- /v1/founder-execution-plane/coding-team/status -> HTTP 200

Status: DONE.

## Pi non-interactive sandbox recovery

Architecture: docs/PI_NONINTERACTIVE_USER_BUS_ARCHITECTURE_DELTA.md

Root cause: Remote/non-login control-plane processes did not inherit XDG_RUNTIME_DIR or DBUS_SESSION_BUS_ADDRESS even though the real systemd user bus existed at /run/user/1000/bus.

Implementation:
- preserve secret filtering and systemd-run --user;
- derive only the canonical per-UID runtime path when missing;
- derive DBus address only when the canonical path is a Unix socket owned by the effective UID;
- preserve ambient values;
- missing/non-socket bus fails closed;
- no direct/unsandboxed Pi fallback.

Commit: e7f34e68 — Fix Pi non-interactive user-bus recovery.

Verification:
- 38 focused + execution-plane tests passed after promotion;
- independent Codex review: PASS;
- live MCP-dispatched Pi OBSERVE job morning-self-heal-diagnosis-20261001-v2 completed;
- status COMPLETED_NO_CHANGES; Pi return code 0;
- production mutation false; outbound false; payment false; revenue recognition false.

Status: DONE.

## Production timer recovery

Architecture: docs/PRODUCTION_CONTROL_TIMER_RECOVERY_DELTA_2026-10-01.md

Observed root cause: 11 enabled timers were inactive after earlier containment/cutover operations. This was not a systemd crash: zero failed units were present.

Deployment drift found:
1. empire-astra-dispatcher.timer was enabled while its service was missing.
2. repo Astra service defaulted to GUARDED_EXECUTE, inconsistent with current OBSERVE doctrine.
3. live empire-ops-control.service still used GUARDED_EXECUTE while repo correctly used OBSERVE.

Corrections:
- Astra deployment default changed to OBSERVE and locked by regression test;
- reviewed Astra service installed live without starting it;
- reviewed Ops Control OBSERVE service replaced stale live definition;
- daemon-reload performed;
- no service was restarted during definition alignment.

Commit: bfd378a6 — Default Astra dispatcher service to OBSERVE.

Independent Codex timer review classified 10 existing bounded schedules SAFE_TO_RESUME and revenue-runtime-supervisor HOLD.

Resumed schedules: Astra dispatcher, buyer capacity readiness, buyer review materializer, commercial evidence verifier, conversation recovery, legacy permit recovery, Ops Control, Predictive Intelligence, private-capital snapshot and qualification booster.

All 10 timers are active. Triggered oneshot services completed successfully. Astra live artifact reports mode OBSERVE and every selected action as WOULD_DISPATCH. Systemd failed-unit count remains zero.

## Revenue runtime supervisor founder gate

revenue_runtime_supervisor.sh can start Resend inbound, outbound-governor, outbound-follow-up, GTM and closer schedules. It is therefore not generic self-heal.

empire-revenue-runtime-supervisor is now explicitly FOUNDER_GATE in runtime_self_heal.py.
Commit: 7c309be2 — Gate revenue runtime supervisor in self-heal.
Verification: 13 self-heal / ops tests passed. The timer remains inactive and was not started.

## Remaining live-code reload gate

empire-reliability-agent.service is a long-running process owned by ubuntu. It started at 2026-10-01 06:33 and imports runtime_self_heal into process memory. Its service unit declares EMPIRE_AUTONOMOUS_MODE=OBSERVE.

Because the process predates commit 7c309be2, it can overwrite runtime/self_heal/latest.json every ~120 seconds with the old supervisor policy. This explains the temporary reversion from FOUNDER_GATE to OBSERVE_ONLY despite direct current-code classification returning FOUNDER_GATE.

Required final live action: restart empire-reliability-agent.service so it imports current production code, then verify two consecutive cycles preserve FOUNDER_GATE. This restart is HELD pending explicit founder approval in the current task.

## Buyer capacity artifact clarification

Current canonical readiness output is runtime/buyer_capacity_readiness/latest.json. The old runtime/buyer_capacity/latest.json is legacy/stale evidence, not the current readiness output.

Current readiness evidence: buyers_seen 1057; capacity_verified 0; commercially_activated 0; allocation_ready false; highest_priority_blocker verified_commercial_terms. These are business-readiness facts, not runtime-health failures.

## Broad regression

Morning upgrade/control regression: 283 tests passed, 1 Starlette deprecation warning. No failed systemd units.

Migration 018 remains untouched with SHA256 e7edcfe1d0f94c3898437e68db0714557370b7b86f9b21ee76cc04be60bc3c21.

## Examples

Positive: an already-enabled internal timer whose service matches the reviewed repo and cannot directly send, move funds, accept terms or recognize revenue may resume as an existing bounded schedule.

Negative: do not start a timer merely because it is enabled. Astra lacked an installed service, while Revenue Runtime Supervisor can indirectly revive outbound execution.

Failure recovery: a long-running Python service started before a policy/code change can retain stale modules in memory. File-on-disk correctness does not prove process-code correctness; compare process start time to deployed code and reload through the explicit restart gate.

## Authority / non-actions

No live email was sent. No terms were accepted. No payment/fund action occurred. No revenue was recognized. No migration was applied. Migration 018 was not changed. Revenue Runtime Supervisor was not started.
