# Buyer Identity Search Cycle Breaker V1

## Goal
Stop parallel buyer enrichment lanes from repeating the same degraded identity-search path within one governed cycle.

## Contract
A shared in-process event starts clear for each parallel cycle.
If one identity-recovery subprocess returns serp_degraded=true, the event opens.
Remaining lanes skip new broad identity-recovery subprocesses for that cycle.
The next systemd process starts clean and may test Search Fabric again.

## Preserved behavior
First-party targeted probes still run.
Canonical identity hints still run.
Existing target people remain prioritised.
Queue durability and retry scheduling remain unchanged.
No evidence threshold is lowered.

## Safety
No new provider.
No database migration.
No outbound or call authority.
No payment or revenue authority.
No synthetic identity.
