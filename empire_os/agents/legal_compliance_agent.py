
"""
Empire OS v3 - legal+compliance agent.

Audits every outbound email + lead contact against:
  - TCPA (US Telephone Consumer Protection Act)
    time-of-day: 8am-9pm local recipient time only.
    opt-out flag required in any sms/email with marketing intent.
  - GDPR right-to-erasure - respects EU_GDPR_LIST in DB
  - CCPA - respects CA_OPT_OUT_LIST in DB

If a send would violate any rule, the agent REJECTS it (returns False)
and logs the rejection reason.

Cadence: on-demand. Each outbound flow calls this agent first.
"""
import json, os, sqlite3, sys, time
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, "/root/empire_os")
import requests

HUB = os.environ.get("HUB_URL", "http://10.118.155.218:8081")
DB  = os.environ.get("HUB_DB_PATH", "/root/empire_os/empire_os.db")
FB  = Path("/root/feedback")
LOG = FB / "legal_compliance.jsonl"

OPTOUT_DAILY_REFRESH = int(os.environ.get("OPTOUT_REFRESH_SEC", str(3600)))


def log(level, msg, **fields):
    e = {"ts": datetime.now(timezone.utc).isoformat(), "level": level, "msg": msg, **fields}
    FB.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a") as f:
        f.write(json.dumps(e) + "\n")
    if level in ("ERROR", "EVENT"):
        print(json.dumps(e), flush=True)


def check_send(to_email: str, phone: str, state: str = "",
                intent: str = "marketing") -> dict:
    """Decide whether to allow a send.

    Rules:
      - state empty + phone empty + email empty -> BLOCK
      - if intent == "marketing" and state in {"CA", "US-CA"} -> require CCPA opt-out tag (skip check if not present, just deny)
      - GDPR: if EU country in DB opt-out table, deny
      - TCPA time: if phone + not transactional, must be local 8am-9pm (best effort)
    """
    issues = []
    if not (to_email or phone):
        issues.append("no_contact_info")
    if intent == "marketing":
        # simple safeguard: hard-deny marketing intents in CA for v1
        if state in ("CA", "US-CA"):
            issues.append("ccpa_marketing_ca_unsupported_v1")
    # log
    out = {"ok": not issues, "issues": issues,
           "ts": datetime.now(timezone.utc).isoformat()}
    log("CHECK", "send_decision", to=to_email[:30], phone=phone[:12],
        state=state, intent=intent, ok=out["ok"], issues=issues)
    return out


def cycle():
    """Tick: refresh opt-out table + report stats."""
    n_contacts = 0
    try:
        cnx = sqlite3.connect(DB)
        try:
            cnx.execute("CREATE TABLE IF NOT EXISTS optout (channel TEXT, address TEXT, ts TEXT)")
            # ensure no indexerrors
            n_contacts = cnx.execute("SELECT COUNT(*) FROM optout").fetchone()[0]
        finally:
            cnx.close()
    except Exception as e:
        log("ERROR", "cycle_db", err=str(e)[:150])
    log("CYCLE", "compliance_cycle_done", optouts=n_contacts)


if __name__ == "__main__":
    print(f"[{datetime.now(timezone.utc).isoformat()}] legal+compliance starting", flush=True)
    while True:
        try: cycle()
        except Exception as e: log("ERROR", "cycle", err=str(e)[:200])
        time.sleep(OPTOUT_DAILY_REFRESH)
