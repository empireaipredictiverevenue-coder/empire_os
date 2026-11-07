"""Narrow adapter to *candidate* canonical EmpireDB metering functions.

No schema creation, credential issuance or production connection is performed
by importing this module. The existing DB and gateway owners must provision a
dedicated, least-privilege login, review SQL and grant function execution.

This replaces the prototype SQLite pilot store ONLY after the canonical
EmpireDB contract is independently installed and verified.
"""
from __future__ import annotations
from hashlib import sha256
from json import loads
from typing import Any, Callable

from .durable_store import ActiveTenant, AdmissionError


class EmpireDbMeteringStore:
    """Only four dedicated PostgreSQL stored-function calls are permitted."""
    def __init__(self, connect: Callable[[], Any]):
        if not callable(connect):
            raise ValueError("dedicated_connection_factory_required")
        self._connect = connect

    def _call(self, name: str, params: tuple) -> Any:
        if name not in {"authenticate", "reserve", "settle", "usage_snapshot"}:
            raise ValueError("unapproved_data_cloud_db_operation")
        sql = {
            "authenticate": "SELECT empire_data_cloud_api.authenticate(%s::text)",
            "reserve": "SELECT empire_data_cloud_api.reserve(%s::text,%s::text,%s::text,%s::text,%s::text)",
            "settle": "SELECT empire_data_cloud_api.settle(%s::text,%s::bigint,%s::text,%s::bigint,%s::text)",
            "usage_snapshot": "SELECT empire_data_cloud_api.usage_snapshot(%s::text)",
        }[name]
        try:
            with self._connect() as con:
                with con.cursor() as cur:
                    cur.execute("SELECT current_database()::text,session_user::text")
                    proof=cur.fetchone()
                    if proof != ("empiredb", "empire_data_cloud_meter_login"):
                        raise AdmissionError(503,"dedicated_empiredb_meter_role_unverified")
                    cur.execute(sql,params)
                    result=cur.fetchone()
                    if not isinstance(result,(tuple,list)) or len(result)!=1:
                        raise AdmissionError(503,"empiredb_meter_result_unavailable")
                    return result[0]
        except AdmissionError:
            raise
        except Exception as exc:
            # Do not leak SQL, connection strings or privileged values.
            state=getattr(exc,"sqlstate",None)
            if state=="28000": raise AdmissionError(401,"valid_bearer_token_required") from exc
            if state=="42501": raise AdmissionError(403,"operation_or_tenant_not_entitled") from exc
            if state=="23505": raise AdmissionError(409,"idempotency_key_reused") from exc
            if state=="P0001": raise AdmissionError(429,"monthly_request_or_cost_cap_reached") from exc
            if state=="22023": raise AdmissionError(400,"invalid_request_identifier") from exc
            raise AdmissionError(503,"empiredb_meter_unavailable") from exc

    @staticmethod
    def _json(v: Any) -> dict:
        if isinstance(v,(bytes,str)):
            try: v=loads(v)
            except (ValueError,UnicodeError) as exc:
                raise AdmissionError(503,"invalid_empiredb_meter_payload") from exc
        if not isinstance(v,dict):
            raise AdmissionError(503,"invalid_empiredb_meter_payload")
        return v

    def authenticate(self, raw_token: str) -> ActiveTenant:
        if not isinstance(raw_token,str) or not 24<=len(raw_token)<=512:
            raise AdmissionError(401,"valid_bearer_token_required")
        digest=sha256(raw_token.encode()).hexdigest()
        p=self._json(self._call("authenticate",(digest,)))
        try:
            tenant_id=p["tenant_id"]
            ops=p["operations"]
            hosts=p["hosts"]
            nums=[p[k] for k in ("monthly_cap","cost_cap_micros","search_ceiling_micros","audit_ceiling_micros")]
            if (not isinstance(tenant_id,str) or not tenant_id or len(tenant_id)>100
                or not isinstance(ops,list) or not isinstance(hosts,list)
                or any(type(n) is not int or n<0 for n in nums)
                or any(type(item) is not str for item in ops+hosts)):
                raise ValueError("invalid")
            return ActiveTenant(tenant_id,*nums,frozenset(ops),frozenset(hosts))
        except (KeyError,TypeError,ValueError) as exc:
            raise AdmissionError(503,"invalid_empiredb_meter_payload") from exc

    def reserve(self, policy: ActiveTenant, operation: str, idempotency_key: str,
                request_hash: str, token_hash: str, target_host: str | None = None) -> int:
        if (not isinstance(token_hash,str) or len(token_hash)!=64):
            raise AdmissionError(401,"valid_bearer_token_required")
        number=self._call("reserve",(token_hash,operation,idempotency_key,request_hash,target_host))
        if type(number) is not int or number<=0:
            raise AdmissionError(503,"invalid_empiredb_reservation")
        return number

    def settle(self, policy: ActiveTenant, reservation_id: int, state: str,
               *, actual_usd_micros: int | None = None,
               cost_source_ref: str | None = None,token_hash: str | None = None) -> None:
        if not isinstance(token_hash,str) or len(token_hash)!=64:
            raise AdmissionError(401,"valid_bearer_token_required")
        # The SQL stores a provider-reported amount, NOT independently verified
        # costs; verified actual cost stays null until reconciliation by owner.
        result=self._call("settle",(token_hash,reservation_id,state,
                                    actual_usd_micros,cost_source_ref))
        if result=="cost_integrity_hold":
            raise AdmissionError(503,"provider_cost_exceeded_approved_ceiling_tenant_held")
        if result!=state:
            raise AdmissionError(503,"empiredb_usage_settlement_unavailable")

    def snapshot(self, policy: ActiveTenant, *, token_hash: str | None = None) -> dict:
        if not isinstance(token_hash,str) or len(token_hash)!=64:
            raise AdmissionError(401,"valid_bearer_token_required")
        snapshot=self._json(self._call("usage_snapshot",(token_hash,)))
        # Cost reports remain unverified until provider invoice/ledger joined.
        if snapshot.get("billing_enabled") is not False or snapshot.get("verified_actual_cost_usd_micros") is not None:
            raise AdmissionError(503,"unapproved_billing_state")
        return snapshot
