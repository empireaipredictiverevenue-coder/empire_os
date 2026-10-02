# Identity Recovery SERP Circuit Breaker V1

## Goal
Stop one buyer identity recovery from repeatedly calling Search Fabric after Search Fabric has already reported that all configured engines failed.

## Contract
The breaker is local to one `recover_identity()` call.
It opens only when the SERP snapshot reports `engine=none`, an explicit snapshot error, or the adapter raises `SerpSnapshotError`.

A legitimate empty result from an available engine does not globally disable Search Fabric.
Direct first-party probing remains first.
Official registry and Companies House paths remain available.
No evidence threshold is lowered.

## Safety
No new provider.
No external service.
No authority expansion.
No database migration.
No outbound.
No synthetic identity.
