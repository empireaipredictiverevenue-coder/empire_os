# Empire AI Predictive Cloud V4.1 — real Redis 8 local acceptance

**24 October 2026** · Original EmpireOS / Predictive Cloud V3→V4 · Same canonical EmpireDB PostgreSQL · **ISOLATED RESEARCH ONLY**

## The exact milestone

The earlier V4 Redis Shadow adapter, feature-value validation, tenant key schema, Hash read pipeline, single-key revision Lua fence and observational Streams were checked using a Python command double. This milestone **ran that unchanged V4 Lua program and feature/Stream adapter against the actual Redis 8.0.5 interpreter and protocol**, using an Ubuntu-packaged executable extracted only to `/tmp`. This is not a Redis Cloud deployment or benchmark.

### How it was isolated

- No system package installation, `sudo apt install`, Docker service, systemd unit or Redis Cloud connection.
- Ubuntu repositories supplied unmodified `redis-server`, `redis-tools` and `liblzf1` .deb packages. Extraction with `dpkg-deb -x` executed **no maintainer scripts** and placed the binaries and dependency in a user-owned temporary directory.
- Real server started **only for the test process**, with `--port 0` (no TCP listener), private 0700 Unix socket and runtime directory, `--save ""`, `--appendonly no`, `--maxmemory 32mb` and `--maxmemory-policy noeviction`. A shell exit trap terminates this exact spawned server and removes the socket/data directory.
- A tiny stdlib Python RESP2 Unix-socket test client in `scripts/rehearse_predictive_cloud_v4_real_redis_20261024.py` supplies the original adapter's injected Redis commands. No `redis-py` or global process configuration was installed.
- The runner `scripts/rehearse_predictive_cloud_v4_real_redis_20261024.sh` **refuses ambient server binaries** and only accepts a binary whose `/tmp/empire-v4-redis-package.*/root/usr/bin/redis-server` symlink resolves to that extracted package's Redis multicall binary, plus its matching local liblzf. The `redis-server` symlink is invoked without resolving argv0 so Redis executes **server mode**, not the RDB checker.
- The experiment uses **fictional tenant, source, entity and event digests**, no actual buyer data, payments, campaigns, device notifications, source approvals, outbound, provider keys or production DB sessions.

### Observed actual Redis behaviour

Ran the entire existing V4 feature/Stream path against the isolated Redis server:

1. `PING` returned `PONG`; Redis `CONFIG GET port` was 0 and `CONFIG GET save/appendonly` showed persistence disabled.
2. The **actual Lua script** successfully wrote a Hash and TTL as one Redis-key operation. An older revision **4** and equal revision **5** could not overwrite revision **5** or extend TTL.
3. Eight independent Unix-socket writers attempted revisions **6–13** concurrently. The final stored revision was **13**, independent of arrival ordering. The V4 read path retained the “NOT ELIGIBLE FOR REAL ROUTING” safety flag.
4. Two different Hashes were read in a **single pipelined batch**, preserving reference ordering and expected *simulated* net calculation.
5. An attempt to read the same entity under a different tenant digest returned a cache miss. **This is application key separation, not Redis Cloud ACL or cryptographic tenant authentication.**
6. Two identical advisory Stream events were appended and received different Redis IDs; the Stream length was **2**, proving `XADD` is not exactly-once processing or a canonical financial record.
7. A short-TTL Hash expired on the actual Redis timer. The adapter returned `CACHE_MISS_OR_EXPIRED` requiring an independently approved authoritative fallback.
8. The isolated Redis service terminated and its runtime directory was removed. Production Redis is not configured or touched; canonical EmpireDB remains authoritative.

Output status: `REAL_LOCAL_REDIS8_V4_HOTPATH_PASS`, Redis **8.0.5**. No measured throughput or p95 latency was produced. Concurrent revision fencing **does not extend across Active-Active Redis Cloud regions**, a TTL can expire and lose its cache watermark, and a source digest is not verified source authorization. Those are separate release gates.

## Repeat the local experiment without installing a service

```bash
cd /home/ubuntu/empire_worktrees/prime_universal_evidence_fusion_20261024

# Unprivileged Ubuntu package extraction in a dedicated temporary directory.
pkgdir="$(mktemp -d /tmp/empire-v4-redis-package.XXXXXX)"
(
  cd "$pkgdir"
  apt download redis-server redis-tools liblzf1
  mkdir -p root
  for deb in ./*.deb; do dpkg-deb -x "$deb" root; done
)

# Starts a disposable Redis server bound to a 0700 Unix socket, with port 0.
EMPIRE_V4_REDIS_SERVER_BIN="$pkgdir/root/usr/bin/redis-server" \
EMPIRE_V4_REDIS_LIBRARY_DIR="$pkgdir/root/usr/lib/x86_64-linux-gnu" \
bash scripts/rehearse_predictive_cloud_v4_real_redis_20261024.sh

# Optional pytest pass through the *same* disposable Redis package:
EMPIRE_V4_REDIS_SERVER_BIN="$pkgdir/root/usr/bin/redis-server" \
EMPIRE_V4_REDIS_LIBRARY_DIR="$pkgdir/root/usr/lib/x86_64-linux-gnu" \
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B -m pytest -q \
 tests/test_predictive_cloud_v4_real_redis_20261024.py

# Remove only the local, test-only package extract after all runs.
rm -rf -- "$pkgdir"
```

The suite never contacts Redis Cloud. The two environment variables supply local temporary **executable/library paths only**, not network credentials or a production endpoint. The project does not gain runtime Redis client dependencies or scheduled jobs.

## What remains for real Redis Cloud implementation

1. Owner-approve the subscription, budget, region/residency, tenancy and Redis Cloud service plan, plus actual connectivity from the existing Scaleway node. AWS PrivateLink/GCP PSC **are not present just because the enterprise architecture mentions them**.
2. Approve restricted Redis TLS/ACL credentials and key rotation through the original Security/Cloud Ops owners. Verify real Redis Cloud command/script support; the tested Lua run was on a **single local Redis 8 server**, not the provider's Active-Active deployment.
3. Define an EmpireDB-authorized, tenant-scoped, source-provenance-first projection/outbox. Real revision counters, purpose/rights, timestamp custody and withdrawal/invalidation must come from canonical signed evidence.
4. Test disconnection, partial pipeline replies, aggressive TTL, Redis replica/failover and cross-region Active-Active divergence. Implement monitoring and bounded client retries without turning observational data into unsupported execution.
5. Benchmark **actual** end-to-end p50/p95/p99 latency, key size, shards, region RTT and cost before asserting sub-1.5ms or 500,000 IOPS.
6. Preserve original founder approval gates: no financial execution or USDT BSC authority, paid traffic, outreach, email or live agent action from Redis contents.

**One EmpireOS · One Predictive Cloud · One EmpireDB PostgreSQL · PRIME/ASTRA preserved.**
