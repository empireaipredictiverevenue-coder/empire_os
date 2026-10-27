# Agent ownership authority — original Execution Plane owner pickup

Date: 27 October 2026
Source: explicit founder request to stop cross-agent workstream collisions.
Status: **PRIVATE CANDIDATE, NOT DEPLOYED.** No standing owner assignments created.

## Observed root cause

The original `empire_os/execution_lease.py` prevents simultaneous overlapping domain/path **leases**. But a worker can request a lease using an owner string it supplies, and the lease expires. This is coordination, not standing founder-authorised ownership. The canonical architecture (`docs/AGENT_TOOL_EXECUTION_PLANE_ARCHITECTURE.md`) already names the Execution Plane as the owner of this control. This patch does not replace that system.

A ChatGPT chat with direct remote shell or API write access can also bypass the Execution Plane. **No code-only patch inside this one module prevents such direct calls.** Live enforcement requires limiting those write paths to the governed original gateway.

## Candidate changes

- `empire_os/agent_owner_authority_review.py`: pure, fail-closed Ed25519 signed founder-policy and per-job ticket verifier, exact authenticated worker identity/job/capability/department binding, pinned founder policy hash for revocation, exact file paths and domain leases. Rejects missing/invalid policy, unknown owner, overlapping assignments, out-of-lane path, forged or expired ticket, missing lease coverage and changed digest.
- `acquire_owner_authorized_lease`: owner-reviewed adapter that verifies the standing assignment and job ticket BEFORE using the **existing** `ExecutionLeaseManager.acquire`, not a second lease manager.
- `tests/test_agent_owner_authority_review_20261027.py`: synthetic-only, no named production owners. Tests positive and multiple negative cases against existing lease manager.

## Mandatory original-owner integration review

1. Confirm original governance owner; review the candidate in branch `review/agent-owner-authority-20261027`. Do **not** cherry-pick into a dirty live tree.
2. Founder reviews **one central exact workstream-to-principal-to-path ownership register**. UNKNOWN/ambiguous assignments remain unowned and blocked for mutation, not self-assigned by a worker. No real policy or signing private key exists in this candidate.
3. The original trusted issuer securely signs the current owner policy and individual bounded internal-write job tickets. Private signing key must be inaccessible to all workers, ChatGPT chats, repository and runtime output. Trusted public key and current policy digest must be pinned by the original trusted control-plane owner, not provided by the requesting worker.
4. Derive `authenticated_worker_principal` from trusted service/gateway identity, **never** from an agent's `owner` field, prompt or ticket. Reassign by founder-authorised, pinned policy revision. Review clock/rollback and ticket revocation, including replay and use-once ticket consumption.
5. Bind the validator at every original mutating entry point: `empire_os/hermes_control.py`, `empire_os/pi_sandbox_runner.py`, `empire_os/empire_coder_sandbox_runner.py`, `empire_os/coder/worker.py`, with normal `ExecutionRequest`/allowed-path validation and the existing lease lock. Confirm actual changed paths are checked after worktree/sandbox apply as well.
6. Govern direct production mutators separately (shell/Desktop Commander, Git, website, CRM, email plugins and root deploy operators) through authenticated roles and least-privilege OS/service permissions; this test-only candidate does **not** restrict them.
7. Conduct existing owner integration tests, rollback rehearsal, service/queue compatibility verification and founder-controlled release. Do not silently enable enforcement without preserving original working jobs and explicit affected-owner acceptance.

## Acceptance

No unowned or cross-owner mutation can obtain a lease through governed workers, even after an old lease expires; a valid assigned worker can lease an exact scoped path. No other agent can fabricate a founder ticket or edit standing policy. Direct out-of-band writes cannot bypass the adopted production gateway. No outreach/payment/SEO/site mutation follows from ownership assignment alone.

## Current constraints

This branch is **not a deployed organisation-wide lock**. Existing workers still use the unmodified original `ExecutionLeaseManager`; signed ticket issuance, trusted service identity, founder-assigned policy, protected execution gateway, and live integration are all pending. No service, timer, website, CRM, inbox, buyer acquisition or Awin owner was modified.


## 27 October original live permission audit — read-only

The live original execution-plane services `empire-hermes-control.service`,
`empire-coder-worker.service`, and `empire-coder-verify-drain.service`
all report `User=ubuntu` and `Group=ubuntu`. The repository root is
`ubuntu:ubuntu` `0755`; `empire_os/` is `ubuntu:ubuntu` `0775`.
The current lease state is mode `0600` but also owned by `ubuntu`.
The services retain different systemd path-level write restrictions,
but that does NOT establish independent worker identities or prevent
out-of-band mutation by the shared `ubuntu` principal.

The original mutation entry points inspected are:

- `empire_os/hermes_control.py`: around line 1532;
- `empire_os/pi_sandbox_runner.py`: around line 311;
- `empire_os/empire_coder_sandbox_runner.py`: around line 364;
- `empire_os/coder/worker.py`: around line 368.

Each directly calls the existing `ExecutionLeaseManager.acquire`.
The dispatcher alone is NOT a complete enforcement boundary. This is
current source inspection, not proof every possible direct writer was found.

