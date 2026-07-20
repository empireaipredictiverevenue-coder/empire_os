#!/usr/bin/env python3
"""
Empire OS Cortex Health Watchdog
================================

Detects "truth regressions" in the cortex tick report
(/root/feedback/cortex_report.json) and fires a Telegram alert when any of
these failure modes are observed:

  (a) waste.waste contains text indicating waste hotspots/lanes
  (b) asi.error contains text
  (c) guard.status != 'healthy'
  (d) pillar_revenue.occupied_lanes == pillar_revenue.lanes  (full saturation
      is a regression — there should always be empty headroom)
  (e) leaks.settlements stays at 2 indefinitely (no new settlements for
      SETTLE_STALL_TICKS consecutive ticks)

Designed to run on the HOST every 5 min via systemd timer
(empire-cortex-health.timer). Telegram creds live on the host at
/root/.empire_secrets/telegram.env — NOT inside the container — so the watcher
must execute on the host.

Alert format honors MONEY_ONLY=1 (compact) but always includes which failure
mode(s) fired and the offending payload excerpt. Cooldown prevents alert spam
when the same mode keeps firing (default 30 min).

Usage:
  cortex_health_watchdog.py            # one tick
  cortex_health_watchdog.py --once     # one tick + explicit exit 0
  cortex_health_watchdog.py --dry-run  # detect but never send Telegram
  cortex_health_watchdog.py --reset    # clear cooldown + stall counters
  cortex_health_watchdog.py --status   # print last alert + stall state
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# ───────────────────────────── paths & config ──────────────────────────────

REPORT_PATH = Path("/root/feedback/cortex_report.json")
TELEGRAM_ENV = Path("/root/.empire_secrets/telegram.env")
STATE_PATH = Path("/root/empire_os/cortex_health_watchdog.state.json")
LOG_PATH = Path("/root/feedback/cortex_health_watchdog.log")

# 5-min timer + reasonable jitter → only fire after 3 consecutive ticks stuck at 2
SETTLE_STALL_TICKS = 3
# 30-min cooldown per failure mode (mode-keyed, so different modes can co-fire)
ALERT_COOLDOWN_SEC = 30 * 60
# Default MONEY_ONLY derived from env file
DEFAULT_MONEY_ONLY = True


# ───────────────────────────── helpers ──────────────────────────────────────


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _log(level: str, msg: str, **fields) -> None:
    entry = {"ts": _now(), "level": level, "msg": msg, **fields}
    line = json.dumps(entry, ensure_ascii=False)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a") as f:
        f.write(line + "\n")
    print(line, flush=True)


def _load_env(path: Path) -> dict[str, str]:
    """Parse a simple KEY=VALUE env file. Returns empty dict if missing."""
    if not path.exists():
        return {}
    out: dict[str, str] = {}
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def _tg_send(text: str, env: dict[str, str]) -> tuple[bool, str]:
    """Send a message to Telegram using the bot creds. Returns (ok, info)."""
    token = env.get("TELEGRAM_BOT_TOKEN", "")
    chat = env.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat:
        return False, "missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID"
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat,
        "text": text,
        "disable_web_page_preview": True,
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
            if data.get("ok"):
                return True, "sent"
            return False, f"api returned ok=false: {data}"
    except Exception as e:  # noqa: BLE001 — surface any HTTP error
        return False, f"http error: {e!r}"


def _money_only() -> bool:
    """MONEY_ONLY=1 → compact alerts. Honor the env file if present."""
    if not TELEGRAM_ENV.exists():
        return DEFAULT_MONEY_ONLY
    env = _load_env(TELEGRAM_ENV)
    val = env.get("TELEGRAM_MONEY_ONLY", env.get("MONEY_ONLY", "1")).lower()
    return val in ("1", "true", "yes", "on")


# ───────────────────────────── state ────────────────────────────────────────


def _load_state() -> dict:
    if not STATE_PATH.exists():
        return {"last_alerts": {}, "settle_stall_counter": 0, "last_settlements": None}
    try:
        return json.loads(STATE_PATH.read_text())
    except Exception:  # noqa: BLE001
        return {"last_alerts": {}, "settle_stall_counter": 0, "last_settlements": None}


def _save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2))
    tmp.replace(STATE_PATH)


# ───────────────────────────── detection ────────────────────────────────────


def _load_report() -> dict | None:
    if not REPORT_PATH.exists():
        return None
    try:
        return json.loads(REPORT_PATH.read_text())
    except Exception as e:  # noqa: BLE001
        _log("ERROR", "cortex_report.json unreadable", error=repr(e))
        return None


def detect(report: dict, state: dict) -> list[dict]:
    """
    Returns a list of fired failure-mode dicts:
       {"mode": "...", "detail": "..."}
    Settlement stall is computed via state (consecutive ticks).
    """
    fired: list[dict] = []

    # (a) waste.error contains text — cortex report nests error inside waste sometimes
    waste = report.get("waste") or {}
    waste_err = ""
    if isinstance(waste, dict):
        waste_err = str(waste.get("error") or "").strip()
    if waste_err:
        fired.append({"mode": "waste_error", "detail": waste_err[:200]})

    # Also: non-empty waste_indicators above a threshold counts as regression.
    # Some cortex reports embed `error` as a list of strings.
    waste_inner = waste.get("waste") if isinstance(waste, dict) else None
    if isinstance(waste_inner, dict):
        w_indicators = waste_inner.get("total_waste_indicators", 0) or 0
        w_lanes = waste_inner.get("waste_lanes") or []
        w_hotspots = waste_inner.get("waste_hotspots") or []
        if w_indicators and w_indicators > 5:
            fired.append({
                "mode": "waste_indicators_high",
                "detail": f"total_waste_indicators={w_indicators} lanes={len(w_lanes)} hotspots={len(w_hotspots)}",
            })
        if w_err := waste_inner.get("error"):
            fired.append({"mode": "waste_error_inner", "detail": str(w_err)[:200]})

    # (b) asi.error contains text
    asi = report.get("asi") or {}
    asi_err = ""
    if isinstance(asi, dict):
        asi_err = str(asi.get("error") or "").strip()
    if asi_err:
        fired.append({"mode": "asi_error", "detail": asi_err[:200]})

    # (c) guard.status != 'healthy'
    guard = report.get("guard") or {}
    if isinstance(guard, dict):
        g_status = str(guard.get("status") or "").strip()
        if g_status and g_status.lower() != "healthy":
            units_down = guard.get("units_down") or []
            fired.append({
                "mode": "guard_unhealthy",
                "detail": f"status={g_status!r} units_down={units_down}",
            })

    # (d) pillar_revenue.occupied_lanes == pillar_revenue.lanes (full saturation)
    rev = report.get("revenue") or report.get("pillar_revenue") or {}
    if isinstance(rev, dict):
        occ = rev.get("occupied_lanes")
        total = rev.get("lanes")
        if isinstance(occ, int) and isinstance(total, int) and total > 0 and occ == total:
            fired.append({
                "mode": "revenue_saturated",
                "detail": f"occupied_lanes={occ} == lanes={total}",
            })

    # (e) settlements stuck at 2 indefinitely — track via state
    leaks = report.get("leaks") or {}
    settlements = None
    if isinstance(leaks, dict):
        s = leaks.get("settlements")
        if isinstance(s, int):
            settlements = s

    if settlements is not None:
        prev_settle = state.get("last_settlements")
        # First observation seeds the counter
        if prev_settle is None:
            state["settle_stall_counter"] = 1
        elif settlements == prev_settle and settlements <= 2:
            state["settle_stall_counter"] = int(state.get("settle_stall_counter", 0)) + 1
        else:
            state["settle_stall_counter"] = 0
        state["last_settlements"] = settlements

        if settlements <= 2 and state["settle_stall_counter"] >= SETTLE_STALL_TICKS:
            fired.append({
                "mode": "settlements_stalled",
                "detail": f"settlements={settlements} stuck for {state['settle_stall_counter']} ticks",
            })

    return fired


# ───────────────────────────── alerting ─────────────────────────────────────


def _format_alert(modes: list[dict], report: dict, money_only: bool) -> str:
    ts = report.get("ts") or _now()
    n = len(modes)
    if money_only:
        # One-line, terse, MONEY_ONLY friendly
        short = "; ".join(m["mode"] for m in modes)
        return (
            f"⚠️ CORTEX REGRESSION x{n} @ {ts}\n"
            f"modes: {short}\n"
            f"detail: " + " | ".join(m["detail"][:80] for m in modes)
        )
    # Verbose — full mode list + key payload excerpt
    rev = report.get("revenue") or {}
    leaks = report.get("leaks") or {}
    body = [f"🚨 CORTEX REGRESSION ({n} mode{'s' if n != 1 else ''}) @ {ts}", ""]
    for m in modes:
        body.append(f"• [{m['mode']}] {m['detail']}")
    body.append("")
    body.append(
        f"revenue: occupied_lanes={rev.get('occupied_lanes')}/{rev.get('lanes')} "
        f"avg_seat={rev.get('avg_seat_price')}"
    )
    body.append(
        f"leaks: settlements={leaks.get('settlements')} charges={leaks.get('charges')} "
        f"uncollected_seats={leaks.get('uncollected_seats')}"
    )
    body.append(
        f"guard: status={report.get('guard', {}).get('status')} "
        f"asi.error={(report.get('asi', {}) or {}).get('error') or 'none'}"
    )
    return "\n".join(body)


def _cooldown_ok(state: dict, mode: str, now_ts: float) -> bool:
    last = state.get("last_alerts", {}).get(mode)
    if not isinstance(last, (int, float)):
        return True
    return (now_ts - float(last)) >= ALERT_COOLDOWN_SEC


def _send_alerts(fired: list[dict], report: dict, dry_run: bool) -> tuple[list[str], list[str]]:
    """Returns (sent_modes, skipped_cooldown_modes). Updates state["last_alerts"]."""
    if not fired:
        return [], []
    env = _load_env(TELEGRAM_ENV)
    money_only = _money_only()
    text = _format_alert(fired, report, money_only)
    now_ts = time.time()
    state = _load_state()
    sent: list[str] = []
    skipped: list[str] = []

    # Decide which modes pass cooldown
    to_fire = []
    for m in fired:
        if _cooldown_ok(state, m["mode"], now_ts):
            to_fire.append(m)
        else:
            skipped.append(m["mode"])

    if not to_fire:
        # Even if all in cooldown, refresh stall counter so we don't drift
        _save_state(state)
        return [], skipped

    if dry_run:
        _log("DRY", "would send telegram", text=text, modes=[m["mode"] for m in to_fire])
        return [m["mode"] for m in to_fire], skipped

    ok, info = _tg_send(text, env)
    _log("INFO" if ok else "ERROR", "telegram send", ok=ok, info=info,
         modes=[m["mode"] for m in to_fire])
    if ok:
        for m in to_fire:
            state.setdefault("last_alerts", {})[m["mode"]] = now_ts
            sent.append(m["mode"])
    _save_state(state)
    return sent, skipped


# ───────────────────────────── main ─────────────────────────────────────────


def run_once(dry_run: bool = False) -> int:
    report = _load_report()
    if report is None:
        _log("WARN", "no cortex_report.json — skipping")
        return 0

    state = _load_state()
    fired = detect(report, state)
    # Persist state even if no alert fires (we update settle stall counter)
    _save_state(state)

    if not fired:
        _log("OK", "cortex healthy", ts=report.get("ts"),
             occupied=report.get("revenue", {}).get("occupied_lanes"),
             total=report.get("revenue", {}).get("lanes"),
             settlements=report.get("leaks", {}).get("settlements"))
        return 0

    sent, skipped = _send_alerts(fired, report, dry_run=dry_run)
    _log("ALERT", "regression fired",
         modes_fired=[m["mode"] for m in fired],
         sent=sent,
         cooldown_skipped=skipped)
    # Always exit 0 — watchdog pattern; alerting failures must not flap systemd
    return 0


def show_status() -> int:
    state = _load_state()
    report = _load_report()
    print(json.dumps({
        "report_present": report is not None,
        "report_ts": report.get("ts") if report else None,
        "state": state,
        "settle_stall_threshold": SETTLE_STALL_TICKS,
        "alert_cooldown_sec": ALERT_COOLDOWN_SEC,
    }, indent=2, ensure_ascii=False))
    return 0


def reset_state() -> int:
    if STATE_PATH.exists():
        STATE_PATH.unlink()
    _log("INFO", "state reset")
    return 0


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="Empire OS cortex health watchdog")
    p.add_argument("--once", action="store_true", help="single tick (default behavior)")
    p.add_argument("--dry-run", action="store_true", help="detect but don't send telegram")
    p.add_argument("--reset", action="store_true", help="clear cooldown + stall counters")
    p.add_argument("--status", action="store_true", help="print state and exit")
    args = p.parse_args(argv)

    if args.reset:
        return reset_state()
    if args.status:
        return show_status()
    return run_once(dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
