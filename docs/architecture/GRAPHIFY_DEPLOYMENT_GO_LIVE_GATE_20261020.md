# Graphify — production release gate and deployment checkpoint

**20 October 2026, founder-approved Graphify integration scope.**
This is a release *verification* of the existing production code adapter,
not a new agent, worker, authority, financial system or campaign.

## Current state

The production Graphify adapter is ALREADY installed on the existing
empire-coder-worker.service, whose original job queue remains authoritative.
The one-shot timer, no-restart opt-in and read-only prepatch observation are
enabled. The current Graphify code-only AST has 20 authentic attested Python
modules, 400 nodes and 1,116 static relationships.

The deployment release gate is a new reusable, read-only quality check.
It verifies ALL of the following from actual production sources:

1. Graphify snapshot file and source-manifest attestation are current,
   including four real known symbol matches and unchanged indexed sources.
2. The original private graph release receipt hashes match the published
   code graph, and its earlier private graph and manifest backups match
   their original digests. The receipt and backups retain private mode.
3. The existing, ORIGINAL systemd oneshot Coder service uses the
   Graphify-aware wrapper, with BOTH explicitly enabled Graphify flags,
   a successful last service result and the existing active timer.
   An inactive service with result=success is normal between one-shot jobs.
4. A genuine current source retrieval returns context.py for
   ContextBuilder; the real models.py code impact returns known extracted
   dependents without authorising edits.
5. All Graphify-owned installed source files remain clean in the
   production Git checkout.
6. The original Coder plan-promotion, founder directive and shared dirty
   checkout gates are checked separately. They are NOT quietly redefined
   as Graphify defects or implicitly converted into execution authority.

Run on EmpireOS:

    cd /srv/empire_os
    PYTHONPATH=. .venv/bin/python -B \
      -m scripts.review_graphify_deployment_readiness_20261020 --read-only

The command emits a sanitized machine-readable JSON with two distinct
results: graphify_release_status and coder_implementation_status.

## Initial real-source signoff

The first end-to-end read-only signoff from the Graphify integration
worktree reported:
- Graphify release: DEPLOYED_CODE_ADAPTER_VERIFIED
- Coder implementation: HELD_BY_EXISTING_OWNERS
- No Graphify release blockers
- Rollback receipt and old graph hashes verified
- Existing timer active, worker entrypoint/flags correct, service healthy
- 20/20 attested real Python modules unchanged, 400 nodes, 1,116 edges
- ContextBuilder genuine source retrieved, models.py returned 9
  extracted direct dependency review candidates
- Canonical implementation blockers still include missing authenticated
  IMPLEMENT promotion contracts, unrelated dirty code owners, and
  historical provider/model errors. No legitimate owner was overridden.

The unit checks exercise each failure state and ensure clean code deployment
can NEVER be mistaken for a proven successful IMPLEMENT outcome.
No synthetic customer data, fake leads, fake payments, invented
authorisation or fabricated job receipts are generated.

## Rollback and boundaries

The original private graph backups and deployment receipts remain
available. Changing the release gate cannot authorise automatic code
patches or commercial tasks, and no production worker is restarted by
running the check. The existing opt-in Graphify observation drop-in can
be disabled by its previously documented scoped rollback command.

The release gate currently runs on demand. It does NOT silently install
an additional monitor, background worker or scheduled service. Any
scheduled rollout health integration belongs with the existing Coder
operations/service owner and should consume the same JSON status codes.

**Deployment definition:**
- Graphify code adapter deployed and usable = verified today.
- Independent production IMPLEMENT success = NOT yet proven.
- Coder PLAN-to-IMPLEMENT permission/owner cleanup = still required
  from each canonical owner, without bypassing original guards.
- Customer revenue or commercial uplift = NOT proven.
