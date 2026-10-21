# EmpireOS Predictive — original timed refresh integration (21 October 2026)

Scope is **only** the existing `empire-predictive-intelligence.service` refresh and its original five-minute timer; database roles, original tenant reader, outbound, payment activation, customer learning and model weights are out of scope.

## Observed production gap

The active systemd service still runs `/srv/empire_os/scripts/build_predictive_intelligence.py --repo-root /srv/empire_os`, importing `empire_os.predictive_intelligence` from the mutable shared checkout, not from the isolated tested OBSERVE release. A zero-outcome cache written by the old code has no `source_scope_admission_status`. The amended source rejects those old cache formats even when their reported count is zero, then re-reads and quarantines the legacy globally scoped outcome RPC. No legacy source row can become a tenant-specific forecast.

The original owner credential, four native RLS policies, and successful zero-candidate source read were independently reported on 21 Oct 2026. The restricted tenant cohort reader remains a separate manual OBSERVE command. This refresh does **not** train on those candidates.

## Guarded production-owner installation (not automatically activated)

Operator-only installer `scripts/install_guarded_predictive_refresh_20261021.sh` is fail-closed and requires `--apply-owner-approved-observe` plus the **full exact reviewed release commit**. First perform a non-privileged `--check`. The remote agent cannot execute the privileged activation because its command policy blocks `sudo`.

The installer checks exact existing systemd unit/drop-in hashes and old shared-writer source hash; rejects unexpected owner changes or existing override. It stages a root-owned non-writable copy of the tested release under `/opt/empire/predictive_guard_<commit>`, and appends only a `60-predictive-guard.conf` override. The unit retains the existing DB environment and runtime directory, but its Python module loading is pinned to the root-owned code. It briefly stops and restores the original timer during switchover, runs the single service once, and verifies the persisted snapshot contains source-admission fields with **no forecasts** and false authority flags. On failure it removes the override, reloads systemd, restores the preflight snapshot and restarts the timer.

The installer makes no outbound, payment, model-training, CRM, SQL migration, credential or customer access changes. It does not copy code into dirty `/srv/empire_os`.

Success only establishes a guarded **unscoped global source quarantine** in the scheduled writer. It does not authenticate customer finance evidence, issue a conversion prediction registry receipt or authorize a customer forecast. The service remains on OBSERVE.

Owner handoff requires exact final commit, passing release manifest and approval for the dedicated service switch; no implicit permission to alter any other production service.
