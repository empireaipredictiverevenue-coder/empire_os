# EmpireOS existing Coder process — live signing observation receipt

Date: 22 October 2026. Canonical EmpireOS, NOT a new agent framework.

## Real production evidence

The existing `empire-coder-worker.service` was observed running as a
Type=oneshot service in `activating/start`, with its real MainPID,
`ubuntu` UID and correct kernel cgroup all independently verified.

The versioned one-time observation flag, owned by `ubuntu` with mode
0600 and exact bytes, was consumed by an ordinary scheduled run of the
**existing** Graphify Coder wrapper. No additional worker invocation was
issued and no separate task was enqueued.

A transient Ed25519 private key was generated inside the real Coder
Python process, used to sign an exact bounded metadata envelope and
discarded. No private key was written to the repository, environment,
runtime store or logs.

The **actual** systemd journal entry contains a signed public observation
with kernel-associated journal metadata. The independent read-only
`scripts/review_coder_signing_journal_20261022.py` validates:

- The Ed25519 signature against the public key in the signed receipt.
- The payload PID against journald's trusted `_PID` field.
- `_UID` against the existing `ubuntu` account.
- The exact `_SYSTEMD_UNIT` and `_SYSTEMD_CGROUP`.
- Presence and format of the systemd invocation ID and stdout transport.
- Timestamp alignment of the actual journal record and signed content.
- Exact explicit safeguards forbidding privileged claims or treating
  an ephemeral self-issued key as a trusted registered agent.

Result observed on host:

```text
status=VERIFIED_HISTORICAL_MANAGED_CODER_EPHEMERAL_SIGNATURE
observed_at_utc=2026-10-22T13:51:22.505007+00:00
ed25519_signature_verified=true
trusted_journal_pid_uid_cgroup_unit_match=true
verified_process_signing_observation_count=1
registered_agents=0
trusted_agent_registration_verified=false
live_message_transport_verified=false
production_queue_modified=false
execution_authority=none
```

Run again any time without credentials, external calls or writes:

```bash
cd /srv/empire_os
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  scripts/review_coder_signing_journal_20261022.py --review-read-only
```

The one-time marker was consumed (not left armed) and did not change
systemd services, grants or financial/outbound authority.

## Important boundary

A self-issued short-lived key proves this particular worker process
could perform cryptographic signing *at that moment*. It does NOT
establish an externally pinned, persistent agent identity or make
future messages trustworthy. Kernel-assigned journal PID/cgroup
metadata strengthens provenance of the event, not authority of the
public key beyond this event.

The Coder and several other legacy workers still run as shared
`ubuntu` UID. Provisioning persistent private keys into that
account's shared environment would permit cross-agent impersonation.
Do NOT do that.

For real agent-to-agent message pickup, next gates are a trustworthy
owner/host-root provisioning and broker key-registration process,
separate key-access boundaries for Coder and Research (or a root-held
signing operation strictly scoped to an attested unit/cgroup), exact
tenant/capability binding, replay expiry, and independent review of one
bounded genuine work item before promotion. The canonical queue remains
the only authority for task leases and status.

No extra agent/service, public HTTP route, DB migration, paid model
request, external send, payment or production work-queue mutation
occurred during the signing observation.
