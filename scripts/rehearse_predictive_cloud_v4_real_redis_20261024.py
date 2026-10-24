#!/usr/bin/env python3
"""Real Redis 8 Unix-socket-only V4 feature and advisory Stream fixture.

RESEARCH ONLY: no TCP, no Redis Cloud, no EmpireDB writes, no sender, no
financial authority. This is an independent Redis RESP2 wire client built
using Python stdlib to avoid installing packages on production EmpireOS.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import socket
import stat
import threading
import time

from empire_os.predictive_cloud_v4_redis_shadow import (
    SCHEMA, RedisV4Hold, record_fixture_feature, read_fixture_feature,
    read_fixture_features_batch, emit_fixture_swarm_observation, feature_key,
)


def digest(s: str) -> str:
    return sha256(("fictional-v4-real-redis-test:"+s).encode()).hexdigest()


NOW = datetime.now(timezone.utc)


class RedisReplyError(RuntimeError):
    pass


class RedisSocket:
    is_v4_disposable_fixture = True

    def __init__(self,path: str):
        p=Path(path)
        if (not str(p).startswith("/tmp/empire-v4-redis-run.")
            or p.name!="redis.sock"
            or not p.is_socket()
            or not stat.S_ISSOCK(p.stat().st_mode)):
            raise RuntimeError("V4_REFUSED_NON_EPHEMERAL_REDIS_UNIX_SOCKET")
        self.path=str(p)

    def _wire(self,commands):
        with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as s:
            s.settimeout(4)
            s.connect(self.path)
            with s.makefile("rwb") as wire:
                for fields in commands:
                    parts=[str(x).encode() if not isinstance(x,bytes) else x for x in fields]
                    request=b"*"+str(len(parts)).encode()+b"\r\n"
                    for part in parts:
                        request+=b"$"+str(len(part)).encode()+b"\r\n"+part+b"\r\n"
                    wire.write(request)
                wire.flush()
                return [self._reply(wire) for _ in commands]

    @classmethod
    def _reply(cls,f):
        flag=f.read(1)
        if not flag:
            raise RedisReplyError("V4_REDIS_DISCONNECTED_BEFORE_REPLY")
        value=f.readline()
        if not value.endswith(b"\r\n"):
            raise RedisReplyError("V4_REDIS_INCOMPLETE_REPLY")
        value=value[:-2]
        if flag==b"-":
            raise RedisReplyError("V4_REDIS_ERROR:"+value.decode(errors="replace"))
        if flag==b":":
            return int(value)
        if flag==b"+":
            return value.decode()
        if flag==b"$":
            count=int(value)
            if count==-1:
                return None
            if count<0 or count>1_000_000:
                raise RedisReplyError("V4_REDIS_BULK_TOO_LARGE")
            blob=f.read(count+2)
            if len(blob)!=count+2 or not blob.endswith(b"\r\n"):
                raise RedisReplyError("V4_REDIS_INVALID_BULK")
            return blob[:-2]
        if flag==b"*":
            n=int(value)
            if n==-1:
                return None
            if n<0 or n>10000:
                raise RedisReplyError("V4_REDIS_ARRAY_TOO_LARGE")
            return [cls._reply(f) for _ in range(n)]
        raise RedisReplyError("V4_REDIS_UNSUPPORTED_RESP")

    def command(self,*args):
        return self._wire([args])[0]

    def eval(self,script,count,key,*args):
        return self.command("EVAL",script,count,key,*args)

    def hgetall(self,key):
        result=self.command("HGETALL",key)
        if type(result) is not list or len(result)%2:
            raise RedisReplyError("V4_INVALID_HASH_RESULT")
        return dict(zip(result[::2],result[1::2]))

    def xadd(self,key,message,*,id="*"):
        args=["XADD",key,id]
        for k,v in message.items():
            args.extend((k,v))
        return self.command(*args)

    def pipeline(self,*,transaction=False):
        if transaction:
            raise RedisReplyError("V4_NOT_TRANSACTIONAL_PIPELINE_IN_THIS_FIXTURE")
        return Pipeline(self)


class Pipeline:
    def __init__(self,client):
        self.client=client
        self.ops=[]
    def hgetall(self,key):
        self.ops.append(("HGETALL",key))
        return self
    def execute(self):
        output=self.client._wire(self.ops)
        return [dict(zip(x[::2],x[1::2])) if type(x) is list and len(x)%2==0
                else x for x in output]


def packet(*,entity: str, revision: int, now: datetime):
    return {
        "schema_version":SCHEMA,
        "tenant_scope_digest":digest("tenant"),
        "entity_digest":digest(entity),
        "sector":"roofing",
        "source_evidence_digest":digest("fictional-source"),
        "revision":revision,
        "observed_at":now.isoformat(),
        "pcvr":"0.250000",
        "gross_cents":10000,
        "acquisition_cost_cents":100,
        "fulfilment_cost_cents":900,
        "processing_fee_cents":100,
        "capacity":9,
        "synthetic_only":True,
    }


def main():
    path=os.environ.get("EMPIRE_V4_REDIS_FIXTURE_SOCKET","")
    redis=RedisSocket(path)
    assert redis.command("PING")=="PONG"
    assert redis.command("CONFIG","GET","port")==[b"port",b"0"]
    assert redis.command("CONFIG","GET","appendonly")==[b"appendonly",b"no"]
    assert redis.command("CONFIG","GET","save")==[b"save",b""]
    redis.command("FLUSHDB")
    now=datetime.now(timezone.utc)
    key_record=packet(entity="roofing-first",revision=5,now=now)
    original=record_fixture_feature(redis,key_record,now=now,ttl_seconds=6,
                                    fixture_authorised=True)
    assert original["status"]=="DISPOSABLE_FEATURE_HASH_WRITTEN"
    stale=key_record.copy()
    stale["revision"]=4
    stale["pcvr"]="0.990000"
    for bad in (stale,key_record):
        try:
            record_fixture_feature(redis,bad,now=now,ttl_seconds=10,
                                   fixture_authorised=True)
        except RedisV4Hold as e:
            assert "outdated_or_duplicate_revision" in str(e)
        else:
            raise AssertionError("V4_OLD_OR_DUPLICATE_REVISION_OVERWROTE_HASH")
    key=feature_key(tenant_scope_digest=key_record["tenant_scope_digest"],
                    entity_digest=key_record["entity_digest"],sector="roofing")
    assert redis.command("HGET",key,"revision")==b"5"
    assert redis.command("HGET",key,"pcvr")==b"0.250000"
    assert 0 < redis.command("TTL",key) <=6

    # This runs independent socket connections. The actual Redis server
    # serializes EVAL for one key. Highest fixture revision must survive.
    barrier=threading.Barrier(8)
    def contender(revision):
        c=RedisSocket(path)
        local=packet(entity="roofing-first",revision=revision,now=now)
        local["pcvr"]=f"0.{revision:06d}"
        barrier.wait(timeout=5)
        try:
            record_fixture_feature(c,local,now=now,ttl_seconds=9,
                                   fixture_authorised=True)
            return "accepted"
        except RedisV4Hold as e:
            assert "outdated_or_duplicate_revision" in str(e)
            return "rejected"
    with ThreadPoolExecutor(max_workers=8) as executor:
        outcomes=list(executor.map(contender,range(6,14)))
    assert "accepted" in outcomes
    assert redis.command("HGET",key,"revision")==b"13"
    assert redis.command("HGET",key,"pcvr")==b"0.000013"
    assert 0 < redis.command("TTL",key) <=9
    fetched=read_fixture_feature(
        redis,tenant_scope_digest=key_record["tenant_scope_digest"],
        sector="roofing",entity_digest=key_record["entity_digest"],
        now=now,fixture_authorised=True,
    )
    assert fetched["revision"]==13
    assert fetched["eligible_for_real_routing"] is False

    second=packet(entity="roofing-second",revision=1,now=now)
    record_fixture_feature(redis,second,now=now,ttl_seconds=3,
                           fixture_authorised=True)
    batch=read_fixture_features_batch(
        redis,tenant_scope_digest=key_record["tenant_scope_digest"],
        references=[("roofing",key_record["entity_digest"]),
                    ("roofing",second["entity_digest"])],
        now=now,fixture_authorised=True,
    )
    assert [r["revision"] for r in batch]==[13,1]
    assert [r["simulation_expected_net_cents"] for r in batch]==[-1100,1400]

    # A truly different tenant cannot discover another tenant's key by
    # correctly formed request. Redis ACLs are still not configured here.
    wrong_tenant=read_fixture_feature(
        redis,tenant_scope_digest=digest("other-tenant"),
        sector="roofing",entity_digest=key_record["entity_digest"],
        now=now,fixture_authorised=True,
    )
    assert wrong_tenant["status"]=="CACHE_MISS_OR_EXPIRED"

    streamargs=dict(
        tenant_scope_digest=key_record["tenant_scope_digest"],
        event_digest=digest("replayed-advisory"),
        signal="RISK_CONSTRAINT_OBSERVED",
        source_evidence_digest=key_record["source_evidence_digest"],
        now=now,fixture_authorised=True,
    )
    a=emit_fixture_swarm_observation(redis,**streamargs)
    b=emit_fixture_swarm_observation(redis,**streamargs)
    assert a["stream_id"]!=b["stream_id"]
    assert redis.command("XLEN",a["stream"])==2
    assert a["durable_ledger_committed"] is False
    assert a["treasury_execution"] is False

    expiring=packet(entity="expires-fast",revision=2,now=now)
    record_fixture_feature(redis,expiring,now=now,ttl_seconds=1,
                           fixture_authorised=True)
    time.sleep(1.3)
    miss=read_fixture_feature(
        redis,tenant_scope_digest=expiring["tenant_scope_digest"],
        sector="roofing",entity_digest=expiring["entity_digest"],
        now=now,fixture_authorised=True,
    )
    assert miss["status"]=="CACHE_MISS_OR_EXPIRED"

    print(json.dumps({
        "status":"REAL_LOCAL_REDIS8_V4_HOTPATH_PASS",
        "redis_version":redis.command("INFO","server").decode().split("redis_version:")[1].splitlines()[0],
        "unix_socket_only":True,
        "tcp_port":0,
        "persistence_enabled":False,
        "lua_atomic_revision_fence":True,
        "concurrent_independent_writer_connections":8,
        "final_revision":13,
        "pipelined_two_hash_read":True,
        "ttl_real_expiry":True,
        "stream_duplicate_observations_stored":2,
        "redis_cloud_connected":False,
        "production_empiredb_touched":False,
        "money_moved":False,
        "paid_traffic":False,
        "real_latency_slo_verified":False,
        "real_multi_region_semantics_verified":False,
    },sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
