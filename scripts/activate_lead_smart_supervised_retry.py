#!/usr/bin/env python3
"""One-command, founder-controlled 10-20 minute Direct roofing pilot.

Default is read-only. Only --apply-founder-approved-window changes site call
admission. Requires a separately agreed buyer window; never changes Ringba,
sends traffic, edits legal disclosures or reports a payment.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from empire_os.lead_smart_site_handoff import (
    CAMPAIGN, NUMBER, CONFIG, LEDGER, HandoffHeld, _control, _write_atomic,
)
from scripts.disable_lead_smart_pilot_control import stop_control
from scripts.materialize_lead_smart_launch_readiness import compute_live_launch_readiness

ROOT = Path("/srv/empire_os")
PYTHON = ROOT / ".venv/bin/python"
ZONE = ZoneInfo("America/Chicago")


def window(start_local: str, minutes: int) -> tuple[datetime, datetime]:
    if type(minutes) is not int or not 10 <= minutes <= 20:
        raise ValueError("duration must be 10 through 20 minutes")
    try:
        parsed = datetime.fromisoformat(start_local)
    except ValueError as exc:
        raise ValueError("start must be YYYY-MM-DDTHH:MM Chicago time") from exc
    if parsed.tzinfo is not None:
        raise ValueError("use local Chicago time without an offset")
    start = parsed.replace(tzinfo=ZONE)
    end = start + timedelta(minutes=minutes)
    start_min = start.hour * 60 + start.minute
    end_min = end.hour * 60 + end.minute
    if (start.weekday() >= 5 or start.date() != end.date()
            or not 480 <= start_min < 1080
            or not 480 < end_min <= 1080):
        raise ValueError("weekday pilot must be fully within buyer's 8AM-6PM Chicago hours")
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


def revised_control(control: dict, start: datetime, end: datetime,
                    max_handoffs: int) -> dict:
    if (control.get("enabled") is not False
            or control.get("campaign_id") != CAMPAIGN
            or control.get("tracking_number") != NUMBER
            or control.get("stop_method") != "atomic_site_handoff_gate"):
        raise ValueError("recognized disabled pilot control required")
    if type(max_handoffs) is not int or not 1 <= max_handoffs <= 10000:
        raise ValueError("invalid maximum number of site handoffs")
    new = dict(control)
    new["starts_at"] = start.isoformat()
    new["ends_at"] = end.isoformat()
    new["max_site_handoffs"] = max_handoffs
    new["enabled"] = False
    return new


def _lock():
    lock = LEDGER.with_suffix(".lock")
    return lock.open("a+b")


def change_control(expected: dict, updated: dict) -> None:
    with _lock() as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        if json.loads(CONFIG.read_text()) != expected:
            raise RuntimeError("control changed concurrently")
        _write_atomic(CONFIG, updated)
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def refresh_coverage() -> None:
    for module in (
        "scripts.run_lead_smart_coverage_observer",
        "scripts.materialize_lead_smart_coverage_intelligence",
        "scripts.materialize_lead_smart_zip_gate",
    ):
        subprocess.run([str(PYTHON), "-B", "-m", module],
                       cwd=ROOT, stdout=subprocess.DEVNULL,
                       check=True, timeout=90)


def run(start_local: str, minutes: int, max_handoffs: int,
        apply: bool = False) -> dict:
    start, end = window(start_local, minutes)
    current = json.loads(CONFIG.read_text())
    candidate = revised_control(current, start, end, max_handoffs)
    now = datetime.now(timezone.utc)
    report = {
        "campaign": CAMPAIGN, "tracking_number": NUMBER,
        "starts_at": start.isoformat(), "ends_at": end.isoformat(),
        "duration_minutes": minutes, "max_site_handoffs": max_handoffs,
        "site_calls_enabled": False, "money_moved": False,
    }
    if not apply:
        return {**report, "status": "REVIEW_ONLY", "control_changed": False}
    # Operator action must happen near the agreed time, not the day before.
    if not (start <= now < start + timedelta(seconds=90)):
        raise RuntimeError("outside selected launch minute; control left OFF")
    _control({**candidate, "enabled": True}, now)
    refresh_coverage()
    now = datetime.now(timezone.utc)
    if not (start <= now < start + timedelta(seconds=90)
            and (end - now).total_seconds() >= 60):
        raise RuntimeError("window elapsed during coverage refresh; OFF")
    change_control(current, candidate)  # Stage the NEW window but keep OFF.
    timer_name = None
    try:
        readiness = compute_live_launch_readiness()
        blockers = readiness["blockers"]
        if blockers != ["pilot_stop_verified"]:
            raise RuntimeError("preflight held: " + json.dumps(blockers))
        # Stop is installed and verified BEFORE the switch can be enabled.
        seconds = int((end-datetime.now(timezone.utc)).total_seconds()) - 10
        if seconds < 50:
            raise RuntimeError("insufficient remaining window")
        timer_name = "empire-roofing-auto-stop-" + start.strftime("%Y%m%d%H%M%S")
        subprocess.run([
            "sudo", "-n", "systemd-run",
            "--unit="+timer_name,
            "--on-active="+str(seconds)+"s",
            "--timer-property=AccuracySec=1s",
            "--property=WorkingDirectory=/srv/empire_os",
            "--property=User=ubuntu",
            str(PYTHON), "-B", "-m",
            "scripts.disable_lead_smart_pilot_control", "--apply",
        ], cwd=ROOT, check=True, timeout=30)
        subprocess.run(["systemctl", "is-active", "--quiet", timer_name+".timer"],
                       check=True, timeout=10)
        enabled = dict(candidate)
        enabled["enabled"] = True
        _control(enabled, datetime.now(timezone.utc))
        change_control(candidate, enabled)
        ready = compute_live_launch_readiness()
        if ready["launch_ready"] is not True:
            raise RuntimeError("postactivation check held: "+json.dumps(ready["blockers"]))
        return {**report, "status": "LIVE_SITE_HANDOFF_ENABLED",
                "site_calls_enabled": True,
                "automatic_stop_timer": timer_name+".timer",
                "remaining_blockers": ready["blockers"]}
    except BaseException:
        # A created timer is independent and survives Ctrl+C; also stop now.
        stop_control(apply=True)
        # Restore the prior DISABLED window only if no concurrent change
        # happened; never roll another operator's work backward.
        try:
            change_control(candidate, current)
        except (RuntimeError, OSError, ValueError):
            pass
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-chicago", required=True,
                        help="YYYY-MM-DDTHH:MM in America/Chicago")
    parser.add_argument("--duration-minutes", type=int, default=15)
    parser.add_argument("--max-site-handoffs", type=int, default=5)
    parser.add_argument("--apply-founder-approved-window", action="store_true")
    a = parser.parse_args()
    try:
        result = run(a.start_chicago, a.duration_minutes,
                     a.max_site_handoffs, a.apply_founder_approved_window)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (ValueError, RuntimeError, HandoffHeld, OSError,
            subprocess.SubprocessError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "HELD", "site_calls_enabled": False,
                          "reason": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
