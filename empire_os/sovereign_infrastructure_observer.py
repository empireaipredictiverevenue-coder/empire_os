"""Read-only sovereign infrastructure evidence for EXISTING EmpireOS Ops Control.

No credentials, network requests, restarts, repairs, writes, new servers,
timers, backup creation, outbound, source activation or funding actions.
Existing Ops Control owns publication to its normal founder-readable snapshot.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import os
import re
import subprocess
from typing import Any, Callable

SCHEMA = "empire.sovereign_infrastructure_observer.v1"
# These are *known* existing services; idle oneshots are not presumed broken.
UNITS = (
    ("empire-founder-console.service", "resident", "interface"),
    ("empire-founder-dashboard-api.service", "resident", "interface"),
    ("postgresql@18-main.service", "resident", "database"),
    ("pgbouncer.service", "resident", "database"),
    ("empire-cloudflared.service", "resident", "connectivity"),
    ("empire-autonomous-revenue-os.service", "resident", "commercial"),
    ("empire-department-cycle.service", "oneshot", "departments"),
    ("empire-media-os.service", "oneshot", "media"),
    ("empire-data-exchange-custody-capture.service", "oneshot", "custody"),
)
MAX_OUTPUT=4096


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8",errors="replace")[:8192]
    except OSError:
        return None


def _systemd_state(
    name: str, *, runner: Callable[..., Any] = subprocess.run,
) -> dict[str, str]:
    result=runner(
        ["systemctl","show",name,"--property=LoadState,ActiveState,Result",
         "--no-pager"],capture_output=True,text=True,timeout=5,check=False,
    )
    if result.returncode:
        return {"load":"unknown","active":"unknown","result":"unknown"}
    raw=(result.stdout or "")[:MAX_OUTPUT]
    props={}
    for line in raw.splitlines():
        key,sep,value=line.partition("=")
        if sep and key in {"LoadState","ActiveState","Result"}:
            props[key]=value
    return {
        "load":props.get("LoadState","unknown"),
        "active":props.get("ActiveState","unknown"),
        "result":props.get("Result","unknown"),
    }


def _host_summary(
    *, meminfo: str | None, mdstat: str | None, disk: Any,
    cpu_cores: int | None,
) -> dict[str, Any]:
    avail=None
    total=None
    if isinstance(meminfo,str):
        for name,value in re.findall(r"^(MemTotal|MemAvailable):\s*(\d+) kB\s*$",meminfo,re.M):
            if name=="MemTotal":total=int(value)*1024
            elif name=="MemAvailable":avail=int(value)*1024
    disk_total=None
    disk_available=None
    if disk is not None:
        try:
            disk_total=int(disk.f_blocks)*int(disk.f_frsize)
            disk_available=int(disk.f_bavail)*int(disk.f_frsize)
        except (AttributeError,TypeError,ValueError):
            pass
    arrays=[]
    if isinstance(mdstat,str):
        for line in mdstat.splitlines():
            match=re.match(r"^\s*(md\d+)\s*:\s*active\s+raid1\b",line)
            if match:
                arrays.append(match.group(1))
        # RAID replication != off-node backup and no replacement for restore.
        degraded=bool(re.search(r"\[U_\]|\[_U\]|\[__\]",mdstat))
        raid_status=(
            "DEGRADED" if degraded
            else "MIRRORED_PRESENT" if arrays and "[UU]" in mdstat
            else "UNVERIFIED"
        )
    else:
        raid_status="UNKNOWN"
    return {
        "cpu_logical_cores":cpu_cores if isinstance(cpu_cores,int) and cpu_cores>0 else None,
        "memory_total_bytes":total,
        "memory_available_bytes":avail,
        "disk_total_bytes":disk_total,
        "disk_available_bytes":disk_available,
        "raid1_arrays":arrays,
        "raid_status":raid_status,
        "separate_recovery_copy_verified":False,
        "backup_restore_rehearsal_verified":False,
        "high_availability_failover_verified":False,
    }


def collect_sovereign_infrastructure_health(
    *, runner: Callable[..., Any] = subprocess.run,
    meminfo: str | None = None, mdstat: str | None = None,
    disk: Any = None, cpu_cores: int | None = None,
) -> dict[str, Any]:
    """Snapshot fixed service and resource evidence; never touch credentials."""
    # Injected inputs enable deterministic tests without touching production.
    if meminfo is None: meminfo=_read(Path("/proc/meminfo"))
    if mdstat is None: mdstat=_read(Path("/proc/mdstat"))
    if disk is None:
        try: disk=os.statvfs("/")
        except OSError: disk=None
    if cpu_cores is None: cpu_cores=os.cpu_count()
    resources=_host_summary(
        meminfo=meminfo,mdstat=mdstat,disk=disk,cpu_cores=cpu_cores)
    services=[]
    findings=[]
    for name,kind,domain in UNITS:
        try:state=_systemd_state(name,runner=runner)
        except (OSError,subprocess.SubprocessError,TimeoutError):
            state={"load":"unknown","active":"unknown","result":"unknown"}
        # Inactive successful oneshots are normal; failed oneshots are not.
        if state["load"]!="loaded" or state["active"] in ("unknown","failed"):
            classification="FAILED" if state["active"]=="failed" else "UNKNOWN"
        elif kind=="resident" and state["active"]=="active" and state["result"]=="success":
            classification="RUNNING"
        elif kind=="resident" and state["active"]!="active":
            classification="FAILED"
        elif kind=="oneshot" and state["active"] in {"inactive","active"} and state["result"]=="success":
            classification="EXPECTED_ONESHOT" if state["active"]=="inactive" else "RUNNING"
        elif kind=="oneshot" and state["active"]=="activating":
            classification="RUNNING"
        else:
            classification="UNKNOWN"
        row={"unit":name,"domain":domain,"kind":kind,
             "classification":classification,
             "active_state":state["active"],"unit_result":state["result"]}
        services.append(row)
        if classification in {"FAILED","UNKNOWN"}:
            findings.append({
                "code":"critical_service_down",
                "component":name,"severity":"critical" if domain in {"database","commercial"} else "warning",
                "commercial_priority":95 if domain in {"database","commercial"} else 75,
                "repairable":False,
                "summary":"Existing owned service needs evidence-based diagnosis",
                "evidence":{"active_state":state["active"],"result":state["result"],
                            "domain":domain},
            })
    if resources["raid_status"]=="DEGRADED":
        findings.append({
            "code":"infrastructure_raid_degraded","component":"mdraid",
            "severity":"critical","commercial_priority":100,
            "repairable":False,"summary":"Mirrored disk array degraded",
            "evidence":{"raid_status":"DEGRADED"},
        })
    blockers=[]
    if not resources["separate_recovery_copy_verified"]:
        blockers.append("OFF_NODE_BACKUP_NOT_VERIFIED")
    if not resources["backup_restore_rehearsal_verified"]:
        blockers.append("RESTORE_REHEARSAL_NOT_VERIFIED")
    if not resources["high_availability_failover_verified"]:
        blockers.append("SINGLE_HOST_FAILOVER_NOT_VERIFIED")
    if resources["raid_status"] not in {"MIRRORED_PRESENT"}:
        blockers.append("MIRROR_INTEGRITY_NOT_VERIFIED")
    return {
        "schema_version":SCHEMA,"observed_at":datetime.now(timezone.utc).isoformat(),
        "mode":"OBSERVE","status":"DEGRADED" if findings else "HEALTHY_WITH_RECOVERY_GATES",
        "infrastructure_strategy":"INTEGRATE_EXISTING_EMPIREOS_NO_ADDITIONAL_SERVER",
        "observed_services":services,"service_findings":findings,
        "service_findings_count":len(findings),"resources":resources,
        "recovery_evidence_blockers":blockers,
        "database_credentials_accessed":False,"secrets_reported":False,
        "automatic_repair_actions":0,"new_runtime_created":False,
        "outbound_enabled":False,"payment_execution":False,
        "database_writes":False,"execution_authority":"NONE",
    }
