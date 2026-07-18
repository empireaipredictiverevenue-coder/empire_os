#!/usr/bin/env python3
"""Empire OS — REVENUE INVARIANT WATCHDOG (lean replacement for empire_coder).

Runs on the HOST. Every INTERVAL seconds it asserts the two
revenue-integrity invariants that, when violated, produced the
6-month 'simulated' charge bug + the double-insert UNIQUE crash:

  INV-1 (NO-SIM): zero si_charges rows with status='simulated'.
          Any such row is a revenue-integrity HOLE — fails immediately,
          no grace window. Charges must be 'open' (awaiting on-chain)
          or 'succeeded' (paid), never fake.

  INV-2 (FK cardinality): every si_ppc_invoices.charge_id maps to
          EXACTLY one si_charges row. !=1 means double-insert (dup
          charge rows) or orphan (invoice with no charge). Both corrupt
          the revenue ledger.

SQL runs INSIDE the empire-hub container via `incus exec` (needs the
live DB). On ANY violation: Telegram alert (MONEY-gated creds) + jsonl
log. Best-effort: a single failing probe never crashes the loop.

Usage:
  python3 revenue_invariant_check.py --once     # one check, exit code
  python3 revenue_invariant_check.py            # loop forever
"""
from __future__ import annotations
import json, os, sys, time, subprocess, urllib.request
from datetime import datetime, timezone

ROOT = "/root/empire_os"
CONTAINER = os.environ.get("EMPIRE_CONTAINER", "empire-hub")
LOG = os.environ.get("WATCHDOG_LOG", "/root/feedback/revenue_watchdog.jsonl")
TELEGRAM_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")
TELEGRAM_BOT = os.environ.get("TELEGRAM_BOT_TOKEN", "")
INTERVAL_S = int(os.environ.get("WATCHDOG_INTERVAL", "300"))


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def log_json(level: str, msg: str, **fields):
    e = {"ts": now_iso(), "level": level, "msg": msg, **fields}
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a") as f:
        f.write(json.dumps(e) + "\n")
    if level in ("ERROR", "WARN"):
        print(json.dumps(e), flush=True)


def tg_alert(text: str):
    if not (TELEGRAM_CHAT and TELEGRAM_BOT):
        return
    try:
        payload = json.dumps({
            "chat_id": TELEGRAM_CHAT,
            "text": text,
            "disable_web_page_preview": True,
        }).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{TELEGRAM_BOT}/sendMessage",
            data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=8):
            pass
    except Exception:
        pass


def incus_exec(script: str, timeout: int = 25) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["incus", "exec", CONTAINER, "--", "sh", "-c", script],
        capture_output=True, text=True, timeout=timeout)


def _sql_count(query: str) -> int:
    """Run a COUNT(*) query inside the container; return int or raise."""
    out = incus_exec(
        f"cd {ROOT} && python3 -c \""
        f"import sqlite3;c=sqlite3.connect('/root/empire_os/empire_os.db');"
        f"print(c.execute({query!r}).fetchone()[0])\"")
    return int((out.stdout or "0").strip() or 0)


def check_no_sim() -> list[str]:
    """INV-1: any 'simulated' charge = NO-SIM violation."""
    probs: list[str] = []
    try:
        n = _sql_count(
            "SELECT COUNT(*) FROM si_charges WHERE status='simulated'")
        if n > 0:
            probs.append(
                f"NO-SIM VIOLATION: {n} si_charges row(s) status='simulated' "
                f"(revenue-integrity hole — must be 'open'/'succeeded')")
    except Exception as e:
        probs.append(f"nosim_check_error:{e}")
    return probs


def check_fk_cardinality() -> list[str]:
    """INV-2: each invoice.charge_id -> exactly 1 si_charges row."""
    probs: list[str] = []
    try:
        n = _sql_count(
            "SELECT COUNT(*) FROM si_ppc_invoices i "
            "WHERE (SELECT COUNT(*) FROM si_charges c "
            "WHERE c.charge_id=i.charge_id) != 1")
        if n > 0:
            probs.append(
                f"FK CORRUPTION: {n} invoice(s) with !=1 si_charges row "
                f"(double-insert / orphan charge)")
    except Exception as e:
        probs.append(f"fk_check_error:{e}")
    return probs


def run_once() -> dict:
    probs = check_no_sim() + check_fk_cardinality()
    results = {
        "no_sim_probs": check_no_sim(),
        "fk_probs": check_fk_cardinality(),
        "ok": len(probs) == 0,
    }
    if probs:
        log_json("ERROR", "revenue_invariant_violation", probs=probs)
        tg_alert("⚠️ REVENUE WATCHDOG — invariant VIOLATED:\n" +
                 "\n".join(f"• {p}" for p in probs))
    else:
        log_json("OK", "revenue_invariants_hold")
    return results


def main():
    if "--once" in sys.argv:
        res = run_once()
        print(json.dumps(res, indent=2, default=str))
        sys.exit(0 if res["ok"] else 1)
    log_json("INFO", "watchdog_loop_start", interval_s=INTERVAL_S)
    while True:
        try:
            run_once()
        except Exception as e:
            log_json("ERROR", "watchdog_loop_crashed", err=str(e)[:300])
        time.sleep(INTERVAL_S)


if __name__ == "__main__":
    main()