### Original owner's rollout conditions

1. First seal and authenticate the founder-reviewed exact assignment register.
   The adjacent `FOUNDER_WORKSTREAM_OWNER_REGISTER_DRAFT_20261027.json`
   names proposed **roles**, not real authenticated principals. All entries
   are unapproved. It must never be used as a signed policy or imported as
   production authority.
2. Route ALL four verified mutating worker entry points, including direct
   worker invocation paths, through the signed owner verifier, *then* the
   existing lease manager. Reject requests without tickets; no observe job
   should need a mutation ticket. Add existing dispatcher admission checks as
   defence in depth, never as the sole control.
3. Bind actual modifications to the signed allowed-path set after the
   sandbox/worktree completes, before changes can be promoted or published.
   The draft now includes a one-use receipt under the existing lease lock,
   but original-owner-protected custody, revocation, reconciliation and
   adoption must still be independently reviewed before production.
4. Make producer and consuming service principals independently
   authenticated. Restrict write permissions by workspace and deploy role
   rather than relying on every worker's common `ubuntu` identity.
   Test unprivileged read-only researchers and verifier access; don't
   recursively `chown` or `chmod` the live repository.
5. Gate direct GitHub, Desktop Commander, root shell, website, outbound mail,
   billing and database writes at their existing connector/service
   permission boundaries. No in-Python execution-plane guard can prevent a
   separate authorised direct write channel from bypassing it.
6. Rehearse under original owner control with actual queues, timers,
   root-custodied rollback and stale-owner/reassignment scenarios. The
   draft is ready for integration *review*, not an unconditional cutover.

**Recorded result:** production owner identities and release signatures
have not been issued; direct shell/plugin write restrictions are not
confirmed. This remains `OWNER_INTEGRATION_HOLD`, not an organisation-wide
ownership lock.


## Private integration-readiness acceptance check

Added read-only candidate `empire_os/agent_owner_integration_readiness.py`.
The owner can run the same static inspection against production without
mutating services, scheduling jobs, making signed assignments or granting
lease access:

```bash
cd /home/ubuntu/empire_worktrees/agent_owner_authority_review_20261027
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B - <<'PY'
from pathlib import Path
import json
from empire_os.agent_owner_integration_readiness import inspect_original_owner_integration
print(json.dumps(inspect_original_owner_integration(Path('/srv/empire_os')),
                 sort_keys=True, indent=2))
PY
```

The tool intentionally emits `ORIGINAL_OWNER_INTEGRATION_HOLD`, never
production enforcement PASS based on static code patterns. The original
execution-plane owner must provide independent authenticated policy custody,
worker identity checks, real mutator integration, replay protection and
out-of-band permission proof. A pasted adapter name is not execution proof.

A further private fix rejects nested `.env.production` and `.env.local`
as mutation paths. Unit coverage is synthetic; no production credentials,
agent identities or owner assignments were created.

### Repository handoff caveat

At 27 October the private review branch was observed **4,559 commits ahead
of `origin/main`**. Do not push the private production-history branch as a
GitHub PR or merge all ancestor commits into upstream. The review owner
should examine only the three scoped candidate commits and their exact
patches in the shared local EmpireOS worktree; reconcile against their
current base through a separate controlled original-owner release.


## Draft PR security-hardening review — 27 October, no live activation

A further red-team review found that the first candidate lease adapter
did not independently bound the existing lease lifetime by the signed
job ticket's expiry. The draft now **fails closed** when a caller
requests a lease exceeding its still-valid ticket lifetime, and rejects
lease durations that the original lease manager would otherwise silently
clamp. This is additional candidate defence, not protection against
direct calls to the unmodified production lease manager.

The original owner also needs **post-mutation evidence**, because an
approved relative path can point to another lane through a symlink or
hard link inside a worktree. The additive
`attest_actual_worktree_changes` helper checks that an independently
observed, exact changed-file set matches the previously signed file set
and contains only local regular single-link files, with no symlinks in
their ancestor path. It is conservative: deletion, rename, missing
file, hardlink or symlink attempts require **separate review**.

**Mandatory trusted inputs:** The original owner must derive the worktree
root from the protected execution service and the actual changed paths
from authenticated Git/sandbox readback. A worker's self-reported list
cannot count as independent evidence. The helper has not been installed
at any live mutation, promotion or publication boundary.

**Still outstanding:** The later section adds a test-only one-use ticket
receipt that survives lease release and rejects replay, but its security
depends on original-owner-controlled ledger custody and distinct worker
identities; neither is installed. Signed ticket revocation, secure issuer
custody, receipt rotation/reconciliation, service identity separation and
out-of-band shell/plugin access must be independently approved before
any live lock is called enforced. Synthetic tests are not production proof.


## Draft PR one-use ticket replay control (27 October, review-only)

The next isolated candidate reuses the **existing** `ExecutionLeaseManager._locked`
file lock to serialize a valid signed ticket, the current lease-conflict
check and consumption of the one-use ticket identifier. It does **not**
introduce a second scheduler, agent, lock service, database or production
worker. It stores only SHA-256 digests of signed ticket IDs in a private
`0600` sibling receipt under the *original* lease-manager root.

