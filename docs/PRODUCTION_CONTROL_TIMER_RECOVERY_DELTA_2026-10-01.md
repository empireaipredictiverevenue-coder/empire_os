# Production Control Timer Recovery — Architecture Delta

Date: 2026-10-01
Status: IMPLEMENTATION DELTA / LIVE ACTIVATION HELD
Owner: EmpireOS Control Fabric / Runtime Reliability

## Purpose

Recover production control-plane health after the Supabase-to-EmpireDB containment
period without blindly restarting enabled timers or restoring stale authority.

Observed production truth:

- EmpireDB is canonical.
- Supabase containment is no longer authoritative while EmpireDB is canonical.
- systemd has zero failed units.
- runtime self-heal is DEGRADED only because 11 enabled timers are inactive.
- those timers were previously active and later deactivated in batches during
  the containment/cutover period.
- self-heal correctly classifies those units as OBSERVE_ONLY rather than
  automatically reactivating them.
- 10 of the relevant live service/timer definitions match current repository
  definitions.
- live `empire-ops-control.service` is stale:
  live = `EMPIRE_OPS_HEAL_MODE=GUARDED_EXECUTE`;
  repo = `EMPIRE_OPS_HEAL_MODE=OBSERVE`.
- `empire-astra-dispatcher.timer` is installed/enabled but
  `empire-astra-dispatcher.service` is not installed.
- the repository Astra service currently requests
  `EMPIRE_ASTRA_DISPATCH_MODE=GUARDED_EXECUTE`, which conflicts with the
  current default OBSERVE doctrine.

## Architecture

```text
systemd timer inventory
  -> runtime_self_heal
  -> policy classification
       AUTO_REPAIR
       OBSERVE_ONLY
       FOUNDER_GATE
  -> deployment contract verification
  -> OBSERVE-safe unit definitions
  -> founder-gated live activation
  -> fresh snapshots / timer schedules
  -> self-heal health
```

## Canonical placement

- Runtime reliability owner: `empire_os/runtime_self_heal.py`
- Astra dispatcher owner: `empire_os/astra_dispatcher.py`
- Astra deployment contract:
  `deploy/systemd/empire-astra-dispatcher.service`
- Ops Control deployment contract:
  `deploy/systemd/empire-ops-control.service`

This delta does not change canonical business data or data authority.

## Authority

Current authority remains OBSERVE.

This delta MUST NOT:
- start/restart/enable/disable production services or timers without the live
  activation gate;
- send outreach;
- accept terms;
- move funds;
- recognize revenue;
- apply migrations;
- weaken migration 018;
- convert OBSERVE_ONLY self-heal inventory into automatic repair authority.

## Implementation

Repository correction:

1. change the Astra systemd service default from
   `EMPIRE_ASTRA_DISPATCH_MODE=GUARDED_EXECUTE` to
   `EMPIRE_ASTRA_DISPATCH_MODE=OBSERVE`;
2. add a regression test that locks the systemd unit to OBSERVE by default;
3. leave the dispatcher’s explicit `mode="GUARDED_EXECUTE"` test paths intact
   because guarded execution remains a testable capability, not the production
   default.

Live deployment remains separate:

1. install the corrected Astra service unit;
2. replace the stale Ops Control service unit with the repository OBSERVE unit;
3. daemon-reload;
4. start only reviewed OBSERVE-safe timers;
5. verify timer schedules, service results and snapshots;
6. rerun self-heal;
7. record DONE evidence.

Live deployment is HELD until explicit founder approval for service/timer
activation in the current task.

## Positive example

An enabled internal snapshot timer whose service loads EmpireDB configuration,
has a repository-matching unit and performs no external commercial action may be
reactivated after the live gate.

## Negative example

Do not start `empire-astra-dispatcher.timer` while its service is missing or
while its installed/repository service would default to GUARDED_EXECUTE.

Do not treat `enabled` as evidence that a timer is safe to start.

## Verification

Repository gate:
- Astra dispatcher tests;
- deployment-contract regression;
- compile relevant Python module;
- diff check.

Live gate:
- exact unit-file hashes;
- timer active/waiting states;
- no failed units;
- current snapshot freshness;
- self-heal status;
- migration 018 SHA unchanged;
- Founder read surface healthy.

## DONE

This recovery slice is not DONE until both repository and separately approved
live activation gates pass.
