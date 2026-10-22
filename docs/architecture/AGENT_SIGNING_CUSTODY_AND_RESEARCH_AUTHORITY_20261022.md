# EmpireOS Agent OS — Coder signing custody and real Research authority gate

22 October 2026. Main canonical repo `/srv/empire_os` (EmpireDB; NOT
a new A2A framework, Supabase or synthetic research worker).
Source-only planning and offline tests. No production credential, queue,
payment, outbound, agent message or managed-process restart.

## Production facts verified

- The existing root-owned `empire-ops-privileged-helper.service`
  is live on the protected release
  `/opt/empire-ai/privileged-helper/releases/agent-identity-readonly-20261022v1`.
- Coder process PID 4064398 successfully authenticated via the new
  read-only identity socket, with matching Linux journald UID, PID,
  unit/cgroup and invocation ID at
  `2026-10-22T16:38:55.454617+00:00`.
- Independent proof command:
  `PYTHONPATH=. ./.venv/bin/python -B scripts/review_coder_root_identity_journal_20261022.py --review-read-only`
- No persistent trusted Coder private key has been installed. The live
  root helper still exposes ONLY legacy service actions and the
  read-only, zero-authority identity-preflight socket.
- `DepartmentCollaboration` already checks pinned public Ed25519
  credentials. Existing isolated filesystem canary has demonstrated
  signed Coder ↔ synthetic Research messages, but NOT genuine managed
  peers or a production task.

## Prepared: root-held signer custody, not deployed

`empire_os/agent_root_signing_custody.py` contains an inactive
root-only key-loading and observe-only signing contract.

- Static future root custody directory:
  `/var/lib/empire-ai/agent-os-signing`;
  future Coder filename `empire_coder.ed25519`.
- Directory owner must be root, mode `0700`; exact private key owner
  root, mode `0400` or `0600`, 32 raw Ed25519 bytes, one hardlink
  and regular file only.
- Parent is opened by `O_DIRECTORY|O_NOFOLLOW`, secret by
  `O_NOFOLLOW|O_NONBLOCK` relative to trusted dirfd; strict `fstat`
  owner/type/mode/length validation before interpreting any bytes.
- Runtime entrypoint checks `euid==0`. Ordinary Coder / Research
  processes running as shared `ubuntu` CANNOT load this key.
- Future root-helper integration **must obtain Coder identity from
  `attest_connected_managed_worker()` directly**; accepting a
  user-provided `RootCustodyReceipt` from a socket frame would be an
  impersonation vulnerability.
- The only prototype output is a short-lived, observe-only
  `empire.agent-os.root-origin-observe.v1` receipt. Its detached
  Ed25519 signature is *domain-separated* from canonical
  `DepartmentCollaboration` signatures. It cannot be submitted as a
  `send`, `inbox` or `pickup` signature.
- The independent `verify_pinned_root_origin_observation()` requires
  a separately trusted Ed25519 public key; it refuses the signed
  receipt's own unpinned public key, malformed scope, wrong PID/role,
  future/expired one-minute evidence, tampering and false send authority.
  The verifier explicitly reports that **no atomic nonce replay ledger
  exists yet**. Signature freshness alone does not establish replay
  protection or an authorised collaboration transport.
- This source does not auto-create `/var/lib/empire-ai` or a key,
  install a root-helper handler, issue a signed message, write a replay
  store, register a public key or grant task authority.
- Test-suite keys are generated only in isolated temporary test
  workspaces, not in any production root service or shared `.env`.

Before deployment, the root-helper owner must separately approve a
protected root-owned release, pin an independently reviewed key
provisioning/rotation and revocation process, make a trusted
public-key registry tied to the specific existing Coder principal,
and authorize message-transport integration only when a genuine
recipient and canonical lease authority are both independently proven.
Simply creating a key is not authority to send.

## Actual Research runtime review

Read-only source:
`scripts/review_existing_research_worker_candidates_20261022.py --review-read-only`

Five existing, loaded systemd service candidates were evaluated:

| Existing source/service | Current identity decision |
| --- | --- |
| `empire-department-cycle.service` | Already pinned as Strategy Executive, NOT Research |
| `empire-buyer-acquisition-scout.service` | Multi-command buyer discovery/persistence workflow; NOT an attested independent Research agent |
| `empire-linkedin-revenue-department.service` | Narrow LinkedIn market research lane; potential specialist owner only after review |
| `empire-market-gps.service` | Market data reader; not yet a signed Research worker |
| `empire-predictive-intelligence.service` | Predictive materializer; not an attested Research message author |

At inspection each was loaded but no active main PID was present.
This is normal for scheduled `oneshot` services, not proof of a
persistent worker identity. A program source that has `research`
in its name is not a managed service identity.

`empire_os/agents/research_agent.py` and
`empire_os/agents/deep_research_agent.py` are repository source
assets. Legacy `empire_os/agents/AGENTS.md` references paths such
as `/root/empire_os` and old container models; that inventory is
not evidence of a current protected Research process or enrollment.

The authoritative currently pinned `MANAGED_WORKERS` has only Coder
and Strategy/Executive Operations; neither a registered general
Research worker nor an approved Research public signing key exists.

## Exact next gates

1. Authoritative Research owner identifies which *existing* single
   managed runtime should be the recipient and what exact canonical
   `market_intelligence/research` role and `intelligence_fabric`
   component that process may represent. No relabeling an executive,
   discovery or predictive service without owner validation.
2. Inspect pinned systemd ExecStart, UID/GID, cgroup and active MainPID
   in the actual process. Verify agent role/service binding and deny
   other same-UID processes using the existing root peer protocol.
3. Independent review of per-agent Ed25519 private-key ownership,
   separate trusted public-key enrollment, nonce/replay policy,
   tenant binding, key rotation/revocation and stable release hash.
4. Only then prepare one observe-only, capability-scoped Coder
   help request into the existing `DepartmentCollaboration` transport,
   canonical work linkage, genuine Research reply and independent
   review. No automatic `DONE`, prospect creation, outbound or funds.
5. Preserve founder-only Smart CRM Kanban tenant and role boundaries.

**Stage truth:** root custody source tested, verified Research worker
count zero, production trusted public keys zero, real peer messages
zero, production root-helper signing handler NOT installed.
