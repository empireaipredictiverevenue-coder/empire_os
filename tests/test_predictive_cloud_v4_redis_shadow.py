"""Predictive Cloud V4.1: offline Redis Hash/Streams client contract.

Uses an in-memory, bounded Redis-command double, not a Redis instance.
No cloud, network, service setup, prod DB or treasury execution.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from hashlib import sha256

import pytest

from empire_os.predictive_cloud_v4_redis_shadow import (
    SCHEMA, STREAM, RedisV4Hold, FEATURE_REVISION_FENCE_LUA,
    feature_key,inspect_fixture_feature,record_fixture_feature,
    read_fixture_feature,read_fixture_features_batch,
    emit_fixture_swarm_observation,readiness,
)

NOW=datetime(2026,10,24,20,0,tzinfo=timezone.utc)
def h(x):return sha256(x.encode()).hexdigest()

def example():
    return {
      "schema_version":SCHEMA,
      "tenant_scope_digest":h("fictional-tenant-a"),
      "entity_digest":h("fictional-entity"),
      "sector":"roofing",
      "source_evidence_digest":h("fictional-source-proof-not-authentication"),
      "revision":3,
      "observed_at":(NOW-timedelta(seconds=3)).isoformat(),
      "pcvr":"0.250000",
      "gross_cents":10000,
      "acquisition_cost_cents":100,
      "fulfilment_cost_cents":900,
      "processing_fee_cents":100,
      "capacity":9,
      "synthetic_only":True,
    }


class FakeRedisPipeline:
    def __init__(self,db,transaction):
        assert type(transaction) is bool
        self.db=db
        self.transaction=transaction
        self.ops=[]
    def hset(self,key,*,mapping):
        self.ops.append(("hset",key,dict(mapping)))
        return self
    def expire(self,key,ttl):
        self.ops.append(("expire",key,ttl))
        return self
    def hgetall(self,key):
        self.ops.append(("hgetall",key))
        return self
    def execute(self):
        if not self.transaction:
            self.db._commands.append(("PIPELINED-HGETALL",len(self.ops)))
            return [self.db._data.get(key,{}) for kind,key in self.ops if kind=="hgetall"]
        # Mimic transactional batch: same fake-store state as an atomic commit.
        assert len(self.ops)==2
        _,key,record=self.ops[0]
        kind,key2,ttl=self.ops[1]
        assert kind=="expire" and key==key2
        self.db._data[key]={k.encode():v.encode() for k,v in record.items()}
        self.db._ttl[key]=ttl
        self.db._commands.append(("MULTI-HSET-EXPIRE",key))
        return [len(record),True]


class FakeRedis:
    is_v4_disposable_fixture=True
    def __init__(self):
        self._data={}
        self._ttl={}
        self._streams={}
        self._commands=[]
    def pipeline(self,*,transaction=False):
        return FakeRedisPipeline(self,transaction)
    def eval(self,script,key_count,key,new_revision,ttl,*pairs):
        # Contract double, not a Redis Lua interpreter or Cloud benchmark.
        assert script==FEATURE_REVISION_FENCE_LUA
        assert key_count==1
        assert len(pairs)%2==0 and len(pairs)>0
        previous=self._data.get(key,{}).get(b"revision")
        if previous is not None:
            try:
                if int(previous)>=int(new_revision):
                    self._commands.append(("EVAL-REVISION-REFUSED",key))
                    return 0
            except ValueError:
                return -1
        self._data[key]={
            str(pairs[i]).encode():str(pairs[i+1]).encode()
            for i in range(0,len(pairs),2)
        }
        self._ttl[key]=int(ttl)
        self._commands.append(("EVAL-FENCED-HSET-EXPIRE",key))
        return 1
    def hgetall(self,key):
        self._commands.append(("HGETALL",key))
        return self._data.get(key,{})
    def xadd(self,key,message,*,id="*"):
        assert id=="*"
        index=len(self._streams.setdefault(key,[]))+1
        mid=f"1700000000000-{index}"
        self._streams[key].append((mid,message.copy()))
        self._commands.append(("XADD",key))
        return mid


def test_existing_predictive_cloud_v3_unaffected_and_not_rebuilt():
    from empire_os.predictive_cloud_v3 import (
        forecast_observed_metric,ObservedMetricPoint,
    )
    assert callable(forecast_observed_metric)
    assert ObservedMetricPoint.__module__=="empire_os.predictive_cloud_v3"


def test_fixture_projection_expected_net_is_simulated_not_revenue():
    packet=inspect_fixture_feature(example(),now=NOW)
    assert packet["simulation_expected_net_cents"]==1400
    assert packet["realised_net_profit_cents"] is None
    assert packet["eligible_for_real_routing"] is False
    assert packet["empiredb_authority"]=="not_verified"
    assert packet["execution_authority"]=="none"
    assert "fictional-tenant-a" not in packet["feature_key"]


def test_feature_key_tenant_separated_not_raw_entity():
    record=example()
    a=feature_key(tenant_scope_digest=record["tenant_scope_digest"],
                  sector="roofing",entity_digest=record["entity_digest"])
    b=feature_key(tenant_scope_digest=h("fictional-tenant-b"),
                  sector="roofing",entity_digest=record["entity_digest"])
    assert a!=b
    assert a.startswith("v4:feature_vector:")
    assert "{" not in a
    assert len(a)<200


def test_fake_redis_transactional_hset_expire_and_hash_read():
    redis=FakeRedis()
    record=example()
    receipt=record_fixture_feature(redis,record,now=NOW,fixture_authorised=True)
    assert receipt["status"]=="DISPOSABLE_FEATURE_HASH_WRITTEN"
    assert receipt["ttl_seconds"]==15
    assert receipt["execution_authority"]=="fixture_only"
    assert receipt["real_redis_cloud_connected"] is False
    read=read_fixture_feature(
        redis,tenant_scope_digest=record["tenant_scope_digest"],
        sector="roofing",entity_digest=record["entity_digest"],
        now=NOW,fixture_authorised=True,
    )
    assert read["status"]=="DISPOSABLE_FEATURE_HASH_READ"
    assert read["pcvr"]=="0.250000"
    assert read["simulation_expected_net_cents"]==1400
    assert len(redis._commands)==2
    assert redis._commands[0][0]=="EVAL-FENCED-HSET-EXPIRE"
    assert redis._commands[1][0]=="HGETALL"


def test_cache_miss_requires_authoritative_fallback_and_no_fake_profit():
    redis=FakeRedis()
    record=example()
    outcome=read_fixture_feature(
        redis,tenant_scope_digest=record["tenant_scope_digest"],
        sector=record["sector"],entity_digest=record["entity_digest"],
        now=NOW,fixture_authorised=True,
    )
    assert outcome=={
        "status":"CACHE_MISS_OR_EXPIRED",
        "execution_authority":"none",
        "empiredb_fallback_required":True,
    }


def test_stale_cache_never_routes():
    redis=FakeRedis()
    record=example()
    record_fixture_feature(redis,record,now=NOW,fixture_authorised=True)
    with pytest.raises(RedisV4Hold,match="future_or_stale_feature"):
        read_fixture_feature(
            redis,tenant_scope_digest=record["tenant_scope_digest"],
            sector=record["sector"],entity_digest=record["entity_digest"],
            now=NOW+timedelta(seconds=40),fixture_authorised=True,
        )


def test_tenant_rebinding_inside_hash_refused():
    redis=FakeRedis()
    record=example()
    record_fixture_feature(redis,record,now=NOW,fixture_authorised=True)
    key=feature_key(tenant_scope_digest=record["tenant_scope_digest"],
                    sector=record["sector"],entity_digest=record["entity_digest"])
    redis._data[key][b"tenant_scope_digest"]=h("other-tenant").encode()
    with pytest.raises(RedisV4Hold,match="cross_tenant"):
        read_fixture_feature(redis,tenant_scope_digest=record["tenant_scope_digest"],
            sector=record["sector"],entity_digest=record["entity_digest"],
            now=NOW,fixture_authorised=True)


@pytest.mark.parametrize("bad,reason",[
  ({"pcvr":"NaN"},"pcvr"),
  ({"pcvr":"1.1"},"pcvr"),
  ({"pcvr":0.5},"pcvr"),
  ({"pcvr":"0.0000001"},"pcvr"),
  ({"capacity":True},"capacity"),
  ({"capacity":-1},"capacity"),
  ({"gross_cents":10.5},"gross_cents"),
  ({"gross_cents":10**12},"gross_cents"),
  ({"acquisition_cost_cents":-1},"acquisition_cost_cents"),
  ({"revision":0},"positive_revision"),
  ({"revision":True},"revision"),
  ({"synthetic_only":False},"fixture_only"),
  ({"tenant_scope_digest":"user@example.com"},"digest"),
  ({"entity_digest":"real-id"},"digest"),
  ({"source_evidence_digest":"bogus"},"digest"),
  ({"sector":"trading"},"supported_sector"),
  ({"observed_at":"2026-10-24T20:00:00"},"bounded_timestamp"),
  ({"observed_at":"not-a-time"},"timestamp"),
  ({"observed_at":(NOW+timedelta(seconds=1)).isoformat()},"stale"),
  ({"observed_at":(NOW-timedelta(minutes=2)).isoformat()},"stale"),
  ({"live_payment_approved":True},"exact_feature"),
])
def test_bounded_features_fail_closed(bad,reason):
    record=example()
    record.update(bad)
    with pytest.raises(RedisV4Hold,match=reason):
        inspect_fixture_feature(record,now=NOW)


@pytest.mark.parametrize("ttl",[0,61,False,1.5,"5"])
def test_fixture_write_ttl_bounded(ttl):
    with pytest.raises(RedisV4Hold,match="ttl_out_of_bounds"):
        record_fixture_feature(FakeRedis(),example(),now=NOW,
                               ttl_seconds=ttl,fixture_authorised=True)


def test_client_without_disposable_attestation_cannot_write():
    class Client:
        pass
    with pytest.raises(RedisV4Hold,match="disposable_fixture_io_only"):
        record_fixture_feature(Client(),example(),now=NOW,fixture_authorised=True)
    with pytest.raises(RedisV4Hold,match="disposable_fixture_io_only"):
        record_fixture_feature(FakeRedis(),example(),now=NOW,fixture_authorised=False)


def test_disallowed_injected_hash_fields_rejected():
    redis=FakeRedis()
    record=example()
    record_fixture_feature(redis,record,now=NOW,fixture_authorised=True)
    key=feature_key(tenant_scope_digest=record["tenant_scope_digest"],
                    sector=record["sector"],entity_digest=record["entity_digest"])
    redis._data[key][b"wire_transfer"]=b"true"
    with pytest.raises(RedisV4Hold,match="untrusted_redis_hash"):
        read_fixture_feature(redis,tenant_scope_digest=record["tenant_scope_digest"],
            sector=record["sector"],entity_digest=record["entity_digest"],
            now=NOW,fixture_authorised=True)


def test_not_a_money_lock_or_execution_transport():
    state=readiness()
    assert state["status"]=="REDIS_CLOUD_NOT_CONNECTED"
    assert state["original_predictive_cloud_preserved"] is True
    assert state["canonical_financial_ledger"]=="EmpireDB_PostgreSQL"
    assert state["real_latency_benchmark_ms"] is None
    assert state["real_peak_iops_benchmark"] is None
    assert state["redis_used_for_critical_money_authority"] is False
    assert state["paid_traffic"] is False
    assert state["execution_authority"]=="none"


def test_observe_stream_xadd_never_treasury_execution():
    redis=FakeRedis()
    record=example()
    event=emit_fixture_swarm_observation(
      redis,tenant_scope_digest=record["tenant_scope_digest"],
      event_digest=h("fictional-consensus-1"),
      signal="RISK_CONSTRAINT_OBSERVED",
      source_evidence_digest=record["source_evidence_digest"],
      now=NOW,fixture_authorised=True,
    )
    assert event["status"]=="DISPOSABLE_ADVISORY_STREAM_APPENDED"
    assert event["stream"]==f"{STREAM}:{record['tenant_scope_digest']}"
    assert event["durable_ledger_committed"] is False
    assert event["redis_delivery_guaranteed"] is False
    assert event["treasury_execution"] is False
    assert event["execution_authority"]=="fixture_only"
    assert redis._commands[-1][0]=="XADD"
    assert len(redis._streams)==1
    assert redis._streams[event["stream"]][0][1]["mode"]=="OBSERVE"


@pytest.mark.parametrize("signal",[
    "TREASURY_EXECUTION", "PLACE_TRADE", "BUY_ADS",
    "WIRE_USDT", "AUTO_BID", "SEND_EMAIL", "SETTLEMENT_CONFIRMED",
    "",None,
])
def test_swarm_refuses_invented_execution_signals(signal):
    redis=FakeRedis()
    with pytest.raises(RedisV4Hold,match="non_advisory"):
        emit_fixture_swarm_observation(
            redis,tenant_scope_digest=h("tenant"),
            event_digest=h("event"),signal=signal,
            source_evidence_digest=h("source"),now=NOW,fixture_authorised=True)
    assert redis._streams=={}


def test_swarm_event_requires_client_fixture_boundary():
    redis=FakeRedis()
    with pytest.raises(RedisV4Hold,match="disposable_fixture_io_only"):
        emit_fixture_swarm_observation(
            redis,tenant_scope_digest=h("tenant"),event_digest=h("event"),
            signal="CAPACITY_OBSERVED",source_evidence_digest=h("source"),
            now=NOW,fixture_authorised=False)


def test_pipeline_hash_reads_are_ordered_and_bounded():
    db=FakeRedis()
    a=example()
    b=example()
    b["entity_digest"]=h("fictional-entity-two")
    b["sector"]="hvac"
    b["pcvr"]="1.0"
    record_fixture_feature(db,a,now=NOW,fixture_authorised=True)
    record_fixture_feature(db,b,now=NOW,fixture_authorised=True)
    results=read_fixture_features_batch(
        db,tenant_scope_digest=a["tenant_scope_digest"],
        references=[("roofing",a["entity_digest"]),("hvac",b["entity_digest"])],
        now=NOW,fixture_authorised=True)
    assert [x["simulation_expected_net_cents"] for x in results]==[1400,8900]
    assert db._commands[-1]==("PIPELINED-HGETALL",2)


def test_pipeline_missing_hash_requires_canonical_fallback():
    a=example()
    result=read_fixture_features_batch(
        FakeRedis(),tenant_scope_digest=a["tenant_scope_digest"],
        references=[("roofing",a["entity_digest"])],
        now=NOW,fixture_authorised=True)
    assert result[0]["status"]=="CACHE_MISS_OR_EXPIRED"
    assert result[0]["empiredb_fallback_required"] is True


@pytest.mark.parametrize("refs",[
    [],
    [("roofing",h("entity"))]*33,
    [("roofing",h("entity"))]*2,
    [("roofing","not-digest")],
    [("trading",h("entity"))],
    [("roofing",h("entity"),"unexpected")],
])
def test_batch_refuses_invalid_or_duplicated_references(refs):
    db=FakeRedis()
    with pytest.raises(RedisV4Hold):
        read_fixture_features_batch(
            db,tenant_scope_digest=h("tenant"),references=refs,
            now=NOW,fixture_authorised=True)
    assert not db._commands


def test_pipeline_detects_hash_rewritten_to_other_tenant():
    db=FakeRedis()
    a=example()
    record_fixture_feature(db,a,now=NOW,fixture_authorised=True)
    key=feature_key(tenant_scope_digest=a["tenant_scope_digest"],
                    sector=a["sector"],entity_digest=a["entity_digest"])
    db._data[key][b"tenant_scope_digest"]=h("another-tenant").encode()
    with pytest.raises(RedisV4Hold,match="cross_tenant"):
        read_fixture_features_batch(
            db,tenant_scope_digest=a["tenant_scope_digest"],
            references=[("roofing",a["entity_digest"])],
            now=NOW,fixture_authorised=True)


def test_existing_predictive_cloud_status_preserves_unknown_redis_readiness(tmp_path):
    from empire_os.predictive_cloud_status import build_predictive_cloud_status
    status=build_predictive_cloud_status(tmp_path,now=NOW)
    redis=status["redis_v4_shadow"]
    assert redis["status"]=="REDIS_CLOUD_NOT_CONNECTED"
    assert redis["real_latency_benchmark_ms"] is None
    assert redis["real_peak_iops_benchmark"] is None
    assert redis["real_multi_region_active_active_verified"] is False
    assert redis["redis_used_for_critical_money_authority"] is False
    assert redis["canonical_financial_ledger"]=="EmpireDB_PostgreSQL"
    assert status["execution_authority"]=="none"
    assert status["available_component_count"]==0


def test_fenced_feature_write_rejects_old_and_duplicate_revisions():
    db=FakeRedis()
    source=example()
    record_fixture_feature(db,source,now=NOW,fixture_authorised=True,ttl_seconds=20)
    older=source.copy()
    older["revision"]=2
    older["pcvr"]="0.990000"
    with pytest.raises(RedisV4Hold,match="outdated_or_duplicate"):
        record_fixture_feature(db,older,now=NOW,fixture_authorised=True,ttl_seconds=50)
    with pytest.raises(RedisV4Hold,match="outdated_or_duplicate"):
        record_fixture_feature(db,source,now=NOW,fixture_authorised=True)
    key=feature_key(tenant_scope_digest=source["tenant_scope_digest"],
                    sector=source["sector"],entity_digest=source["entity_digest"])
    assert db._ttl[key]==20
    assert db._data[key][b"pcvr"]==b"0.250000"
    fresh=source.copy()
    fresh["revision"]=4
    fresh["pcvr"]="0.300000"
    record_fixture_feature(db,fresh,now=NOW,fixture_authorised=True,ttl_seconds=25)
    assert db._data[key][b"pcvr"]==b"0.300000"
    assert db._ttl[key]==25


def test_fenced_feature_write_rejects_corrupt_existing_revision():
    db=FakeRedis()
    value=example()
    record_fixture_feature(db,value,now=NOW,fixture_authorised=True)
    key=feature_key(tenant_scope_digest=value["tenant_scope_digest"],
                    sector=value["sector"],entity_digest=value["entity_digest"])
    db._data[key][b"revision"]=b"not-a-number"
    newer=value.copy()
    newer["revision"]=4
    with pytest.raises(RedisV4Hold,match="corrupt_cached_revision"):
        record_fixture_feature(db,newer,now=NOW,fixture_authorised=True)


def test_fenced_revision_is_single_shard_only_not_multiregion_money_authority():
    assert "HGET" in FEATURE_REVISION_FENCE_LUA
    assert "HSET" in FEATURE_REVISION_FENCE_LUA
    assert "EXPIRE" in FEATURE_REVISION_FENCE_LUA
    assert "KEYS[1]" in FEATURE_REVISION_FENCE_LUA
    assert "unpack(ARGV, 3)" in FEATURE_REVISION_FENCE_LUA
    assert "redis.call('XADD'" not in FEATURE_REVISION_FENCE_LUA
    assert readiness()["real_multi_region_active_active_verified"] is False
