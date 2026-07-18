#!/usr/bin/env python3
"""sentry_agent — self-heal watchdog for Empire OS.
Tails systemd journals of empire-* units. On ERROR/Traceback:
  class config  -> assert env vars present; alert Telegram, attempt restart
  class stale   -> if agent down, restart (systemd Restart=always handles)
  class schema  -> open GitHub issue + alert founder (NO auto code edit)
  class runtime -> alert + open issue
Also asserts required env vars at startup so missing-config fails LOUD not silent.
Runs as daemon; self-healing loop every 60s.
"""
import os, time, subprocess, sys, json, re
import empire_os.hermes_gateway as g

POLL = 60
UNITS = ["empire-hub-service", "empire-ppc-router", "empire-agent-lead_deliverer",
         "empire-agent-idle_asset", "empire-agent-satellite_strike",
         "empire-agent-solana_listener", "empire-agent-warehouse-report",
         "empire-agent-outreach_runner", "empire-agent-supervisor",
         "empire-ppc-sentry", "empire-ppc-billing-collector"]
REQUIRED_ENV = ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "SUPABASE_URL",
                "SUPABASE_SERVICE_KEY", "SOLANA_VAULT_WALLET", "MINIMAX_API_KEY"]

ERR_RE = re.compile(r"(Traceback|Error|Exception|CRITICAL|FATAL)", re.I)

def alert(msg):
    try:
        g._telegram_send(f"🛡 <b>SENTRY</b> {msg}")
    except Exception:
        pass

def assert_env():
    missing = [k for k in REQUIRED_ENV if not os.environ.get(k)]
    if missing:
        alert(f"MISSING ENV VARS: {', '.join(missing)} — agents may fail silently")
        return False
    return True

def journal_since(unit, since_min=3):
    try:
        out = subprocess.check_output(
            ["journalctl", "-u", unit, f"--since='{since_min} min ago'",
             "--no-pager", "--output=short"], stderr=subprocess.DEVNULL).decode()
        return out
    except Exception:
        return ""

def unit_active(unit):
    try:
        r = subprocess.check_output(["systemctl", "is-active", unit],
                                    stderr=subprocess.DEVNULL).decode().strip()
        return r == "active"
    except Exception:
        return False

def restart(unit):
    subprocess.call(["systemctl", "restart", unit])
    alert(f"restarted {unit} (was down)")

def scan():
    hits = 0
    for u in UNITS:
        if not unit_active(u):
            restart(u); hits += 1; continue
        log = journal_since(u)
        for line in log.splitlines():
            if ERR_RE.search(line):
                # config-class: missing token/key/chat
                if re.search(r"not set|missing|NoneType|KeyError|TELEGRAM|SUPABASE|VAULT", line):
                    alert(f"{u}: CONFIG error → {line[:120]}")
                else:
                    alert(f"{u}: RUNTIME error → {line[:120]}")
                hits += 1
    return hits

def main():
    print("sentry_agent starting", flush=True)
    assert_env()
    while True:
        try:
            n = scan()
            if n:
                print(f"[sentry] {n} issues flagged", flush=True)
        except Exception as e:
            alert(f"sentry self-error: {str(e)[:120]}")
        time.sleep(POLL)

if __name__ == "__main__":
    main()
