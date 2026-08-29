"""
Audit 6.1 / 6.2 / 6.3 — Security Monitor (SIEM mock) + Incident Response
MOCKED external: Splunk / Elastic Security / Threat intel feeds.
Real: local event store (jsonl), severity correlation, automated response
playbook stubs. All threat numbers are CONFIG constants (mocked), logic runs.
"""
import os
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from empire_os.security.pii_masking import mask_log

SIEM_PATH = Path("/root/empire_os/feedback/security_siem.jsonl")
SIEM_PATH.parent.mkdir(parents=True, exist_ok=True)

# ── MOCKED external thresholds (Audit 6.2) ──
BRUTE_FORCE_FAILS = 10        # >=10 failed logins -> alert
PRIV_ESC_PATTERNS = ["sudo", "chmod 777", "setuid"]
EXFIL_PATTERNS = ["dump", "select * from", "copy all"]
# MOCKED: AbuseIPDB / MaxMind reputation
BLOCKED_COUNTRIES = []        # geo-fence (empty = allow all in mock)
TRUSTED_IPS = set()


class SIEM:
    """Local security event store + correlation."""
    def __init__(self, path=SIEM_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def ingest(self, event: dict):
        event["ts"] = datetime.now(timezone.utc).isoformat()
        event["masked"] = mask_log(json.dumps(event, default=str))[:400]
        with open(self.path, "a") as f:
            f.write(json.dumps(event) + "\n")

    def recent(self, n=50):
        try:
            lines = self.path.read_text().splitlines()[-n:]
            return [json.loads(l) for l in lines]
        except Exception:
            return []


_siem = SIEM()


def record_event(kind, severity="INFO", **fields):
    _siem.ingest({"kind": kind, "severity": severity, **fields})
    if severity in ("CRITICAL", "HIGH"):
        _auto_respond(kind, fields)


class SecurityMonitor:
    def __init__(self):
        self.failed_logins = {}

    def note_failed_login(self, ip):
        n = self.failed_logins.get(ip, 0) + 1
        self.failed_logins[ip] = n
        if n >= BRUTE_FORCE_FAILS:
            record_event("brute_force", "CRITICAL", ip=ip, attempts=n)
            return "LOCK_ACCOUNT"
        return "OK"

    def note_priv_esc(self, cmd):
        if any(p in cmd for p in PRIV_ESC_PATTERNS):
            record_event("priv_esc", "HIGH", cmd=cmd[:120])
            return "ALERT"
        return "OK"

    def note_exfil(self, query):
        if any(p in query.lower() for p in EXFIL_PATTERNS):
            record_event("exfil", "CRITICAL", query=query[:120])
            return "ISOLATE"
        return "OK"


# ── Audit 6.3 Incident Response Automation (playbook stubs) ──
RESPONSE_PLAYBOOK = {
    "brute_force": "Lock account + alert security team (Level 2)",
    "ddos": "Activate WAF rules + raise rate limits (Level 2)",
    "data_breach": "Revoke credentials + notify users (Level 3)",
    "malware": "Isolate host + collect forensics (Level 3)",
    "unauthorized_access": "Revoke session + audit logs (Level 1)",
}


def _auto_respond(kind, fields):
    action = RESPONSE_PLAYBOOK.get(kind, "LOG_ONLY")
    _siem.ingest({"kind": "incident_response", "action": action,
                  "trigger": kind, "fields": fields})


if __name__ == "__main__":
    m = SecurityMonitor()
    for _ in range(11):
        m.note_failed_login("1.2.3.4")
    m.note_exfil("SELECT * FROM leads")
    print(json.dumps(_siem.recent(5), indent=2))
