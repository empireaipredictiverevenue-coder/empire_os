# EmpireOS existing root helper — strict managed-agent peer identity

22 October 2026. Dedicated credential isolation milestone, **source-only**.
Do not describe this module as an active broker, a live signed agent, or
an autonomous task worker. No new framework, daemon, agent, token, key,
task, payment integration or communication authority was created.

## Production truth

- The **existing** `empire-ops-privileged-helper.service` is running
  as `root`, pinned at:
  `/opt/empire-ai/privileged-helper/releases/20261015-custody-audit-v5`.
- Existing UNIX socket:
  `/run/empire-ops/privileged.sock` (root:ubuntu, mode 0660).
- Its existing allowlisted service-management actions check peer UID
  through `SO_PEERCRED`. This is enough for its current published
  allowlist; **it is not proof of a specific agent** because multiple
  services share Linux UID `ubuntu`.
- The Coder and Department cycle each run short-lived `oneshot` main
  processes as `ubuntu`; their real operating phase is
  `ActiveState=activating, SubState=start`.
- Existing Coder signing journal receipt passed independent verification:
  one genuinely observed ephemeral Ed25519 key, but **zero**
  trusted persistent agent registrations.

## New inactive security primitive

`empire_os/agent_peer_identity.py` supplies a fail-closed, opt-in
root-helper-only peer-origin validator for the two already inventoried
managed roles. It does **not** modify `ops_privileged_helper.py` or any
existing root-owned service installation.

The future trusted helper, when separately reviewed and deployed, must:

1. Receive a single bounded, read-only `identity_preflight` frame over a
   local Unix stream. No key material or task body is allowed.
2. Compare kernel connection-time `SO_PEERCRED` against
   **per-message `SCM_CREDENTIALS` via `SO_PASSCRED`**. Requiring both
   denies socket-file-descriptor handoff between same-UID processes,
   which is otherwise a path around a connection-only check.
3. Reject file descriptor transfers (`SCM_RIGHTS`), unknown
   ancillary data, oversized/truncated/fragmented frames, unexpected
   JSON fields, malformed/short nonces and non-root broker processes.
4. Pin the connected process using `pidfd_open`, compare kernel UID/GID
   and cgroup, systemd Id/User/Group/MainPID, and Linux process start
   ticks before/after the systemd identity lookup to deny PID reuse.
5. Require exactly `activating/start` for the allowlisted oneshot main
   process, never `start-pre`, `start-post`, worker siblings, other
   cgroups, stale PIDs, proxy processes or a mere shared UID.
6. Return a **zero-authority, observe-only** departmental role binding:
   `trusted_broker_registration=false`,
   `signing_key_issued=false`,
   `message_transport_activated=false`,
   `queue_write_authority=false`.

The function checks authority **locally on the root helper**, not by
trusting a socket client's JSON claim of PID, UID, role, signature,
department, cgroup or tenant.

## What is NOT yet enabled

- The currently running root-owned Ops helper continues to use its
  original pinned service release and original action allowlist. We
  did **not** restart, edit or replace it.
- There is no root-custodied persistent per-agent key, public-key
  registry, broker-operated sign/send operation, receiving mailboxes,
  task pickup, review or model runtime connected to this new policy.
- No credential is stored in a common `ubuntu` .env, directory,
  process environment or repository.
- Service-local identity evidence is NOT automatically tenant authority,
  runtime permissions, trust enrollment or successful fulfilment.

## Next controlled release gate

To use this for genuine collaboration, the existing Ops privileged
helper owner must prepare an exact pinned release with a narrowly
allowlisted **new, read-only identity-preflight operation**. Crucially,
its read path must call the kernel-credentialed `recvmsg` checker,
rather than merely adding a JSON `agent_id` to the old shared-UID
`_serve_connection` path. Review the current protected pinned release,
test the root helper's original action allowlist and rollback, and
seek explicit founder approval before deployment.

After genuine root-authorised origin binding succeeds for both Coder
and the chosen Research worker, a separate staged change can bind
root-custodied signing operations to a pinned role/tenant/component and
the existing `DepartmentCollaboration` public-key verifier. Then test a
real, observe-only help request/reply linked to an existing canonical
work item, independent evidence review, and unchanged denial of
outbound/financial actions. Do not self-approve task completion.

## Test scope

The offline tests exercise actual UNIX `socketpair()` kernel
credentials plus synthetic systemd/`/proc` evidence, including
per-message credential mismatches, SCM_RIGHTS rejection, root-only
entrypoints, wrong cgroups, wrong GID/UID, invalid phases and PID
reuse. They do not make claims of a live root helper protocol.
