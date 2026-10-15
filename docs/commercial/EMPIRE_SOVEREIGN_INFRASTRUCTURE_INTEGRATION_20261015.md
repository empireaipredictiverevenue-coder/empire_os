# EmpireOS — integrate existing sovereign infrastructure (no additional server)

Date: 15 October 2026. Owner: existing EmpireOS Ops Control.
No machines, VMs, containers, services, timers, databases, credentials,
customer delivery, outbound or payment authority are created.

## Already deployed

- Existing bare-metal host: 8 logical CPU cores, ~62 GiB RAM,
  mirrored local RAID1 filesystem.
- PostgreSQL 18 main with PgBouncer; existing cloud tunnel.
- Founder Console, dashboard API, Autonomous Revenue OS and local inference.
- Existing `empire-ops-control.service` and timer produce
  `runtime/ops_control/latest.json`.
- Existing `empire_os/founder_ops_api.py` serves the same snapshot at
  `/v1/founder-ops/status`.
- Existing incident manager classifies observed non-repairable failures.

## New integration, not a new platform

`empire_os/sovereign_infrastructure_observer.py` reads only fixed
`systemctl show` unit states for nine known, already deployed services
and local `/proc/meminfo`, `/proc/mdstat`, filesystem free space,
and CPU-core count. It distinguishes healthy inactive one-shot units
from failed service starts. Findings join the existing Ops Control
JSON payload, health domains and incident manager without adding to
the automatic-repair plan.

The probe NEVER reads credentials, prints process command lines,
starts/stops/restarts services, writes a file, connects to the internet
or modifies payment/outbound/customer systems.

## Real failure evidence, 15 October

An earlier failed department-cycle run reported a missing accepted
`evidence_lineage` template. A Media OS refresh had external provider
HTTP 403 / 429 retry/backoff and timed out during ExecStartPre.
These are evidence/template and model-routing problems, not hardware
capacity proof. Do not fabricate a missing evidence template or
blindly restart a model-dependent process.

A later read-only query found both services in `activating` state
with `Result=success`; that is NOT a guarantee of eventual completion.
The observer always reflects the most recently queried systemd state.

## Capacity and recovery boundaries

RAID1 is disk redundancy, not off-machine recovery. The observer
**does not claim** off-node backup, independently verified restore
rehearsal, or server failover. These remain unverified until actual
recovery evidence is reviewed via the existing pgBackRest/Data Cloud
privileged helper. This does NOT authorize another server.

One snapshot showed local llama-server using ~31 GiB RSS, with
approximately 26 GiB freeable/available memory. Tune existing systemd
CPU/memory scheduling for Media OS and local inference only after
measuring contention; do not add servers preemptively.

## Next work within existing ownership

1. Trace the original accepted department-control template and
   restore missing evidence ONLY when exact original canonical
   provenance is established.
2. Repair Media OS's provider fallback within the existing runtime
   so an unavailable free model cannot consume the service timeout;
   respect local-first and zero-spend constraints.
3. Inspect pgBackRest backup freshness/recovery evidence via the
   existing protected helper, without leaking credentials.
4. Keep V16's independent 24-hour source-observation gate unchanged.

**Authority: OBSERVE-only. No new server purchase or build.**
