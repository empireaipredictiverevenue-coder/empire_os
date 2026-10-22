# EmpireOS existing-agent signed handoff — real isolated protocol canary

22 October 2026. **No new agent framework, service, cron, job queue,
company or database.** Reuse the existing EmpireOS `DepartmentWorkQueue`,
department role catalogue, Kanban projection and internal collaboration.

## Cryptographic trust improvement

`empire_os/department_collaboration.py` now accepts either the existing
injected HMAC credential for backwards compatibility or an explicitly
registered `AgentPublicCredential` containing **only** an Ed25519 public
verification key and an existing validated Department role profile. The
trusted verifying side needs no agent private signing keys.

All signed operations still validate their exact envelope, target role,
tenant scope, allowed components, signed message sender/recipient and
task identity. Invalid Ed25519 signatures, modified files, wrong signers,
replayed pickup nonces and cross-tenant requests fail closed.

**No key issuance or enrolment** happens on import. The new signature
mode is not proof of an independently attested real worker process.
Proper private signing credentials must be provisioned under verified
service-specific identities by the existing runtime owner, and public
keys registered by the trusted control plane only. The current
`ubuntu` Unix UID is shared by several managed jobs, so file mode
`0600` under that shared UID does NOT provide full agent-key isolation.
Do NOT put all private agent keys in a shared package or environment.

## One-shot canary on the actual EmpireOS host

One-shot:
`scripts/run_agent_collaboration_canary_20261022.py --run-isolated-once`.

Uses temporary, one-shot Ed25519 private signing keys only in memory,
real filesystem instances of the canonical queue and collaboration
message store under an auto-deleted temporary directory, two *existing
department/role definitions* and the unchanged production queue code.

The canary performs and independently verifies:

1. Creates exactly one **synthetic observe-only** local work item.
2. Claims it by the scoped engineering role using a signed Ed25519 pickup,
   verifies one active queue lease and rejects replay.
3. Sends a signed task-linked help request to the existing
   market-intelligence research **role profile**, not a model inference.
4. The researcher role reads its signed inbox and returns a signed
   evidence reply to the original task/message.
5. A verifier with **only public keys** checks both immutable message
   records and recipient/reply/work ID chaining.
6. Completes the *synthetic cryptographic protocol exercise only* in
   that isolated queue using non-execution completion semantics.

This is **NOT** a commercial task, an independent production agent review,
a deployed research execution, or a real agent-to-agent runtime session.
Production queue, CRM, credentials, external communications, treasury
and mainnet are NOT accessed or changed.

The actual one-shot host receipt was:

- status: `ISOLATED_CANONICAL_QUEUE_AND_ED25519_CHAIN_PASS`
- helper request: verified
- signed reply: verified
- two on-disk message records: verified
- replayed pickup: rejected
- local queue: `ready=0, running=0, done=1` (synthetic only)
- live agent communication: **false**
- actual managed worker registration: **false**
- external outbound and funds movement: **false**

Private (non-sensitive) operational receipt:
`/home/ubuntu/empire_releases/agent_collaboration_protocol_canary_20261022/isolated_signed_handoff_receipt.json`

SHA-256:
`747d730ed1c6a8a3518e9fab9931b82003576d5aa5c7d58343fec1e798b901bc`

## Remaining production activation gates

1. Complete real authenticated founder CRM Kanban 200 using existing
   `scripts/verify_founder_crm_agent_kanban.py`; do not send passwords
   or bearer tokens through chat.
2. Verify dedicated per-service identity separation (or equivalently
   enforced trusted kernel/process boundary) for existing active workers
   and provision distinct private signing credentials without exposing
   them to other `ubuntu` processes.
3. Register pinned public verification keys via the existing governed
   control plane, with exact role/component/tenant bindings. Avoid
   broadening the existing worker's authority.
4. Wire sign/send/inbox/pickup into one real managed worker cycle;
   prove execution provenance, timeouts, retries, leases, independent
   review and rollback without using generated fake results.
5. Only then label real production agents connected and allow controlled
   collaboration; no blanket autonomy, outbound or payments.


## Managed Coder identity bridge (source only, not activated)

The existing `empire_os/agent_runtime_identity_evidence.py`
`preflight_local_managed_binding` now also accepts a
`ManagedWorkerSigningIdentity` containing a process-local Ed25519 private
signer and the **already pinned** existing Coder department profile.
After matching the real systemd main PID, Linux UID and cgroup, it returns
only a public-key SHA-256 fingerprint and the explicit result
`trusted_broker_key_registration_still_required=true`.

The role signer can sign a canonical collaboration envelope while the
broker verifies the signature from its **public-only** registry; regression
tests confirm that a wrong process PID does not pass identity preflight.
This bridge does not start an agent, load a secret, register a public key
in a production trust store, connect to a model, modify live work or
implicitly switch on communications. Signing keys must be provisioned by
the separately authorised service owner and remain isolated across
workers (shared `ubuntu` UID is not sufficient).
