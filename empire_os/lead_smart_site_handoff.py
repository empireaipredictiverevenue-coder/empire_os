"""First-party, bounded Lead Smart SITE HANDOFF admission.

Counts on-site dial handoffs, not completed Ringba calls. No timers, new DB,
network calls, personal data persistence, or unilateral revenue authority.
Missing/invalid/stale evidence always prevents the handoff.
"""
from __future__ import annotations

import fcntl
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from zoneinfo import ZoneInfo

CAMPAIGN = "CA8278ed3f26e9495b881fe3833174d007"
NUMBER = "+18883579305"
SCHEMA = "empire.lead_smart.site_handoff_control.v1"
LEDGER_SCHEMA = "empire.lead_smart.site_handoff_ledger.v1"
ROOT = Path("/srv/empire_os/runtime/revenue/lead_smart/pilot")
CONFIG = ROOT / "approved_control.json"
LEDGER = ROOT / "site_handoffs.json"


class HandoffHeld(Exception):
    """Return a generic unavailable response; never expose private reasons."""


def _moment(value: Any) -> datetime:
    if not isinstance(value, str):
        raise HandoffHeld()
    try:
        when = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HandoffHeld() from exc
    if when.tzinfo is None:
        raise HandoffHeld()
    return when.astimezone(timezone.utc)


def _json(path: Path) -> dict:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise HandoffHeld() from exc
    if not isinstance(obj, dict):
        raise HandoffHeld()
    return obj


def _control(control: Mapping[str, Any], now: datetime) -> tuple[str, datetime]:
    if (
        control.get("schema_version") != SCHEMA
        or control.get("enabled") is not True
        or control.get("campaign_id") != CAMPAIGN
        or control.get("tracking_number") != NUMBER
        or type(control.get("max_site_handoffs")) is not int
        or control["max_site_handoffs"] != 5
        or control.get("stop_method") != "atomic_site_handoff_gate"
        or not isinstance(control.get("monitoring_owner"), str)
        or len(control["monitoring_owner"].strip()) < 3
        # A disabled-template placeholder is not a person assigned to monitor
        # the release. Simply flipping enabled must never make it valid.
        or control["monitoring_owner"].strip().upper().startswith((
            "PENDING", "UNASSIGNED", "TBD", "PLACEHOLDER", "TO_BE_ASSIGNED",
        ))
        or not isinstance(control.get("founder_authority_ref"), str)
        or not control["founder_authority_ref"].strip()
    ):
        raise HandoffHeld()
    start = _moment(control.get("starts_at"))
    end = _moment(control.get("ends_at"))
    if not (0 < (end-start).total_seconds() <= 7200 and start <= now < end):
        raise HandoffHeld()
    # The buyer's GENERAL available hours are wider. The first supervised
    # revenue pilot is deliberately narrower: Chicago weekdays 10:00-12:00.
    # Exact start/end must BOTH lie inside that pilot window, even if a
    # founder/config writer accidentally chooses a weekend or a longer slot.
    chicago = ZoneInfo("America/Chicago")
    local_start = start.astimezone(chicago)
    local_end = end.astimezone(chicago)
    if (local_start.weekday() >= 5
            or local_start.date() != local_end.date()
            or not 600 <= local_start.hour * 60 + local_start.minute < 720
            or not 600 < local_end.hour * 60 + local_end.minute <= 720):
        raise HandoffHeld()
    # Deliberately bound the ledger to the selected window.
    return f"{CAMPAIGN}:{start.isoformat()}:{end.isoformat()}", end


def _readiness(readiness: Mapping[str, Any], now: datetime) -> None:
    gates = readiness.get("gates")
    if (
        readiness.get("schema_version") != "empire.lead_smart.launch_readiness.v1"
        or readiness.get("mode") != "READY"
        or readiness.get("launch_ready") is not True
        or readiness.get("call_cta_enabled") is not True
        or readiness.get("execution_authority") != "LIVE_TRAFFIC"
        or readiness.get("buyer_window_open_now") is not True
        or not isinstance(gates, dict)
        or not gates
        or any(value is not True for value in gates.values())
    ):
        raise HandoffHeld()
    evaluated = _moment((readiness.get("operating_hours") or {}).get("evaluated_at"))
    if not (0 <= (now-evaluated).total_seconds() <= 60):
        raise HandoffHeld()


