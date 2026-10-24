# Original EmpireOS Predictive Cloud V4 — real, isolated Redis 8 acceptance

**Research date:** 24 October 2026
**Scope:** Existing EmpireOS / Predictive Cloud V4 feature store + advisory Redis Streams.
**Release:** OFFLINE RESEARCH ONLY. No Redis Cloud, production service, EmpireDB write, trading, paid traffic, treasury execution, outbound or revenue claim.

## Completed

Previous V4 work used an in-memory Redis-command double and tested tenant-scoped Hash features, a bounded Lua revision fence, advisory Streams and read-only readiness on the original Predictive Cloud status API. This milestone executes those **same V4 contracts on an actual Redis 8 server process**, without installing a Redis service on EmpireOS.

The real-run source is `scripts/rehearse_predictive_cloud_v4_real_redis_20261024.py` (already committed to the existing research branch before this acceptance wrapper). This milestone adds:

- `scripts/rehearse_predictive_cloud_v4_real_redis8_20261024.sh`: obtains `redis-server`, `redis-tools`, `liblzf1` as Ubuntu `.deb` packages using **unprivileged `apt download`**, extracts to `/tmp`, starts an unprivileged Redis process only over a **Unix domain socket** with filesystem mode 0700, TCP port **0**, **no RDB snapshots or AOF**, `maxmemory 32mb`, `noeviction`, and **no systemd/Docker/sudo/apt install**. The shell owns an EXIT trap that shuts Redis down without persistence and removes both the temporary package directory and the temporary server directory.
- `tests/test_predictive_cloud_v4_real_redis8_20261024.py`: asserts the no-install/no-TCP/no-persistence wrapper, refuses unexpected socket paths before any Redis access, invokes the real Redis 8 fixture in a subprocess and verifies all acceptance markers. It requires Ubuntu apt repository/network access for the disposable packages; no paid managed Redis account is needed.

## Actual real Redis evidence

On the authorised remote EmpireOS host, Ubuntu 26.04 official package metadata provided Redis **8.0.5**. The real server started as an unprivileged process. The acceptance output was:

```json
{
  "status": "REAL_LOCAL_REDIS8_V4_HOTPATH_PASS",
  "redis_version": "8.0.5",
  "unix_socket_only": true,
  "tcp_port": 0,
  "persistence_enabled": false,
  "lua_atomic_revision_fence": true,
  "concurrent_independent_writer_connections": 8,
  "final_revision": 13,
  "pipelined_two_hash_read": true,
  "ttl_real_expiry": true,
  "stream_duplicate_observations_stored": 2,
  "redis_cloud_connected": false,
  "production_empiredb_touched": false,
  "money_moved": false,
  "paid_traffic": false,
  "real_latency_slo_verified": false,
  "real_multi_region_semantics_verified": false
}
```

The real Redis Lua interpreter correctly rejected stale and equal revisions, kept revision 13 after eight concurrent independent socket writers, preserved feature Hash metadata, returned two ordered batched Hash reads, expired a 1-second feature TTL, and appended two advisory messages with the same original event digest but different Stream IDs. This **demonstrates why Stream event deduplication is still needed** before any regulated or revenue-sensitive downstream processing.

Post-run checks observed no left-behind `empire-v4-redis-*` package/run directories, no Redis server processes and no Redis TCP listeners. The fixture never used the production Redis endpoint or canonical EmpireDB.

## Regression and repeat command

```bash
cd /home/ubuntu/empire_worktrees/prime_universal_evidence_fusion_20261024
bash scripts/rehearse_predictive_cloud_v4_real_redis8_20261024.sh
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B -m pytest -q \
  tests/test_predictive_cloud_v4_real_redis8_20261024.py \
  tests/test_predictive_cloud_v4_redis_shadow.py \
  tests/test_predictive_cloud_status.py
```

**277 scoped affected-system tests passed** when the real Redis tests were run together with original Predictive Cloud V3, status API, PRIME, revenue forecast, source/Quant and Economic Signal Fabric tests. One inherited Starlette/anyio deprecation warning. This is an affected-system suite, not every repository test.

## Still HOLD before real Redis Cloud

1. **Infrastructure/Security:** select and approve a real Redis Cloud account and plan only after pricing, region availability, contract and a working Scaleway-to-cloud **private network/TLS/ACL** design are verified. Neither AWS PrivateLink nor GCP PSC is automatically available from the existing bare-metal deployment.
2. **Predictive Cloud/Data owners:** approve canonical EmpireDB source event IDs, revision monotonicity, identity/tenant scoping, privacy retention and the retry/deduplication contract. No cache key becomes transaction or payment authority.
3. **Performance:** test actual remote Redis Cloud p50/p95/p99, connection reuse, failover, cross-region replication, memory ceilings and realistic peak IOPS. The real local Unix-socket test **does not measure** the 1.5ms end-to-end target or proposed 500,000 IOPS.
4. **Chief of Staff/Swarm:** Streams remain OBSERVE-only until each consumer is protected by original EmpireDB durable outbox, idempotency, explicit risk permission and independent founder gates.
5. **Finance:** EmpireDB stays canonical for money and settlement. Redis Lua single-primary atomicity is **not** a global Active-Active lock or exactly-once treasury ledger. No paid traffic, real bids, outbound, USDT movement or live notification occurred.

**One EmpireOS. One original Predictive Cloud. One canonical EmpireDB. ASTRA and PRIME preserved.**
