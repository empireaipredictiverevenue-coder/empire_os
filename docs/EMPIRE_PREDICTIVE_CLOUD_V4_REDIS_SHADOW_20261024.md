# Original EmpireOS Predictive Cloud V4 — Redis research adapter

Research milestone, 24 October 2026. Original EmpireOS / Predictive Cloud / PRIME; no production change or cloud deployment.

`empire_os/predictive_cloud_v4_redis_shadow.py` adds a bounded Redis-command **offline client contract** to the existing Predictive Cloud; it does NOT install Redis or connect to a service. Original `predictive_cloud_status.py` includes a `redis_v4_shadow` field with `REDIS_CLOUD_NOT_CONNECTED`, no invented throughput or latency, and canonical `EmpireDB_PostgreSQL` money authority.

- Strict synthetic-only, tenant-digested Hash key namespace `v4:feature_vector:<tenant_digest>:<sector>:<entity_digest>`; exact field contract and freshness/TTL checks; 1–32 pipelined `HGETALL` reads, atomic test-double `HSET` and `EXPIRE`, no inappropriate `MGET` for Hashes.
- pCVR is bounded decimal; profit calculation is *simulated net-margin scenario* rather than recognised profit. No customer/contact data, actual payment authority, zero-loss Redis ledger or key leases.
- Tenant-scoped Redis Streams `XADD` only for OBSERVE-only risk/capacity/yield observations; treasury, ads, trades, emails and settlements are rejected. Consumer groups, replay, XACK, real network and live metrics are not implemented.
- Tests use only disposable in-memory command doubles and injected fixture-authorised sessions. Redis client, server binaries and Redis systemd units were not found in inspected original host checkout. No billable Redis Cloud subscription or AWS/GCP network path verified.

V4.1 design corrections: Redis Active-Active is eventually consistent, so cannot be canonical for settlements, consent, dedup or locking. AOF each second is not zero data loss; no 1.5ms p99 or 500k IOPS guarantee without real measurement. EKS/GKE PrivateLink/PSC does not automatically connect existing Scaleway hosts. Redis tiering names and plan features require provider-specific verification. A user-supplied `X-Tenant-ID` is never authoritative.

**Next original owner steps:** secure actual budget/cloud account, private network routing from Scaleway, TLS/ACL and key custody, source-custody/EmpireDB authoritative outbox, real Redis integration only under an owner-approved existing service; profile cold/warm p50/p95/p99, region replication lag, crash/restart/redelivery, stale-value hold, backpressure and cost before any production traffic. No Redis Cloud, outbound, paid traffic, payments or production EmpireDB writes here.

One EmpireOS. One original Predictive Cloud. One canonical EmpireDB.
