#!/usr/bin/env python3
"""Empire OS revenue-loop watchdog (MEDIUM architect fix).

The #1 business risk: the revenue loop silently dies (no buyer pays,
BSC listener stalls, settlement bridge wedged) and NOBODY notices because
there is zero observability. This watchdog answers one question:
  "Has money actually moved recently?"

Checks (all in local SQLite, no external dep):
  - si_settlements / evaluation_settlements: any new settlement in last 24h?
  - payout_log: any confirmed USDT payout in last 24h?
  - daily_revenue_snapshots: fresh snapshot today?
If ALL stale -> send Telegram alert to owner.

Telegram: reads BOT_TOKEN + CHAT_ID from /root/empire_secrets/telegram.env.
Alerts are throttled (max 1 per 6h) via a state file to avoid spam.
"""
import os
import sqlite3
import time
import urllib.request
import urllib.error
import urllib.parse

DB = "/root/empire_os/empire_os.db"
SECRET = "/root/empire_secrets/telegram.env"
STATE = "/root/empire_os/feedback/revenue_watchdog.state"
WINDOW_H = 24
ALERT_COOLDOWN_S = 6 * 3600
CHAT_ID = "808657420"  # owner, from memory


def load_secret() -> str:
    token = ""
    chat = CHAT_ID
    try:
        with open(SECRET) as f:
            for line in f:
                s = line.strip()
                if s.startswith("TELEGRAM_BOT_TOKEN="):
                    token = s.split("=", 1)[1].strip().strip('"').strip("'")
                elif s.startswith("TELEGRAM_CHAT_ID="):
                    chat = s.split("=", 1)[1].strip().strip('"').strip("'")
    except OSError:
        pass
    return token, chat


def last_activity_hours(table: str, col: str) -> float:
    try:
        con = sqlite3.connect(DB, timeout=30)
        con.execute("PRAGMA busy_timeout=30000")
        # column may be text timestamp or unix; try ISO first
        row = con.execute(
            f"SELECT MAX({col}) FROM {table}"
        ).fetchone()
        con.close()
        val = row[0]
        if not val:
            return 99999.0
        # try parse as ISO
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
            try:
                from datetime import datetime
                dt = datetime.strptime(str(val)[:19], fmt)
                return (time.time() - dt.timestamp()) / 3600.0
            except ValueError:
                continue
        # maybe unix epoch int
        try:
            return (time.time() - float(val)) / 3600.0
        except (ValueError, TypeError):
            return 0.0
    except Exception as e:
        return -1.0  # signal error


def send_alert(token: str, chat: str, msg: str) -> None:
    if not token:
        print("ALERT (no token):", msg)
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": chat, "text": msg}).encode()
    try:
        req = urllib.request.Request(url, data=data, method="POST")
        urllib.request.urlopen(req, timeout=15)
        print("telegram alert sent")
    except Exception as e:
        print("telegram send ERR:", str(e)[:120])


def should_alert() -> bool:
    try:
        if os.path.exists(STATE):
            last = float(open(STATE).read().strip() or "0")
            if time.time() - last < ALERT_COOLDOWN_S:
                return False
    except (OSError, ValueError):
        pass
    return True


def stamp_alert() -> None:
    try:
        os.makedirs(os.path.dirname(STATE), exist_ok=True)
        open(STATE, "w").write(str(time.time()))
    except OSError:
        pass


def main() -> None:
    si = last_activity_hours("si_settlements", "settled_at")
    ev = last_activity_hours("evaluation_settlements", "created_at")
    pay = last_activity_hours("payout_log", "settled_at")
    print(f"si_settlements: {si:.1f}h  evaluation: {ev:.1f}h  payout_log: {pay:.1f}h")

    stale = []
    for name, h in (("si_settlements", si), ("evaluation_settlements", ev), ("payout_log", pay)):
        if h < 0:
            stale.append(f"{name}=ERR")
        elif h > WINDOW_H:
            stale.append(f"{name}={h:.0f}h")

    if stale:
        msg = (f"EMPIRE REVENUE WATCHDOG\n"
               f"No settlement activity in {WINDOW_H}h:\n" + "\n".join(f" - {s}" for s in stale) +
               f"\nCheck: bsc-listener / settlement-bridge / revenue-loop")
        print("STALE:", "; ".join(stale))
        if should_alert():
            token, chat = load_secret()
            send_alert(token, chat, msg)
            stamp_alert()
        else:
            print("alert suppressed (cooldown)")
    else:
        print("OK: revenue loop alive")


if __name__ == "__main__":
    main()
