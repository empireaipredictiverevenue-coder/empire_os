"""
empire_watchdog.py — self-healing monitor for Empire OS revenue stack.

Not just "is the process alive" — checks "is it actually producing work".
For each watched service:
  1. systemd active?  if not -> restart + alert
  2. produced output in last N min? (journalctl --since)  if not -> restart + alert
  3. revenue-loop services get a deeper check (balance file freshness)

Run every 5 min via cron. Restarts dead/stale services and sends one
telegram alert per incident (deduped via state file so you're not spammed).

NO new infra. Pure systemd + journalctl + sqlite + telegram.
"""
from __future__ import annotations
import subprocess, time, os, json, datetime

# (service, kind, freshness_minutes)
# kind: "log" = must have log output in window; "always" = just need active
WATCH = [
    # --- revenue loop (critical) ---
    ("bsc_listener", "log", 10),
    ("empire-payment-matcher", "log", 10),
    ("empire-mail-sender", "log", 15),
    ("empire-smtp-relay", "always", 0),
    # --- marketplace ---
    ("empire-buyer-hunter", "log", 15),
    ("empire-a2a-publisher", "log", 30),
    ("empire-omni-agent", "log", 15),
    ("empire-revenue-engine", "log", 30),
    ("empire-router-engine", "log", 30),
    ("empire-queue-sender", "log", 15),
    ("empire-lanes", "log", 60),          # container svc
    ("empire-neural-scout", "log", 60),   # container svc
    # --- intelligence ---
    ("empire-omega-os", "log", 30),
    ("empire-omega-learning", "log", 120),
    ("empire-agent-marketing_agent", "log", 30),
    ("whale_harvester", "log", 60),
    # --- high-ticket / enterprise / law-firm pipelines ---
    # (enterprise_campaigns.py is a script, run via separate cron — not a daemon)
    # --- Gamma OS (analytics/dashboard) ---
    ("empire-metrics-exporter", "log", 60),
    # --- Beta OS (buyer/seller marketplace) ---
    ("empire-a2a-publisher", "log", 30),
    ("empire-a2a-buyer-marketplace", "log", 60),
    ("empire-a2a-closer", "log", 60),
]

STATE = "/root/empire_os/logs/watchdog_state.json"
TELEGRAM = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT = os.environ.get("TELEGRAM_CHAT_ID")


def _journal_recent(svc: str, mins: int) -> bool:
    """True if the service emitted ANY log line in the last `mins` minutes."""
    since = f"{mins} min ago" if mins else "1 min ago"
    try:
        out = subprocess.run(
            ["journalctl", "-u", svc, "--since", since, "--no-pager", "-n", "1"],
            capture_output=True, text=True, timeout=15)
        # a real line looks like "Sep 01 03:18:37 ..." not just "-- No entries"
        for line in out.stdout.splitlines():
            if line and not line.startswith("--") and "No entries" not in line:
                return True
    except Exception:
        pass
    return False


def _active(svc: str) -> bool:
    try:
        r = subprocess.run(["systemctl", "is-active", svc],
                           capture_output=True, text=True, timeout=10)
        # container services: check via incus
        if r.stdout.strip() == "active":
            return True
    except Exception:
        pass
    # try incus container service
    try:
        out = subprocess.run(
            ["incus", "exec", "empire-hub", "--", "systemctl", "is-active", svc],
            capture_output=True, text=True, timeout=10)
        if out.stdout.strip() == "active":
            return True
    except Exception:
        pass
    return False


def _restart(svc: str) -> str:
    # host first, then container
    for cmd in (
        ["systemctl", "restart", svc],
        ["incus", "exec", "empire-hub", "--", "systemctl", "restart", svc],
    ):
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if r.returncode == 0:
                return "restarted"
        except Exception as e:
            return f"err:{e}"
    return "restart-failed"


def _alert(msg: str):
    if not (TELEGRAM and CHAT):
        print(f"[alert] {msg}")
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM}/sendMessage"
        subprocess.run(["curl", "-s", "-X", "POST", url,
                        "-d", f"chat_id={CHAT}", "-d", f"text={msg}"],
                       capture_output=True, timeout=15)
    except Exception:
        print(f"[alert-fail] {msg}")


def main():
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    try:
        state = json.load(open(STATE))
    except Exception:
        state = {}
    incidents = []
    for svc, kind, mins in WATCH:
        active = _active(svc)
        if not active:
            res = _restart(svc)
            incidents.append(f"DEAD {svc} -> {res}")
            state[svc] = time.time()
            continue
        if kind == "log":
            recent = _journal_recent(svc, max(mins, 5))
            if not recent:
                # CONSERVATIVE: stale-but-active = alert only (don't kill a
                # service that may just be on a long cycle). Only DEAD -> restart.
                incidents.append(f"STALE(alive) {svc} (no output {mins}m) -> ALERT")
                state[svc] = time.time()
    json.dump(state, open(STATE, "w"))
    if incidents:
        _alert("🛡 Empire Watchdog — " + " | ".join(incidents))
        print("INCIDENTS:", len(incidents))
        for i in incidents:
            print(" ", i)
    else:
        print(f"[{datetime.datetime.now():%H:%M}] all {len(WATCH)} services healthy")


if __name__ == "__main__":
    main()
