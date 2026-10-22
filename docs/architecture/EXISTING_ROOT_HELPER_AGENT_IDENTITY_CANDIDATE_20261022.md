# EmpireOS Agent OS — reviewed root-helper identity socket candidate

22 October 2026. The first real production Coder signed observation
was independently verified from journald (13:51:22 UTC, Coder main PID,
UID, unit/cgroup and Ed25519 signature), but was ephemeral and NOT an
enrolled identity.

## Existing protected runtime

Running `empire-ops-privileged-helper.service` remains a single root-owned
process pinned at:
`/opt/empire-ai/privileged-helper/releases/20261015-custody-audit-v5`.

The original Unix management socket
`/run/empire-ops/privileged.sock` remains functional and uses the same
fixed action and unit allowlists. Its pinned source is different from
editable `/srv/empire_os` and must NOT be replaced with a repository
symlink or dynamic PYTHONPATH.

## Isolated release candidate

The user-owned isolated candidate is at:
`/home/ubuntu/empire_releases/root_helper_agent_identity_candidate_20261022`

The stage builder
`scripts/stage_root_helper_agent_identity_20261022.py` copies only the
five exact original protected release files, asserts the original
helper SHA-256
`3d2d66c17c09900864eef3ca6776af0456269c655479c8d615c6762c566ec239`,
changes ONLY the existing helper's listener to serve TWO local sockets
inside its SAME running process, adds the two reviewed identity files,
and regenerates `CHECKSUMS.sha256` for every actual candidate file.

The pre-existing management request handler is byte-for-byte the same
inside the candidate. The new endpoint is separate:
`/run/empire-ops/agent-identity-readonly.sock`.

The new socket may only return **observe-only process provenance**:
no persistent signing key, no public-key registry, no AI model invocation,
no queue claim, no external send or money movement.

Its root-only peer authenticator requires:
- `SO_PEERCRED` and **per-message** `SCM_CREDENTIALS`, same PID/UID/GID;
- a server `EMPIRE_AGENT_IDENTITY_READY_V1\n` handshake before the worker
  sends its one framed request (ensuring SO_PASSCRED is already enabled);
- precise systemd unit/MainPID/User/Group, `activating/start` main worker
  phase, kernel cgroup, Linux /proc UID/GID, unchanged process start ticks;
- a pidfd, exact department role binding from static protected allowlist,
  no transferred FDs, no socket proxy, no user-asserted authority.

The candidate uses the protected system Python path and has no dependency
on editable EmpireOS source at runtime. Its public worker allowlist is
intentionally pinned in the root-side module rather than importing the
mutable department catalogue. Source tests can compare the allowlist
with the existing canonical worker definitions.

Current pinned candidate SHA-256:
- helper module: `20624ba83d1a8797d3ad649f947ec6fbf2619b66e6d2863e4c211246ba54f64e`
- kernel peer policy: `7365c18c8c186b221bd0bd2e7f82afb3ab2b1f130c41d477fae4c88ae7e5c036`
- read-only adapter: `757d916ea1eea7378d05781cecabc09f7b6b58da1a26cb9ed741a19fafc2cf61`
- checksums manifest: `938a397a4157685912dfd50b2dcd2ce0a670aa732ee43d94eae904c55dbea436`

## Executed verification (does not touch production helper)

- `scripts/stage_root_helper_agent_identity_20261022.py --verify` PASS;
- protected candidate `sha256sum --check CHECKSUMS.sha256` PASS,
  six entries;
- test helper launched **unprivileged** with candidate package and
  temporary Unix sockets: legacy service-status RPC still worked;
  an unprivileged process could not gain an agent identity;
  malformed identity actions failed;
- 108 relevant regression tests PASS;
- `scripts/deploy_root_helper_identity_readonly_20261022.sh --check`
  returned `ROOT_HELPER_IDENTITY_DRY_RUN_PASS` while the existing
  root-owned production helper stayed unchanged.

## Separate protected production switch — not yet performed

The guarded deployment script is:
`scripts/deploy_root_helper_identity_readonly_20261022.sh`.

Without arguments or with `--check`, it only verifies.
A human operator must separately inspect the candidate and its pinned
checksums, then explicitly run the exact `--apply-founder-approved`
argument as root. It copies to the protected new root-owned release,
checks digests after copying, creates ONLY
`/etc/systemd/system/empire-ops-privileged-helper.service.d/95-agent-identity-readonly-20261022.conf`,
then restarts the existing helper, verifies legacy RPC status and that
the new identity endpoint DENIES an unmanaged process. A failed switch
attempts exactly one restoration of the original pinned release.

A separately gated exact-override rollback script is
`scripts/rollback_root_helper_identity_readonly_20261022.sh`.
Do not assume either was invoked merely because source files were
committed.

## Remaining activation

A READ-ONLY identity socket is not agent communication. Even after this
separate release is approved and proven live, the real Coder service
needs a one-shot **client** probe using the READY handshake and its
actual main process to prove that root's per-message identity validator
accepts it. Then Research must have its real managed worker identity
independently verified; currently no separate proven Research worker.

**Do not provision a persistent Ed25519 private key under shared `ubuntu`
UID as a shortcut.** Root-custodied, bounded-signing operations,
registered public keys, scoped canonical work leases, real help/reply
and independent review are later distinct protected gates.

No production agents were registered, no existing root helper was
restarted, and no outbound, payment, database or queue writes occurred
in this release preparation.
