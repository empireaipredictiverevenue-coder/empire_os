"""Original EmpireOS Predictive Cloud V4.1 Redis hot-path *research* adapter.

Optional disposable Redis-command client injection only. No Redis Cloud DNS,
network, credentials, service installation, HTTP endpoint, scheduled worker,
production EmpireDB writes, financial/outbound/execution authority. All live
Redis actions require independent owner connector and network approval.

Redis is a best-effort feature projection / advisory stream, NEVER the
canonical settlement, entitlement, payment, capacity reservation or lock.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone, timedelta
from decimal import Decimal, ROUND_HALF_UP
import re
from typing import Any

SCHEMA = "empire.predictive_cloud.v4.redis_shadow.v1"
STREAM = "v4:stream:swarm_consensus:shadow"
ALLOWED_SECTORS = frozenset({
    "roofing", "hvac", "solar", "dental", "legal", "b2b_saas",
    "ecommerce", "logistics", "heat_pumps", "storm",
})
ALLOWED_SIGNALS = frozenset({
    "RISK_CONSTRAINT_OBSERVED", "CAPACITY_OBSERVED", "YIELD_ESTIMATE_OBSERVED",
})
DIGEST = re.compile(r"^[0-9a-f]{64}$")
MAX_TTL = 60
MAX_AGE = 30
MAX_CENTS = 10**9
# Atomic against competing writers to a SINGLE Redis primary/key only.
# Not a global ordering primitive for Redis Cloud Active-Active CRDT regions.
# A canonical EmpireDB model/source revision must be approved independently.
FEATURE_REVISION_FENCE_LUA = """
local current = redis.call('HGET', KEYS[1], 'revision')
local proposed = tonumber(ARGV[1])
if current then
  local previous = tonumber(current)
  if not previous then return -1 end
  if previous >= proposed then return 0 end
