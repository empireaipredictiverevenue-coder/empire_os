# EmpireOS real Coder -> trusted root identity socket observation

22 October 2026. This is a **one-shot, zero-authority** provenance
verification, not a trusted signing-key or agent-to-agent activation.

## Verified starting state

The protected original EmpireOS privileged helper was upgraded by the
founder to root-owned
`/opt/empire-ai/privileged-helper/releases/agent-identity-readonly-20261022v1`.
The existing `/run/empire-ops/privileged.sock` management RPC still
responds correctly and root's release `CHECKSUMS.sha256` passes.

The new `/run/empire-ops/agent-identity-readonly.sock` sends a readiness
handshake before receiving a bounded `identity_preflight` request.
From an ordinary `ubuntu` SSH process it deliberately replies
`trusted_managed_main_process_required`. Merely knowing an agent ID or
sharing the service's Unix UID is insufficient.

## Next process-origin proof

New source:
`empire_os/managed_agent_identity_socket_probe.py`, called only by
existing `scripts/run_graphify_coder_worker_20261020.py`.

The existing Coder **systemd main Python process** checks once for the
owner-private, mode-0600 marker:

`/srv/empire_os/runtime/coder/agent_root_preflight_once_20261022.flag`

Exact bytes: `EMPIRE_CODER_ROOT_IDENTITY_PREFLIGHT_ONLY_V1` and newline.
Wrong modes, owner, size, symlinks or changed content are refused.
The marker is consumed once before contacting the root helper.

The helper validates the *kernel* sender PID, UID, GID and cgroup,
systemd MainPID/execution phase and process creation time; the Coder
client checks the exact success response. No credentials or payload
contents are sent. The Coder journal only logs a small result shape:

`CODER_ROOT_IDENTITY_PREFLIGHT { ... }`

It never enables further agent registration, signs a trusted message,
reads/writes EmpireDB, sends outbound, modifies the canonical Department
work queue or changes the original Coder job semantics.

The Coder probe has a 3-second socket timeout and reports only a
failure class to journald if any step fails. A rejected probe will
never interrupt the original worker job.

## Sequence and acceptance

1. New modules + tests committed in isolated worktree and exact production
   branch, without modifying other agents' working files.
2. Read-only tests must pass; manual ordinary-user forged identity request
   must fail.
3. Arm the exact 0600 marker only once; no new systemd unit, timer,
   service restart or additional work item.
4. Observe an automatically scheduled existing Coder cycle and check:
   real `CODER_ROOT_IDENTITY_PREFLIGHT` receipt, kernel journald
   `_SYSTEMD_UNIT`, PID, UID and cgroup, marker consumed, legacy helper
   available, no activated peer communication.
5. The result must **not** be promoted into `registered_agent_count`.
   Only separate root-controlled signing and trusted public-key enrolment
   may establish ongoing agent credentials.

Until verified live, status is SOURCE_PREPARED_ONLY.
