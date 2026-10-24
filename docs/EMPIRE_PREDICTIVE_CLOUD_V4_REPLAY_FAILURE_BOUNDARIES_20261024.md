# Empire AI Predictive Cloud V4 — Replay and transport failure boundary

**24 October 2026** · Existing EmpireOS / PRIME / ASTRA / EmpireDB PostgreSQL · Research only

## Reason for this continuation

The actual isolated Redis 8.0.5 interpreter and 277-test affected-system gauntlet already passed in commits `264573a8d` and `df13c164a`. This follow-on does not retest or recreate the managed cloud environment. It probes safety guarantees that a single-key Redis Lua revision fence **cannot** provide.

## Verified in disposable, fictional fixtures

1. **TTL loses the watermark:** a cached revision 13 expires with the Hash. A delayed revision 12 can then pass the same single-key fence because no previous Hash remains. Its research projection stays synthetic, not entitled to real routing and not verified revenue. A separate durable EmpireDB owner-assigned monotonic revision and withdrawal/invalidation authority is required before production projection.
2. **Partial pipelined replies:** a shortened `HGETALL` result list refuses the entire batch instead of silently mapping the wrong entity to a tenant.
3. **Disconnected socket:** injected read and write transport errors propagate as failures; no successful receipt, feature value or financial action is fabricated. Actual outage and reconnect policies still need authorized network-level verification.
4. **Streams redelivery:** earlier real Redis tests proved duplicate advisory event digests receive different Stream IDs; a Redis Stream is not a durable exactly-once financial, opt-in or execution ledger.

## Next real build gates (not silently granted)

- Design the **canonical EmpireDB-authorised projection/outbox** and demonstrate an owner-issued monotonic revision survives Redis expiry, node restart, delayed retries and source withdrawal. No current code establishes that authority.
- Bind tenant membership, source rights, revocation and event idempotency to existing EmpireDB and original Smart CRM controls, without introducing a separate DB or CRM.
- Keep Redis access behind approved infrastructure, TLS ACLs, retention, budget and measured Scaleway connection. Verify realistic latency/failover before activating any cloud client.
- All Streams are `OBSERVE` and cannot authorize paid advertising, buyer emails, payments, fund movements, treasury execution or dispatch.

**Release disposition: HOLD / RESEARCH ONLY.** Existing production code, systemd, canonical EmpireDB, payment controls and outbound remain untouched.

## Focused verification

```bash
cd /home/ubuntu/empire_worktrees/prime_universal_evidence_fusion_20261024
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B -m pytest -q tests/test_predictive_cloud_v4_redis_shadow.py
```
