"""One-hit read-only Lead Smart Ringba proof using existing root-owned config.

No new timer or third-party provider. Root is required solely because the
existing /etc/empire_ringba.env is 0600/root:root. No outbound, call, update
or launch action is implemented. Do not log token, account ID, caller ANI,
buyer route numbers, exception messages or raw provider responses.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shlex
import stat
from typing import Any, Callable

from empire_os import lead_smart_ringba_api_observer as api
from empire_os import lead_smart_ringba_routing_observer as routing
from empire_os import lead_smart_ringba_tracking_observer as tracking

CONFIG = Path("/etc/empire_ringba.env")
KEY = re.compile(r"^(?:export\s+)?(RINGBA_API_TOKEN|RINGBA_ACCOUNT_ID)=(.*)$")
MAX_CONFIG = 8192

class RingbaPreflightHold(RuntimeError):
    pass


def read_root_config(path: Path = CONFIG, *, euid: int | None = None) -> dict[str,str]:
    effective = os.geteuid() if euid is None else euid
    if effective != 0:
        raise RingbaPreflightHold("ROOT_OWNED_CONFIGURATION_REQUIRES_PRIVILEGED_READER")
    try:
        if path.is_symlink():
            raise RingbaPreflightHold("RINGBA_CONFIG_SYMLINK_NOT_ALLOWED")
        metadata = path.stat()
        if (not stat.S_ISREG(metadata.st_mode)
                or metadata.st_uid != 0
                or metadata.st_gid != 0
                or metadata.st_mode & 0o177
                or not 0 < metadata.st_size <= MAX_CONFIG):
            raise RingbaPreflightHold("RINGBA_CONFIG_OWNERSHIP_OR_MODE_UNSAFE")
        data = path.read_text(encoding="utf-8")
    except (OSError,UnicodeError) as exc:
        raise RingbaPreflightHold("RINGBA_CONFIG_UNAVAILABLE") from exc
    result={}
    for line in data.splitlines():
        line=line.strip()
        if not line or line.startswith("#"):
            continue
        match=KEY.fullmatch(line)
        if not match:
            raise RingbaPreflightHold("UNSUPPORTED_RINGBA_CONFIG_LINE")
        key,value=match.groups()
        if key in result:
            raise RingbaPreflightHold("DUPLICATE_RINGBA_CONFIG_KEY")
        # Parse only one shell literal; NEVER evaluate commands or expansions.
        if "$" in value or "`" in value or "\\n" in value:
            raise RingbaPreflightHold("UNSAFE_RINGBA_CONFIG_VALUE")
        try:
            pieces=shlex.split(value,posix=True)
        except ValueError as exc:
            raise RingbaPreflightHold("MALFORMED_RINGBA_CONFIG_VALUE") from exc
        if len(pieces)!=1 or not pieces[0] or len(pieces[0])>4096:
            raise RingbaPreflightHold("MALFORMED_RINGBA_CONFIG_VALUE")
        result[key]=pieces[0]
    if not result.get("RINGBA_API_TOKEN"):
        raise RingbaPreflightHold("RINGBA_API_TOKEN_NOT_CONFIGURED")
    return result


def _probe(kind: str, getter: Callable[[],dict[str,Any]]) -> dict[str,Any]:
    try:
        data=getter()
        if not isinstance(data,dict):
            raise TypeError("nonobject provider response")
        if kind=="tracking":
            if data.get("schema_version")!=tracking.SCHEMA_VERSION:
                raise ValueError("schema mismatch")
            return {
                "status":"OBSERVED",
                "provider_number_campaign_binding":data.get("provider_binding_verified") is True,
                "source_freshness":"CURRENT_PROVIDER_OBSERVATION",
            }
        if kind=="routing":
            if data.get("schema_version")!=routing.SCHEMA_VERSION:
                raise ValueError("schema mismatch")
            scope=data.get("route_visibility") or {}
            endpoint=data.get("call_routes_endpoint") or {}
            return {
                "status":"OBSERVED",
                "call_routes_http_status":endpoint.get("status") if type(endpoint.get("status")) is int else None,
                "route_visibility":str(scope.get("scope") or "UNVERIFIED_API_SCOPE")[:80],
                "buyer_route_live_proven":False,
                "caller_ani_pass_through_proven":False,
            }
        if data.get("schema_version")!=api.SCHEMA_VERSION:
            raise ValueError("schema mismatch")
        return {
            "status":"OBSERVED",
            "matching_campaign_number_call_rows":data.get("exact_campaign_and_number_match_count",0),
            "provider_log_role":"RESTRICTED_AFFILIATE_OR_ACCOUNT",
            "buyer_leg_connection_proven":False,
            "revenue_verified":False,
        }
    except Exception as exc:
        # Ringba API errors may include raw private response excerpts.
        # Never output or persist str(exc), URLs, headers, tokens or IDs.
        kind_of_error=type(exc).__name__
        return {
            "status":"UNVERIFIED",
            "reason_code":("RINGBA_API_ACCESS_OR_RESPONSE_NOT_VERIFIED"
                           if kind_of_error in ("RingbaApiError","HTTPError")
                           else "RINGBA_PROBE_NOT_VERIFIED"),
            "buyer_route_live_proven":False,
        }


def run_once(token:str, account_hint:str|None, *,
             discover_accounts:Callable[[str],list[str]]=api.discover_accounts,
             choose_account:Callable[...,str]=api.choose_account,
             fetch_logs:Callable[...,Any]=api.fetch_recent_call_logs,
             tracking_observer:Callable[...,dict[str,Any]]=tracking.observe_tracking_objects,
             routing_observer:Callable[...,dict[str,Any]]=routing.observe_routing_objects,
             build_logs:Callable[...,dict[str,Any]]=api.build_schema_observation,
             ) -> dict[str,Any]:
    result={
        "schema_version":"empire.lead_smart.ringba_privileged_one_hit.v1",
        "mode":"OBSERVE", "source":"EXISTING_RINGBA_ACCOUNT",
        "commercial_activation":False,"test_call_performed":False,
        "outbound_sent":False,"execution_authority":"NONE",
    }
    try:
        accounts=discover_accounts(token)
        account_id=choose_account(accounts,account_hint)
    except Exception:
        result["status"]="ACCOUNT_SCOPE_UNVERIFIED"
        result["error_code"]="RINGBA_ACCOUNT_SELECTION_OR_ACCESS_UNVERIFIED"
        return result
    result["account_selection_resolved"]=True
    def logs():
        payload, negotiation=fetch_logs(token=token,account_id=account_id)
        d=build_logs(account_id=account_id,payload=payload)
        # No accounts, caller IDs, provider error excerpts or raw rows emitted.
        return d
    result["call_log_evidence"]=_probe("logs",logs)
    result["tracking_evidence"]=_probe(
        "tracking",lambda:tracking_observer(token=token,account_id=account_id))
    result["routing_evidence"]=_probe(
        "routing",lambda:routing_observer(token=token,account_id=account_id))
    probes=("call_log_evidence","tracking_evidence","routing_evidence")
    result["status"]=(
        "OBSERVATION_COMPLETE_LAUNCH_HELD"
        if all(result[name]["status"]=="OBSERVED" for name in probes)
        else "PROVIDER_EVIDENCE_INCOMPLETE"
    )
    result["buyer_leg_connection_proven"]=False
    result["caller_ani_pass_through_proven"]=False
    result["recording_notice_and_retention_verified"]=False
    result["launch_authorized"]=False
    return result


def main() -> int:
    try:
        conf=read_root_config()
    except RingbaPreflightHold as exc:
        print(json.dumps({
            "schema_version":"empire.lead_smart.ringba_privileged_one_hit.v1",
            "status":"BLOCKED","reason_code":str(exc),
            "outbound_sent":False,"execution_authority":"NONE",
        }))
        return 2
    result=run_once(conf["RINGBA_API_TOKEN"],conf.get("RINGBA_ACCOUNT_ID"))
    print(json.dumps(result,sort_keys=True))
    return 0 if result["status"]=="OBSERVATION_COMPLETE_LAUNCH_HELD" else 2

if __name__=="__main__":
    raise SystemExit(main())
