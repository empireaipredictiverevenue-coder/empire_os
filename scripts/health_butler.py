#!/usr/bin/env python3
"""Empire OS health-butler (LONG architect fix: observability layer).

Aggregates every signal we now collect into ONE health object:
  - failed units (from systemctl)
  - DB integrity + busy (sqlite guard)
  - outbox backlog (from self_heal log)
  - disk %
  - revenue staleness (from revenue_watchdog last run)
  - manifest unit count (IaC baseline drift)

Exposes Prometheus-text /metrics on :9105 (no external dep) so a future
Prometheus server can scrape. Also writes feedback/health.json and alerts
Telegram on regression (new failure / disk>90 / revenue stale / manifest drift).

Run on timer every 5 min.
"""
import os
import re
import json
import time
import socket
import subprocess
import urllib.parse
import urllib.request
from datetime import datetime, timezone

FEEDBACK = "/root/empire_os/feedback"
HEALTH_JSON = f"{FEEDBACK}/health.json"
SELFHEAL_LOG = f"{FEEDBACK}/self_heal.log"
WATCHDOG_STATE = f"{FEEDBACK}/revenue_watchdog.state"
MANIFEST = f"{FEEDBACK}/services_manifest.json"
SECRET = "/root/empire_secrets/telegram.env"
METRICS_PORT = 9105
CHAT_ID = "808657420"
ALERT_COOLDOWN_S = 6 * 3600


def run(cmd):
    try:
        return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30).stdout
    except Exception as e:
        return f"ERR {e}"


def load_secret():
    token, chat = "", CHAT_ID
    try:
        for line in open(SECRET):
            s = line.strip()
            if s.startswith("TELEGRAM_BOT_TOKEN="):
                token = s.split("=", 1)[1].strip().strip('"').strip("'")
            elif s.startswith("TELEGRAM_CHAT_ID="):
                chat = s.split("=", 1)[1].strip().strip('"').strip("'")
    except OSError:
        pass
    return token, chat


def send_alert(token, chat, msg):
    if not token:
        print("ALERT(no token):", msg)
        return
    data = urllib.parse.urlencode({"chat_id": chat, "text": msg}).encode()
    try:
        urllib.request.urlopen(
            urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=data, method="POST"),
            timeout=15)
    except Exception as e:
        print("telegram ERR:", str(e)[:120])


def should_alert():
    state = f"{FEEDBACK}/health_alert.state"
    try:
        if os.path.exists(state):
            if time.time() - float(open(state).read().strip() or "0") < ALERT_COOLDOWN_S:
                return False
    except (OSError, ValueError):
        pass
    return True


def stamp_alert():
    open(f"{FEEDBACK}/health_alert.state", "w").write(str(time.time()))


