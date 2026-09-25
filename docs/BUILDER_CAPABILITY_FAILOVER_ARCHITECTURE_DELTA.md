# Architecture Delta — Builder Capability Promotion and Failover

Date: 2026-09-25
Status: CANONICAL / REQUIRED

## Problem

A worker binary being installed and healthy does not prove that the model behind
that worker can perform the mutation protocol required by the worker.

Observed example:
- Pi runtime and sandbox are healthy.
- qwen2.5-coder:1.5b responds to prompts.
- It emits textual JSON that resembles tool calls.
- It does not emit native structured tool calls.
- Therefore it is not mutation-capable for Pi.

## Rule

**Installed != mutation-capable.**

A mutating build worker may receive implementation jobs only after a live,
worker-specific capability probe has passed.

## Capability ledger

Runtime evidence is stored under:

`runtime/execution_plane/builder_capabilities.json`

The ledger is operational evidence only. It grants no commercial, deployment,
outbound, payment, revenue, or authority-expansion rights.

Tracked capabilities:
- `pi.code_mutation`
- `empire_coder.structured_patch_mutation`
- `hermes.code_mutation`

Every record contains:
- ready boolean;
- observed timestamp;
- evidence/reason;
- model where observed;
- execution authority = none.

## Promotion requirements

### Pi
Requires:
1. sandbox smoke;
2. native structured tool-call probe;
3. real bounded mutation smoke in disposable clone;
4. changed-path enforcement;
5. focused verification.

Textual pseudo-tool calls do not qualify.

### Empire Coder
Requires:
1. disposable-clone structured patch probe;
2. strict JSON patch synthesis;
3. StructuredPatchValidator pass;
4. exact bounded mutation;
5. no production working-tree mutation during probe.

### Hermes
Requires:
1. runtime/model eligibility;
2. genuine >=64k context where Hermes requires it;
3. normal worktree/path/test gates.

Capability metadata must reflect the real model/runtime and must never be faked.

## Failover

For mutating code work:

Hermes eligible and proven
→ Pi eligible and mutation-proven
→ Empire Coder structured-patch proven
→ WAITING_FOR_CAPABLE_BUILDER

A failed or unknown capability does not get silently skipped as success.

## Truth boundary

Capability probe success proves only the narrow worker protocol tested. It does
not prove business correctness, production readiness, commercial authority, or
general model quality.

Candidate verification, Swarm QA, Promptfoo where applicable, live verification,
and canonical data evidence remain separate promotion gates.


## Isolated Empire Coder fallback

Observed Pi runtime health does not override a failed mutation-capability probe.
When Pi code mutation is not proven and Empire Coder structured-patch mutation is
proven, mutating code work may fail over to Empire Coder only through the
disposable-clone proposal runner.

Required properties:
- central domain/path mutation lease;
- disposable full clone, never direct model edits in `/srv/empire_os`;
- one machine-checkable structured patch candidate;
- allowed-path enforcement before and after application;
- focused tests in the clone;
- proposal branch only;
- independent candidate verification before promotion;
- no production deploy, outbound, payment, revenue or authority expansion.

The local model receives one bounded JSON-normalization retry if its synthesized
patch is not strict JSON. A second failure remains a capability failure.