The receipt is **not** silently created or reset by normal job execution.
For tests, `provision_owner_ticket_receipts_for_review` explicitly
initializes it inside a temporary synthetic lease root. Production
initialization requires the original execution-plane owner's protected
custody, identity separation, backup strategy and first-run/rollback
approval. A missing, malformed, symlinked, invalidly owned or corrupt
receipt fails closed. Retention is bounded to 4,096 consumed IDs and
**capacity exhaustion is a HOLD**, not a licence to delete or rotate history.
The original owner must plan secure archival/rotation before the cap.

The record is persisted and fsynced before the existing lease state is
committed while the original lock remains held. An injected failure after
consumption may therefore **burn** a valid ticket without granting work.
The permitted recovery is issuance of a *new* authenticated ticket, not
deleting the receipt or recycling an old ID. Independent worker
identities, trusted ticket issuance, replay-custody permissions, complete
release-time checks and out-of-band GitHub/shell/plugin write restrictions
still require original-owner integration and attestation.

The private adapter invokes some internal `ExecutionLeaseManager`
functions to share its lock and original conflict semantics. This is
a **review-only compatibility assumption**, not permission to change or
deploy the original lease manager. The owner must assess maintenance
coupling and assess crashes, concurrent processes, corruption,
principal isolation and rollback on its actual infrastructure.

**No signed owner policies, real ticket keys, authenticated worker
assignments, service permissions, production receipt, production agent,
new timer or live execution state were created by this testing.**

## Founder identifies as accountable original governance owner (27 October)

The founder explicitly stated in ChatGPT, **"i am the owner and i do auth"**.
The connected repository administrator account was independently read back as
`empireaipredictiverevenue-coder` with GitHub permission `admin`, and the
original tracking issue #146 was assigned to that same authenticated account.
Thus **there is no unidentified second human owner whose approval should be
requested repeatedly** for this governance integration. The founder has
approved proceeding with it and owns the decision to adopt it.

`/.github/CODEOWNERS` now declares that existing account as the reviewer
for a narrow set of Agent & Tool Execution Plane governance files only.
It does not assign or take over SEO, website, Buyer Acquisition, CRM,
Finance or any other distinct agent implementation workstream. CODEOWNERS
is a review declaration: approval enforcement needs independently configured
GitHub branch protection/rulesets, and GitHub generally does not allow a PR
author to approve their own change. It does not prevent direct shell writes.

**Technical separation preserved:** the founder's GitHub/admin identity is
not an authenticated Hermes/Pi/Coder service principal. The six proposed
runtime lane assignments remain unapproved and no production ticket issuer,
private signing key, active enforcement gateway, GitHub branch protection,
review approval or production rollout is created by this record. The
founder's strategic approval is not a blanket permission for agents to
self-assign or modify another workstream.


## Original shared execution-lease enforcement boundary (review branch only)

The original `empire_os/execution_lease.py` is now part of this *draft*
review diff. Ordinary `ExecutionLeaseManager.acquire` verifies a
**root-owned, mode 0644** marker at
`/etc/empire_os/owner_lock.enforced`. The containing directory must be
root-owned and non-group/world-writable; the marker must be a regular
single-linked file of exact bytes `ENFORCE\n`. An unsafe, malformed or
unreadable present marker fails closed. The check is repeated after
acquiring the existing exclusive lease lock to reduce activation races.

When the marker is absent in the existing trusted directory, **original
lease behaviour is preserved**, including unchanged observer operations.
An environment variable cannot turn the lock on or off. When the
root-controlled marker is present, all plain `.acquire` calls—including
Hermes, Pi, Empire Coder sandbox and the structured-patch worker—must
return `SIGNED_WORKSTREAM_TICKET_REQUIRED`, regardless of a
worker-supplied `owner` label.

This is **not** yet full live enforcement. The proposed signed-ticket
adapter reuses the original flock but has **not** been wired into the
four workers with independently authenticated principal and issuer
credentials; directly enabling the marker now would disable legitimate
mutating jobs instead of allowing approved ones. The original release
owner MUST NOT install the marker until all mutating paths have an
authenticated signed-ticket entry point, ticket issuance/custody,
postflight attestation and operational rollback.

Original direct `ExecutionLeaseManager.acquire` remains compatible in
its off state; tests verify that the protected marker rejects plain
mutators and untrusted configuration, and regression suites exercise
existing worker behaviour. This gate does NOT prevent an external agent
with direct write privileges from ignoring the lease manager, nor does
it secure private `ExecutionLeaseManager._write` against processes
sharing its Unix principal. Root/shell/GitHub/connector and separate
service permission boundaries must be established before activation.

**Activation receipt required:** original founder-controlled operator
reviews deployed code digest, authenticated per-service IDs, revocation
and journal custody, fully signed and pinned owner assignments, root
marker mode and hash, concurrent work/leasing quiescence, fault-injected
recovery, reversible marker removal, all four legitimate-job success
cases, unassigned-job denials and read-back on live services.
**No marker, service override, production package or runtime credential
was installed by this review candidate.**
