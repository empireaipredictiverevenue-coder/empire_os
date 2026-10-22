# EmpireOS — live Coder oneshot identity and signed observation

22 October 2026. Existing infrastructure only; **no agent framework,
new worker, database, service, queue, outbound or payment authority**.

## Correct real systemd state

The existing `empire-coder-worker.service` is a Type=oneshot service
running the previously deployed Graphify wrapper
`scripts/run_graphify_coder_worker_20261020.py --once` under `ubuntu`.
At the moment the actual Coder Python ExecStart runs, systemd reports
**ActiveState=activating, SubState=start, MainPID>0**, NOT active/running.
The previous identity checker inadvertently rejected this legitimate
worker state.

The corrected `inspect_existing_worker()` now accepts
`activating/start` for the exact allowlisted worker unit **only when**
systemd's Id, main PID and expected username, Linux /proc UID, and
kernel unit cgroup are all correct. It rejects
`activating/start-post`, `start-pre`, exited, dead and failed. It
does not reinterpret the Department hook phase as Coder identity.

An actual read-only check against EmpireOS captured a live Coder main
process satisfying all checks with
`oneshot_execstart_observed=True, managed_process_evidence=True`.
This proves a live managed OS process, **not that signing credentials
were registered**.

## Bounded in-process Ed25519 observation

`empire_os/managed_agent_signing_probe.py` contains one ephemeral
signing canary, never a trusted signing key issuer. Its entrypoint:
- Is called only in the existing Coder service main Python process;
- Performs the real `preflight_local_managed_binding()` without
  test-injected PID/process callbacks;
- Generates one short-lived Ed25519 private key **in memory only**,
  signs a public, noncommercial, non-executable metadata envelope and
  discards the key;
- Produces a publicly verifiable signed **self-issued** receipt with
  explicit `trusted_broker_registration=False` and
  `production_collaboration_activated=False`;
- Contains no tenant data, buyer records, task content, credentials,
  funds or production work completion claims.

A self-issued ephemeral public key is **not** a verified persistent
worker-to-broker identity. A separate trusted root/systemd process
authority must later provision keys with true isolation (several
workers run under the same `ubuntu` UID), bind the public key to the
permitted scope and register it in the existing collaboration plane.

## Existing Coder lifecycle integration

The deployed existing Graphify worker gains a best-effort
`_observe_existing_worker_signing_identity()` hook before the
unmodified Coder job logic. It is OFF by default.

It can be enabled for a single already-scheduled worker cycle by
creating this exact one-time marker with owner `ubuntu`, mode 0600:

`/srv/empire_os/runtime/coder/agent_signing_observe_once_20261022.flag`

Exact bytes: `EMPIRE_CODER_PROCESS_SIGNING_OBSERVE_ONLY_V1` followed by
one newline. On the next Coder ExecStart the hook checks ownership,
regular-file status, mode, size, exact contents and no symlink,
then consumes the marker before running the bounded read-only probe.
It prints a `CODER_AGENT_SIGNATURE_OBSERVE` JSON line to the existing
Coder systemd journal containing only public receipt fields.
The fallback `EMPIRE_CODER_AGENT_SIGNING_OBSERVE=1` environment toggle
remains available but will cause repeat observations while enabled.

A malformed marker or probe failure NEVER alters existing Coder job
execution. No extra job, message, queue lease, Web access or financial
permission can be created through this marker.

## Acceptance

Relevant tests exercise:
- true and false oneshot phases, kernel UID/cgroup and MainPID;
- temporary signer envelope validation and tamper rejection;
- refusal to recognise self-issued proof as trusted registration;
- exact owner-private one-shot marker, symlink and wrong-mode denial;
- default off and nonblocking failure;
- unchanged existing Ed25519 task protocol and HMAC regressions.

After source integration, arm this limited marker only when operator
chooses to observe a naturally scheduled existing worker. Verify the
public signed journal receipt and service/queue health. A real-world
agent-to-agent handoff, trust broker registration, and independent
production review **remain held** until per-process secret isolation
and trusted provisioning are demonstrated.