end
redis.call('HSET', KEYS[1], unpack(ARGV, 3))
redis.call('EXPIRE', KEYS[1], tonumber(ARGV[2]))
return 1
"""
FIELDS = frozenset({
    "schema_version", "tenant_scope_digest", "entity_digest", "sector",
    "source_evidence_digest", "revision", "observed_at",
    "pcvr", "gross_cents", "acquisition_cost_cents",
    "fulfilment_cost_cents", "processing_fee_cents", "capacity",
    "synthetic_only",
})


class RedisV4Hold(ValueError):
    pass


def _digest(value: Any) -> str:
    if type(value) is not str or DIGEST.fullmatch(value) is None:
        raise RedisV4Hold("v4_opaque_lowercase_sha256_digest_required")
    return value


def _timestamp(value: Any) -> datetime:
    if type(value) is not str or not 20 <= len(value) <= 40:
        raise RedisV4Hold("v4_bounded_timestamp_required")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise RedisV4Hold("v4_timestamp_invalid") from None
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise RedisV4Hold("v4_exact_utc_required")
    return parsed.astimezone(timezone.utc)


def _valid_now(now: datetime) -> datetime:
    if not isinstance(now,datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise RedisV4Hold("v4_trusted_aware_clock_required")
    return now.astimezone(timezone.utc)


def _nonnegative(value: Any, *, name: str, ceiling: int) -> int:
    if type(value) is not int or not 0 <= value <= ceiling:
        raise RedisV4Hold(f"v4_invalid_{name}")
    return value


def _pcvr(value: Any) -> Decimal:
    # Use a bounded, canonical decimal text: not binary floats, NaN or inf.
    if type(value) is not str or re.fullmatch(r"(?:0(?:\.\d{1,6})?|1(?:\.0{1,6})?)", value) is None:
        raise RedisV4Hold("v4_pcvr_probability_bounded_decimal_required")
    return Decimal(value)


def feature_key(*,tenant_scope_digest: str,sector: str,entity_digest: str)->str:
    _digest(tenant_scope_digest)
    _digest(entity_digest)
    if type(sector) is not str or sector not in ALLOWED_SECTORS:
        raise RedisV4Hold("v4_supported_sector_required")
    # Explicit tenant namespace. No hash-tag hotspot, raw contact,
    # identity, prospect id, phone, domain, email, wallet or text.
    return f"v4:feature_vector:{tenant_scope_digest}:{sector}:{entity_digest}"


def _bounded_projection(record: Mapping[str,Any], *, now: datetime) -> dict[str,Any]:
    clock=_valid_now(now)
    if type(record) is not dict or set(record)!=FIELDS:
        raise RedisV4Hold("v4_exact_feature_payload_contract_required")
    if record["schema_version"]!=SCHEMA or record["synthetic_only"] is not True:
        raise RedisV4Hold("v4_fixture_only_data_required")
    _digest(record["source_evidence_digest"])
    key=feature_key(
        tenant_scope_digest=record["tenant_scope_digest"],
        sector=record["sector"],entity_digest=record["entity_digest"],
    )
    revision=_nonnegative(record["revision"],name="revision",ceiling=1_000_000_000)
    if revision==0:
        raise RedisV4Hold("v4_positive_revision_required")
    cvr=_pcvr(record["pcvr"])
    gross=_nonnegative(record["gross_cents"],name="gross_cents",ceiling=MAX_CENTS)
    acq=_nonnegative(record["acquisition_cost_cents"],name="acquisition_cost_cents",ceiling=MAX_CENTS)
    fulfil=_nonnegative(record["fulfilment_cost_cents"],name="fulfilment_cost_cents",ceiling=MAX_CENTS)
    fee=_nonnegative(record["processing_fee_cents"],name="processing_fee_cents",ceiling=MAX_CENTS)
    capacity=_nonnegative(record["capacity"],name="capacity",ceiling=1_000_000)
    observed=_timestamp(record["observed_at"])
    seconds=(clock-observed).total_seconds()
    if not 0 <= seconds <= MAX_AGE:
        raise RedisV4Hold("v4_future_or_stale_feature_refused")
    expected=(cvr*Decimal(gross)-Decimal(acq+fulfil+fee)).quantize(Decimal("1"),rounding=ROUND_HALF_UP)
    return {
        "feature_key":key,
        "source_evidence_digest":record["source_evidence_digest"],
        "tenant_scope_digest":record["tenant_scope_digest"],
        "entity_digest":record["entity_digest"],
        "sector":record["sector"],
        "revision":revision,
        "observed_at":observed.isoformat(),
        "pcvr":str(cvr),
        "gross_cents":gross,
        "acquisition_cost_cents":acq,
        "fulfilment_cost_cents":fulfil,
        "processing_fee_cents":fee,
        "capacity":capacity,
        "simulation_expected_net_cents":int(expected),
        "eligible_for_real_routing":False,
        "realised_net_profit_cents":None,
        "empiredb_authority":"not_verified",
        "execution_authority":"none",
    }


def inspect_fixture_feature(record: Mapping[str,Any], *, now: datetime) -> dict[str,Any]:
    """Pure contract projection; a source digest does not prove source rights."""
    return _bounded_projection(record,now=now)


def _encoded(record: Mapping[str,Any]) -> dict[str,str]:
    return {
        name: str(record[name]).lower() if type(record[name]) is bool else str(record[name])
        for name in sorted(FIELDS)
    }


def record_fixture_feature(
    client: Any, record: Mapping[str,Any], *, now: datetime,
    ttl_seconds: int=15, fixture_authorised: bool=False,
) -> dict[str,Any]:
    """Only explicitly injected fake clients; no live credentials, no timer.

    The flag grants permission ONLY to an isolated test caller and cannot
    be used to claim production source/canonical tenant authority.
    """
    projection=_bounded_projection(record,now=now)
    if fixture_authorised is not True or getattr(client,"is_v4_disposable_fixture",None) is not True:
        raise RedisV4Hold("v4_disposable_fixture_io_only")
    if type(ttl_seconds) is not int or not 1<=ttl_seconds<=MAX_TTL:
        raise RedisV4Hold("v4_ttl_out_of_bounds")
    # Single-key Lua protects monotonic revision plus TTL atomically on
    # ONE shard. No comparable guarantee between Active-Active regions.
    # The injected disposable fake implements this same single-key boundary;
    # this is NOT a verified Redis Cloud execution.
    encoded=_encoded(record)
    args=[]
    for name in sorted(encoded):
        args.extend((name,encoded[name]))
    reply=client.eval(
        FEATURE_REVISION_FENCE_LUA,1,projection["feature_key"],
        str(projection["revision"]),str(ttl_seconds),*args,
    )
    if type(reply) is not int:
        raise RedisV4Hold("v4_shadow_feature_write_unconfirmed")
    if reply==0:
        raise RedisV4Hold("v4_outdated_or_duplicate_revision_refused")
    if reply==-1:
        raise RedisV4Hold("v4_corrupt_cached_revision_refused")
    if reply!=1:
        raise RedisV4Hold("v4_shadow_feature_write_unconfirmed")
    return {
        "schema_version":SCHEMA,
        "status":"DISPOSABLE_FEATURE_HASH_WRITTEN",
        "key":projection["feature_key"],
        "ttl_seconds":ttl_seconds,
        "tenant_scope_digest":record["tenant_scope_digest"],
        "real_redis_cloud_connected":False,
        "production_empiredb_writes":False,
        "paid_traffic":False,
        "outbound_sent":False,
        "treasury_execution":False,
        "execution_authority":"fixture_only",
    }


def _review_feature_hash(data: Any, key: str, now: datetime)->dict[str,Any]:
    if not data:
        return {
            "status":"CACHE_MISS_OR_EXPIRED", "execution_authority":"none",
            "empiredb_fallback_required":True,
        }
    if not isinstance(data,dict) or len(data)>len(FIELDS):
        raise RedisV4Hold("v4_untrusted_redis_hash")
    try:
        decoded={
            (k.decode("ascii") if isinstance(k,bytes) else k):
            (v.decode("ascii") if isinstance(v,bytes) else v)
            for k,v in data.items()
        }
        if set(decoded)!=FIELDS:
            raise RedisV4Hold("v4_untrusted_redis_hash_fields")
        numeric=("revision","gross_cents","acquisition_cost_cents",
                 "fulfilment_cost_cents","processing_fee_cents","capacity")
        for n in numeric:
            if re.fullmatch(r"0|[1-9][0-9]*",decoded[n]) is None:
                raise RedisV4Hold("v4_untrusted_redis_hash_integer")
            decoded[n]=int(decoded[n])
        if decoded["synthetic_only"]!="true":
            raise RedisV4Hold("v4_untrusted_redis_hash_synthetic_only")
        decoded["synthetic_only"]=True
        projection=_bounded_projection(decoded,now=now)
        if projection["feature_key"]!=key:
            raise RedisV4Hold("v4_cross_tenant_or_entity_hash_refused")
        projection["status"]="DISPOSABLE_FEATURE_HASH_READ"
        return projection
    except (AttributeError,UnicodeError,KeyError,TypeError,ValueError) as e:
        if isinstance(e,RedisV4Hold):
            raise
        raise RedisV4Hold("v4_untrusted_redis_hash_decode") from None




def read_fixture_feature(
    client: Any, *, tenant_scope_digest: str, sector: str,
    entity_digest: str, now: datetime, fixture_authorised: bool=False,
) -> dict[str,Any]:
    key=feature_key(tenant_scope_digest=tenant_scope_digest,
                    sector=sector,entity_digest=entity_digest)
    if fixture_authorised is not True or getattr(client,"is_v4_disposable_fixture",None) is not True:
        raise RedisV4Hold("v4_disposable_fixture_io_only")
    return _review_feature_hash(client.hgetall(key),key,now)


def read_fixture_features_batch(
    client: Any, *, tenant_scope_digest: str,
    references: list[tuple[str,str]], now: datetime,
    fixture_authorised: bool=False,
) -> list[dict[str,Any]]:
    """Bounded pipelined HGETALL, never MGET for Hash values.

    Redis Cluster distribution, multi-key atomicity and real speed are NOT
    measured here. Results are order-preserving and checked per-tenant.
    """
    _valid_now(now)
    _digest(tenant_scope_digest)
    if (fixture_authorised is not True
        or getattr(client,"is_v4_disposable_fixture",None) is not True):
        raise RedisV4Hold("v4_disposable_fixture_io_only")
    if type(references) is not list or not 1<=len(references)<=32:
        raise RedisV4Hold("v4_batch_bounds_required")
    keys=[]
    for item in references:
        if type(item) is not tuple or len(item)!=2:
            raise RedisV4Hold("v4_batch_exact_reference_required")
        keys.append(feature_key(
            tenant_scope_digest=tenant_scope_digest,
            sector=item[0],entity_digest=item[1]))
    if len(set(keys))!=len(keys):
        raise RedisV4Hold("v4_batch_duplicate_refused")
    pipeline=client.pipeline(transaction=False)
    for key in keys:
        pipeline.hgetall(key)
    results=pipeline.execute()
    if type(results) not in (list,tuple) or len(results)!=len(keys):
        raise RedisV4Hold("v4_pipeline_incomplete_results")
    return [_review_feature_hash(data,key,now) for key,data in zip(keys,results)]


def emit_fixture_swarm_observation(
    client: Any, *, tenant_scope_digest: str, event_digest: str,
    signal: str, source_evidence_digest: str,
    now: datetime, fixture_authorised: bool=False,
) -> dict[str,Any]:
    _valid_now(now)
    for digest in (tenant_scope_digest,event_digest,source_evidence_digest):
        _digest(digest)
    if type(signal) is not str or signal not in ALLOWED_SIGNALS:
        raise RedisV4Hold("v4_non_advisory_swarm_event_refused")
    if fixture_authorised is not True or getattr(client,"is_v4_disposable_fixture",None) is not True:
        raise RedisV4Hold("v4_disposable_fixture_io_only")
    # Per-tenant, nonfinancial OBSERVE lane. Not a globally ordered,
    # multi-region risk/treasury execution stream.
    stream=f"{STREAM}:{tenant_scope_digest}"
    message={
        "schema_version":SCHEMA,"event_digest":event_digest,
        "source_evidence_digest":source_evidence_digest,
        "signal":signal,"mode":"OBSERVE","execution_authority":"none",
        "observed_at":_valid_now(now).isoformat(),
    }
    msg_id=client.xadd(stream,message,id="*")
    if not isinstance(msg_id,(str,bytes)) or not msg_id:
        raise RedisV4Hold("v4_fixture_stream_unacknowledged")
    return {
        "status":"DISPOSABLE_ADVISORY_STREAM_APPENDED",
        "stream":stream,
        "event_digest":event_digest,
        "stream_id":msg_id.decode("ascii") if isinstance(msg_id,bytes) else msg_id,
        "redis_delivery_guaranteed":False,
        "durable_ledger_committed":False,
        "treasury_execution":False,
        "outbound_sent":False,
        "execution_authority":"fixture_only",
    }


def readiness() -> dict[str,Any]:
    """Never infer live Redis capability from source code or fake results."""
    return {
        "schema_version":SCHEMA,
        "mode":"OBSERVE",
        "status":"REDIS_CLOUD_NOT_CONNECTED",
        "original_predictive_cloud_preserved":True,
        "canonical_financial_ledger":"EmpireDB_PostgreSQL",
        "local_redis_client_verified":False,
        "redis_cloud_subscription_verified":False,
        "private_network_path_verified":False,
        "real_latency_benchmark_ms":None,
        "real_peak_iops_benchmark":None,
        "real_multi_region_active_active_verified":False,
        "real_client_credentials_verified":False,
        "redis_used_for_critical_money_authority":False,
        "paid_traffic":False,
        "production_empiredb_writes":False,
        "execution_authority":"none",
    }
