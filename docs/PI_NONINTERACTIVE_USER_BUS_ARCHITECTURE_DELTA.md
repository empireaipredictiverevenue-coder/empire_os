# Pi Non-Interactive User-Bus Recovery — Architecture Delta

Date: 2026-10-01
Status: APPROVED IMPLEMENTATION DELTA
Owner: Agent & Tool Execution Plane / Pi Sandbox Runner

## 1. Purpose

Restore the existing governed Pi sandbox when EmpireOS dispatches Pi from a
non-login process such as Remote MCP, service execution, or another control-plane
worker.

Observed failure:

`systemd-run --user` fails before Pi starts when both
`XDG_RUNTIME_DIR` and `DBUS_SESSION_BUS_ADDRESS` are absent.

Live evidence on EmpireOS:
- runtime user UID: 1000;
- `/run/user/1000` exists and is owned by ubuntu;
- `/run/user/1000/bus` exists as a Unix socket;
- with the canonical runtime-dir and bus address supplied,
  `systemctl --user` and `systemd-run --user` both succeed.

This is an execution transport defect. It is not a Pi model-health defect.

## 2. Canonical placement

Owner:
- `empire_os/pi_sandbox_runner.py`

Verification owner:
- `tests/test_pi_sandbox_runner.py`

No new service, queue, data store, external provider, or authority is introduced.

## 3. Truth / data contract

Inputs are local operating-system facts only:
- effective UID;
- expected systemd user runtime directory;
- presence of the user-bus Unix socket;
- ambient process environment.

Output is a sanitized process environment used solely to invoke
`systemd-run --user`.

No commercial, customer, buyer, payment, revenue, or canonical business data is
read or written.

Truth class: OBSERVED OPERATIONAL HEALTH.

## 4. Authority contract

Authority remains INTERNAL ENGINEERING / NONE for business actions.

The change MUST NOT:
- weaken the existing systemd sandbox;
- bypass `systemd-run --user`;
- use `--dangerously-*` execution;
- expose secrets;
- send outbound;
- mutate canonical business data;
- move funds;
- recognize revenue;
- apply migrations;
- expand Pi authority.

Migration 018 remains held and untouched.

## 5. Execution model

When building the Pi process environment:

1. preserve the current secret-stripping policy;
2. preserve safe ambient variables when present;
3. if `XDG_RUNTIME_DIR` is missing, derive the standard systemd user runtime
   directory from the effective UID: `/run/user/<uid>`;
4. if `DBUS_SESSION_BUS_ADDRESS` is missing and the canonical bus socket exists,
   set it to `unix:path=/run/user/<uid>/bus`;
5. do not fabricate a usable bus when the runtime directory/socket does not
   exist;
6. allow `systemd-run --user` to fail closed with a clear, observable reason.

No fallback to an unsandboxed Pi process is permitted.

## 6. Worker assignment

- Hermes: sole mutating builder for the owner/test files.
- Codex: independent OBSERVE-only reviewer.
- Pi: cannot repair its own runner while the runner is unavailable.
- Swarm V6: independent verification after implementation.
- Empire Coder: verification fallback only.

No overlapping mutating lease is allowed.

## 7. Failure / recovery behavior

Positive example:
A non-login Remote MCP process has no DBus variables, but
`/run/user/1000/bus` exists. The runner reconstructs only the canonical
user-bus variables and Pi continues through the existing hardened systemd scope.

Negative example:
`/run/user/1000/bus` is absent. The runner must NOT fall back to invoking Pi
directly. The job fails closed and reports the sandbox/runtime dependency.

Security example:
Ambient API keys continue to be removed by `_safe_env`; adding user-bus
variables must not change secret filtering.

## 8. Observability

Existing Pi sandbox result remains authoritative for:
- return code;
- sandbox failure stage;
- output tail;
- changed paths;
- verification;
- authority = none.

A future enhancement may add an explicit `user_bus_unavailable` failure class,
but that is not required to restore the bounded defect.

## 9. Verification / promotion

Required before DONE:
1. focused Pi runner tests;
2. new test: missing ambient DBus variables + existing canonical bus -> derived
   environment is correct;
3. new negative test: missing canonical bus does not invent a DBus address;
4. existing secret-filter test/invariant remains true;
5. compile changed module;
6. execution-plane adjacent tests;
7. live OBSERVE Pi job succeeds through the systemd sandbox;
8. no production repo mutation from the OBSERVE job;
9. Swarm/independent verification;
10. record evidence and close.

## 10. Commercial fit

This change restores engineering throughput only. It creates no revenue,
commercial intent, buyer state, payment state, or external action.

Reliable governed parallel builders reduce founder bottlenecks while preserving
the production authority model.