def _write_atomic(path: Path, payload: dict) -> None:
    # Ledger contains only a count and selected window; no ZIP, ANI or IP.
    data = (json.dumps(payload, sort_keys=True, indent=2) + "\n").encode()
    fd, temporary = tempfile.mkstemp(prefix=".handoff-", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def chicago_buyer_hours_open(now: datetime) -> bool:
    if now.tzinfo is None:
        return False
    local = now.astimezone(ZoneInfo("America/Chicago"))
    start, end = (8, 18) if local.weekday() < 5 else (10, 16)
    minutes = local.hour * 60 + local.minute
    return start * 60 <= minutes < end * 60


def site_handoff_available(
    zip_code: str, *, config_path: Path = CONFIG,
    ledger_path: Path = LEDGER, readiness: Mapping[str, Any],
    eligible_zip: bool, now: datetime | None = None,
) -> bool:
    try:
        now = now or datetime.now(timezone.utc)
        if now.tzinfo is None:
            return False
        now = now.astimezone(timezone.utc)
        if not isinstance(zip_code, str) or not re.fullmatch(r"[0-9]{5}", zip_code):
            return False
        if eligible_zip is not True or not chicago_buyer_hours_open(now):
            return False
        _readiness(readiness, now)
        window, _ = _control(_json(config_path), now)
        state = _json(ledger_path) if ledger_path.exists() else None
        if state is None:
            return True
        return (state.get("schema_version") == LEDGER_SCHEMA
                and state.get("window") == window
                and type(state.get("site_handoffs")) is int
                and 0 <= state["site_handoffs"] < 5)
    except (HandoffHeld, OSError, TypeError, ValueError):
        return False


def reserve_site_handoff(
    zip_code: str, *, config_path: Path = CONFIG,
    ledger_path: Path = LEDGER, readiness: Mapping[str, Any],
    eligible_zip: bool, now: datetime | None = None,
) -> str:
    now = (now or datetime.now(timezone.utc))
    if now.tzinfo is None:
        raise HandoffHeld()
    now = now.astimezone(timezone.utc)
    if not site_handoff_available(
        zip_code, config_path=config_path, ledger_path=ledger_path,
        readiness=readiness, eligible_zip=eligible_zip, now=now,
    ):
        raise HandoffHeld()
    window, _ = _control(_json(config_path), now)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    lock = ledger_path.with_suffix(".lock")
    with lock.open("a+b") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        # Revalidate with the exclusive lock; no sixth concurrent handoff.
        if not site_handoff_available(
            zip_code, config_path=config_path, ledger_path=ledger_path,
            readiness=readiness, eligible_zip=eligible_zip, now=now,
        ):
            raise HandoffHeld()
        existing = _json(ledger_path) if ledger_path.exists() else {
            "schema_version": LEDGER_SCHEMA, "window": window, "site_handoffs": 0,
        }
        existing["site_handoffs"] += 1
        _write_atomic(ledger_path, existing)
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    return "tel:" + NUMBER



def verified_site_handoff_control(
    *, config_path: Path = CONFIG,
    ledger_path: Path = LEDGER,
    now: datetime | None = None,
) -> bool:
    """Live read of the real, bounded site handoff switch, not a claimed flag.

    A configured receipt is necessary but alone does not constitute privacy,
    original-ANI, buyer-route, publication or settlement proof.
    """
    try:
        clock = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        window, _ = _control(_json(config_path), clock)
        if not ledger_path.exists():
            return True
        ledger = _json(ledger_path)
        return (
            ledger.get("schema_version") == LEDGER_SCHEMA
            and ledger.get("window") == window
            and type(ledger.get("site_handoffs")) is int
            and 0 <= ledger["site_handoffs"] < 5
        )
    except (HandoffHeld, OSError, AttributeError, TypeError, ValueError):
        return False
