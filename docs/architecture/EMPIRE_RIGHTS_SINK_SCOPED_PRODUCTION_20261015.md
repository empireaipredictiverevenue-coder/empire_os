# Empire 2026-10-15 — Bounded V18 partner-sink release

**Production scope:** existing `empire_os/economic_memory.py`,
`empire_os/typed_decision_dataset.py`, newly added standalone
`empire_os/company_partner_sink_enforcement_v18.py`, and its
adversarial tests.

This is a **scoped** release drawn from V18 engineering, NOT the full
V19–V23 integrated code package. The current production tree still
contains 66 independently owned, uncommitted tracked files. Do not
reset, stash, stage or overwrite those files. Do not cherry-pick
V23, invoke migration 051/052, restart services, send outreach
or initiate payments as part of this rights-release increment.

## Risk and scope
- Retain production canonical buyer, BSC order/payment, delivery and
  outbound programs unchanged.
- The existing frozen evaluation-dataset consumer and Economic Memory
  snapshot constructor now explicitly reject **known partner-origin
  evidence** from Astoria, BuyTheCalls and RVNU before materialisation.
- The guard is self-contained and freezes the same three source domains
  as the V17 rights prototype. It imports no unshipped research modules.
- Any other unverified partner domain or stripped provenance is NOT
  authenticated or licensed by this guard; additional upstream purpose-
  specific rights checks remain necessary.
- No application instance needs to be restarted simply to copy these
  functions, but existing long-running Python processes may retain
  the old loaded module until their separately governed rollout.
  A code presence check alone is not proof of all live processes.
- The founder gates for live outbound, new training, migrations,
  destructive infrastructure and funds remain unchanged.

## Acceptance
1. Source branch begins at original production `a4d9375a`.
2. The two existing consumer files in production are clean and
   match the original Git head byte-for-byte before application.
3. The new guard/test files are absent from production and written
   only into their named locations; no unrelated paths modified.
4. All tests from `test_company_partner_sink_enforcement_v18`,
   `test_economic_memory`, `test_typed_decision_dataset`,
   `test_typed_decision_baselines`, and
   `test_verified_outcome_learning_continuity` must pass.
5. Test a current-source canary showing a restricted URL is denied
   by both consumers. Test unaffected first-party/canonical records.
6. Record exact prod Git commit and 66 tracked dirty files preserved;
   production branch head advancing makes historic V21 source snapshot
   guard go stale by design. Refresh release evidence before any
   full V23 merge.
7. Reconcile the other agents' work and deploy future tenant-authenticated
   revocable rights and lead-delivery guards separately.

No new independent buyer, contractual data rights or realised revenue
are implied by this release.