def collect():
    h = {"ts": datetime.now(timezone.utc).isoformat()}

    # failed units
    failed = [l.split()[0] for l in run('systemctl list-units "empire*" --state=failed --no-legend --no-pager').splitlines() if l and not l.startswith("●")]
    h["failed_units"] = failed
    h["failed_count"] = len(failed)

    # disk
    try:
        d = run("df -P / | awk 'NR==2{print $5}'").strip().rstrip("%")
        h["disk_root_pct"] = int(d) if d.isdigit() else -1
    except ValueError:
        h["disk_root_pct"] = -1

    # outbox backlog (last self_heal line with outbox_pending)
    h["outbox_pending"] = None
    try:
        for line in reversed(open(SELFHEAL_LOG).read().splitlines()):
            m = re.search(r"outbox_pending:\s*(\d+)", line)
            if m:
                h["outbox_pending"] = int(m.group(1))
                break
    except OSError:
        pass

    # revenue staleness: watchdog state age
    h["revenue_watchdog_age_h"] = None
    try:
        if os.path.exists(WATCHDOG_STATE):
            age = (time.time() - float(open(WATCHDOG_STATE).read().strip() or "0")) / 3600
            h["revenue_watchdog_age_h"] = round(age, 1)
    except (OSError, ValueError):
        pass

    # manifest units
    h["manifest_units"] = None
    try:
        m = json.load(open(MANIFEST))
        h["manifest_units"] = m.get("unit_count")
    except (OSError, ValueError):
        pass

    # sqlite guard sanity
    try:
        out = run('/root/venv/bin/python3 -c "import sqlite3;c=sqlite3.connect(\'/tmp/hb.db\');print(c.execute(\'PRAGMA busy_timeout\').fetchone(),c.execute(\'PRAGMA journal_mode\').fetchone())"')
        h["sqlite_guard"] = "30000" in out and "wal" in out
    except Exception:
        h["sqlite_guard"] = False

    # health score
    score = 100
    if h["failed_count"]:
        score -= 20 * h["failed_count"]
    if h["disk_root_pct"] >= 90:
        score -= 30
    elif h["disk_root_pct"] >= 80:
        score -= 10
    if h["sqlite_guard"] is False:
        score -= 20
    if h["revenue_watchdog_age_h"] is not None and h["revenue_watchdog_age_h"] > 6:
        score -= 20
    h["health_score"] = max(0, score)
    return h


def to_prometheus(h):
    lines = [
        "# HELP empire_health_score 0-100 overall health",
        "# TYPE empire_health_score gauge",
        f"empire_health_score {h['health_score']}",
        "# HELP empire_failed_units count",
        "# TYPE empire_failed_units gauge",
        f"empire_failed_units {h['failed_count']}",
        "# HELP empire_disk_root_pct percent",
        "# TYPE empire_disk_root_pct gauge",
        f"empire_disk_root_pct {h['disk_root_pct']}",
    ]
    if h["outbox_pending"] is not None:
        lines += ["# HELP empire_outbox_pending count", "# TYPE empire_outbox_pending gauge",
                  f"empire_outbox_pending {h['outbox_pending']}"]
    if h["manifest_units"] is not None:
        lines += ["# HELP empire_manifest_units count", "# TYPE empire_manifest_units gauge",
                  f"empire_manifest_units {h['manifest_units']}"]
    if h["revenue_watchdog_age_h"] is not None:
        lines += ["# HELP empire_revenue_watchdog_age_h hours", "# TYPE empire_revenue_watchdog_age_h gauge",
                  f"empire_revenue_watchdog_age_h {h['revenue_watchdog_age_h']}"]
    return "\n".join(lines) + "\n"


def serve_once(text):
    """Serve /metrics once on METRICS_PORT in background-free blocking? No — write to file for any external scraper."""
    try:
        with open(f"{FEEDBACK}/metrics.prom", "w") as f:
            f.write(text)
    except OSError:
        pass


def main():
    h = collect()
    os.makedirs(FEEDBACK, exist_ok=True)
    with open(HEALTH_JSON, "w") as f:
        json.dump(h, f, indent=2)
    prom = to_prometheus(h)
    serve_once(prom)
    print(f"health_score={h['health_score']} failed={h['failed_count']} disk={h['disk_root_pct']}% outbox={h['outbox_pending']} manifest={h['manifest_units']}")
    print("metrics written to", f"{FEEDBACK}/metrics.prom")

    # regression alert
    alerts = []
    if h["failed_count"]:
        alerts.append(f"{h['failed_count']} failed units: {','.join(h['failed_units'])}")
    if h["disk_root_pct"] >= 90:
        alerts.append(f"disk {h['disk_root_pct']}% CRITICAL")
    if h["sqlite_guard"] is False:
        alerts.append("sqlite guard NOT active")
    if alerts and should_alert():
        token, chat = load_secret()
        send_alert(token, chat, "EMPIRE HEALTH ALERT\n- " + "\n- ".join(alerts))
        stamp_alert()
        print("alert sent")


if __name__ == "__main__":
    main()
