"""Recover failed Texas source checks under ORIGINAL brokerage heartbeat lock.

This is a bounded retry helper invoked only by the existing source owner
during its normal cooldown. It does not create a timer or worker.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import json
import os
import tempfile
from typing import Callable, Mapping

ROOT = Path("/srv/empire_os")
STATE = Path("runtime/data_brokerage/texas_source_retry_latest.json")
SCHEMA = "empire.data_brokerage.texas_source_retry.v1"
RETRY_INTERVAL = timedelta(hours=1)
MIN_DELAY = timedelta(minutes=15)
MAX_BYTES = 2000

def _time(value: object) -> datetime | None:
    if not isinstance(value,str):
        return None
    try:
        ts=datetime.fromisoformat(value.replace("Z","+00:00"))
        return ts.astimezone(timezone.utc) if ts.utcoffset() is not None else None
    except (ValueError,OverflowError,TypeError):
        return None

def _checksum(data: dict) -> str:
    return sha256(json.dumps(data,sort_keys=True,separators=(",",":"),
                             allow_nan=False).encode()).hexdigest()

def _existing(root: Path) -> dict | None:
    p=root/STATE
    try:
        if p.is_symlink() or p.stat().st_mode & 0o077 or p.stat().st_size>MAX_BYTES:
            return None
        data=json.loads(p.read_text())
        digest=data.pop("integrity_sha256")
        if (data.get("schema_version")!=SCHEMA
            or data.get("mode")!="RESEARCH_ONLY"
            or data.get("execution_authority")!="none"
            or data.get("outreach_sent") is not False
            or data.get("customer_delivery_enabled") is not False
            or data.get("status") not in (
                "RETRY_CONFIRMED","RETRY_SOURCE_HELD")
            or not isinstance(digest,str) or _checksum(data)!=digest
            or not _time(data.get("attempted_at"))):
            return None
        return data
    except (OSError,ValueError,KeyError,TypeError):
        return None

def _save(root:Path, body:dict) -> None:
    destination=root/STATE
    if destination.is_symlink() or destination.parent.is_symlink():
        raise ValueError("UNTRUSTED_TEXAS_RETRY_PATH")
    destination.parent.mkdir(parents=True,exist_ok=True)
    os.chmod(destination.parent,0o700)
    content={**body,"integrity_sha256":_checksum(body)}
    fd,temporary=tempfile.mkstemp(prefix=".texas_source_retry_",dir=destination.parent)
    try:
        os.fchmod(fd,0o600)
        with os.fdopen(fd,"w") as f:
            json.dump(content,f,sort_keys=True,allow_nan=False)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary,destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)

def retry_in_original_owner(
    root: Path, *, now: datetime, previous:Mapping[str,object] | None,
    texas_runner:Callable | None=None,
) -> dict:
    """May be invoked only under original miner's existing exclusive lock.

    The caller proves it is inside the main source cooldown. This function
    holds when any source-clock/input/integrity requirement is missing.
    """
    root=Path(root).resolve()
    if root!=ROOT or now.utcoffset() is None:
        return {"status":"NONCANONICAL_NO_RETRY","network_requests":0}
    now=now.astimezone(timezone.utc)
    source_at=_time((previous or {}).get("observed_at"))
    next_due=_time((previous or {}).get("next_eligible_at"))
    if not source_at or not next_due or not source_at+MIN_DELAY<=now<next_due:
        return {"status":"NO_RETRY_OUTSIDE_COOLDOWN_WINDOW","network_requests":0}
    from empire_os.data_brokerage_texas_agent import load_state, run_texas_research
    texas=load_state(root,now=now)
    texas_at=_time((texas or {}).get("observed_at"))
    if texas_at and texas_at>=source_at:
        return {"status":"TEXAS_RESEARCH_CURRENT_WITH_ORIGINAL_OWNER","network_requests":0}
    previous_attempt=_existing(root)
    at=_time((previous_attempt or {}).get("attempted_at"))
    if (at and previous_attempt.get("source_cycle_at")==source_at.isoformat()
        and now-at<RETRY_INTERVAL):
        return {"status":"TEXAS_RETRY_COOLDOWN","network_requests":0,
                "next_retry_eligible":(at+RETRY_INTERVAL).isoformat()}
    status="RETRY_SOURCE_HELD"
    reason="UNKNOWN_SOURCE_HOLD"
    try:
        run=texas_runner or run_texas_research
        outcome=run(root,now=now,persist=True,
                    trigger="ORIGINAL_BROKERAGE_COOLDOWN_RETRY")
        if not isinstance(outcome,dict):
            raise ValueError("TEXAS_RETRY_INVALID_RESPONSE")
        updated=load_state(root,now=now)
        verified=(outcome.get("source_receipts_committed") is True
                  and updated is not None
                  and updated.get("execution_trigger")=="ORIGINAL_BROKERAGE_COOLDOWN_RETRY"
                  and _time(updated.get("observed_at"))==now
                  and outcome.get("outreach_sent") is False)
        if verified:
            status="RETRY_CONFIRMED"
            reason="PRIVATE_SOURCE_RECEIPT_MATCHED"
        else:
            reason=str(outcome.get("status") or "SOURCE_COMMIT_NOT_VERIFIED")[:85]
    except (OSError,ValueError,TypeError,KeyError,RuntimeError) as exc:
        reason=type(exc).__name__
    marker={
        "schema_version":SCHEMA,
        "mode":"RESEARCH_ONLY",
        "status":status,
        "reason_code":reason,
        "source_cycle_at":source_at.isoformat(),
        "attempted_at":now.isoformat(),
        "execution_authority":"none",
        "outreach_sent":False,
        "customer_delivery_enabled":False,
    }
    _save(root,marker)
    return {
        "status":status,
        "reason_code":reason,
        "network_requests":"BOUNDED_OFFICIAL_READ_ONLY",
        "source_receipts_committed":status=="RETRY_CONFIRMED",
        "execution_authority":"none",
        "outreach_sent":False,
    }
