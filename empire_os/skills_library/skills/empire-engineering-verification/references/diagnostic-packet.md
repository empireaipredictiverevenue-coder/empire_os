# Bounded diagnostic and execution packet

Use only sections relevant to the incident. Keep identifiers exact and secrets redacted.

## Packet

1. **Outcome:** desired behavior and current impact.
2. **Authority:** environment/target; authorized actions; explicit prohibitions; approval evidence and conditions. Separate code preparation, database writes, migrations, restarts, deployment, outbound, and funds.
3. **Evidence:** timestamp, source, revision/runtime identity, original command and exit status, minimal capture. Label VERIFIED, REPORTED, HYPOTHESIS, UNKNOWN.
4. **Contract:** producer expectation; consumer expectation; actual runtime/schema/configuration; exact mismatch and evidence.
5. **Diagnosis:** causal explanation supported by evidence, or unresolved alternatives plus one read-only discriminator.
6. **Bounded change:** exact diff/objects; why sufficient; no unrelated effects; preconditions and abort conditions.
7. **Execution:** ordered steps; distinguish READ, PREPARE, TEST, and GATED APPLY. Execute no gated step without scoped authority. Check exit codes and postconditions; stop on failure rather than continuing later mutations.
8. **Verification:** original failure reproduction, targeted positive and negative tests, runtime proof after activation, tenant/suppression/idempotency checks when affected.
9. **Recovery:** exact reversible step, prerequisites, and whether authorized; never assume rollback approval.
10. **Result/handoff:** changed files and revision, checks/results, runtime evidence, unresolved items, founder gate, next bounded step. Preserve attempt ledger to prevent repeated work.

## Capture design

Combine independent bounded reads in one capture request. Use `rg` for scoped source searches. Set safe timeouts and output limits. Check prerequisite paths and command availability. Avoid dumping environment files, broad database rows, full mailbox contents, or secrets. Do not use a shell block that mutates merely to diagnose. Include machine, directory, version, and exit status when relevant; make it possible to distinguish command failure from an empty result.

## Examples

- **Missing database column; no migrations allowed:** inspect actual catalog, deployed caller and migration state; diagnose the version/contract mismatch. Prepare an allowed isolated code repair if sufficient. Otherwise deliver the exact migration proposal and verification for founder approval; do not apply it or widen grants.
- **Tests pass; no restarts allowed:** verify the deployed revision read-only. Report tested code separately from runtime. Prepare the exact activation and post-activation check; hold restart behind the existing gate.
- **Malformed search response appears as zero traffic:** capture the actual response shape, inspect parser and downstream forecast contract, add a narrow regression case. Preserve an explicit unavailable/invalid state; never claim zero traffic or forecast readiness from malformed evidence.
- **Repair command fails twice:** do not run it a third time. Inspect the first failure and changed state, update the attempt ledger, and use a discriminator before proposing a materially different repair.
