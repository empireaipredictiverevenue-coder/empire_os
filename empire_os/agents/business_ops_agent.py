"""
Business Operations Agent — meta-ops monitor across every revenue loop.

Read-only. Observes: outbox backlog/failures, inbox replies (real vs test/spam),
awaiting_payment real businesses, settlements, BSC USDT balance, funnel health.
Writes only its own digest files under /root/business_ops/. Never sends email,
never mutates DB, never moves money.

Runs on the empire-hub host container (host runtime, like lead-deliverer-agent).
"""
import json
import time
import os
import sqlite3
import urllib.request
from pathlib import Path
from datetime import datetime, timezone

sys_path = "/root/empire_os"
import sys
if sys_path not in sys.path:
    sys.path.insert(0, sys_path)

from empire_os.synthetic_agents import SyntheticAgent

HUB = "http://127.0.0.1:8081"
DB = "/root/empire_os/empire_os.db"
PORT = 9400  # /health for orchestrator
TICK_INTERVAL = 900  # 15 minutes
ROLE = "business_ops"
AGENT_DIR = Path(f"/root/{ROLE}")
AGENT_DIR.mkdir(parents=True, exist_ok=True)

# test/spam/auto-reply signatures to strip from "real replies".
# IMPORTANT: match on SPECIFIC spam/test signatures only — never on a
# public TLD (.com/.co.uk) or on generic business local-parts (info@,
# sales@, team@), or legitimate buyer replies would be mis-flagged as test.
TEST_MARKERS = (".test", "example-", "example.", "@b.com", "verify@",
                "mistersafelist.com", "splashpagesurfer.com", "mailer.gold",
                "surefireads.com", "demio.com", "websbestmarketing.com",
                "inertix.pro", "systeme.io", "traffix", "memberalert@",
                "noreply@", "no-reply@", "mailer-daemon", "googlemail.com",
                "britishhomesdirect.co.uk", "safelist", "trafficexchange",
                "credits@", "earn", "commissions",
                "unsubscribe", "postmaster@", "daemon@", "autorespond",
                "do-not-reply", "splashpage", "goldmailer", "mailsponsor",
                "listmail", "digest@", "alerts@bounce", "dsn@",
                "returnpath", "feedback@", "fbl@", "abuse@",
                "wowcher", "zavvi", "clarks", "just-eat",
                "thelostestate", "m.wowcher", "n.zavvi")


def _is_test(addr: str) -> bool:
    a = (addr or "").lower()
    return any(m in a for m in TEST_MARKERS)


def _now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class BusinessOpsAgent(SyntheticAgent):
    """Meta-ops monitor — observes every revenue loop, alerts on anomalies."""

    def observe(self) -> dict:
        state = {"ts": _now_iso()}
        # 1) outbox status
        try:
            c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
            c.execute("PRAGMA busy_timeout=30000")
            o = dict(c.execute(
                "select status, count(*) from si_outbox group by status").fetchall())
            state["outbox"] = {
                "total": sum(o.values()),
                "pending": o.get("pending", 0),
                "sent": o.get("sent", 0),
                "failed": o.get("failed", 0),
            }
            # new failed in last tick window (approx: status=failed, recent)
            recent_fail = c.execute(
                "select count(*) from si_outbox where status='failed' "
                "and created_at >= datetime('now','-15 minutes')").fetchone()[0]
            state["outbox"]["failed_recent_15m"] = recent_fail
            c.close()
        except Exception as e:
            state["outbox_error"] = str(e)

        # 2) inbox replies — real vs test/spam
        try:
            c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
            c.execute("PRAGMA busy_timeout=30000")
            rows = c.execute(
                "select id,from_email,subject,status,received_at from si_inbox "
                "order by id desc limit 200").fetchall()
            real = [r for r in rows if not _is_test(r[1])]
            new_real = [r for r in real if r[3] == "new"]
            state["inbox"] = {
                "total_rows": c.execute("select count(*) from si_inbox").fetchone()[0],
                "recent_200_real": len(real),
                "recent_200_real_new": len(new_real),
                "sample_real_new": [
                    {"from": r[1], "subject": (r[2] or "")[:80], "received": r[4]}
                    for r in new_real[:5]
                ],
            }
            c.close()
        except Exception as e:
            state["inbox_error"] = str(e)

        # 3) awaiting_payment real businesses
        try:
            c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
            c.execute("PRAGMA busy_timeout=30000")
            ap = c.execute(
                "select count(*) from si_subscription s join si_tenant t "
                "on s.tenant_id=t.id where s.status='awaiting_payment' "
                "and t.email is not null and t.email != ''").fetchone()[0]
            state["awaiting_payment_real"] = ap
            c.close()
        except Exception as e:
            state["awaiting_error"] = str(e)

        # 4) settlements (realized revenue) via hub
        try:
            r = urllib.request.urlopen(HUB + "/v1/revenue/summary", timeout=8)
            state["revenue"] = json.loads(r.read())
        except Exception as e:
            state["revenue_error"] = str(e)

        # 5) funnel health via hub
        try:
            r = urllib.request.urlopen(HUB + "/v1/funnel/counts", timeout=8)
            state["funnel"] = json.loads(r.read())
        except Exception as e:
            state["funnel_error"] = str(e)

        return state

    def reason(self, state: dict) -> dict:
        """Rule-based alerting (no LLM) — deterministic, always runs."""
        alerts = []
        ob = state.get("outbox", {})
        if ob.get("failed", 0) > 50:
            alerts.append({"sev": "HIGH", "loop": "outbox",
                           "msg": "Failed-send backlog = %d (threshold 50)" % ob["failed"]})
        if ob.get("pending", 0) > 500:
            alerts.append({"sev": "MED", "loop": "outbox",
                           "msg": "Pending email backlog = %d (threshold 500)" % ob["pending"]})
        if ob.get("failed_recent_15m", 0) > 10:
            alerts.append({"sev": "HIGH", "loop": "outbox",
                           "msg": "%d sends failed in last 15m — mail sender may be down" % ob["failed_recent_15m"]})
        ib = state.get("inbox", {})
        if ib.get("recent_200_real_new", 0) > 0:
            alerts.append({"sev": "INFO", "loop": "inbox",
                           "msg": "%d NEW real replies in last 200 inbox rows" % ib["recent_200_real_new"]})
        # test-data honesty flag
        tot = ib.get("total_rows", 0)
        real200 = ib.get("recent_200_real", 0)
        if tot > 0 and real200 == 0:
            alerts.append({"sev": "WARN", "loop": "inbox",
                           "msg": "Inbox = %d rows, ZERO real replies in recent 200 — all test/spam" % tot})
        ap = state.get("awaiting_payment_real", 0)
        if ap > 0:
            alerts.append({"sev": "MED", "loop": "payments",
                           "msg": "%d real businesses awaiting payment (uncollected pipeline)" % ap})
        return {"alerts": alerts, "summary": self._summarize(state, alerts)}

    def _summarize(self, state, alerts) -> str:
        ob = state.get("outbox", {})
        ib = state.get("inbox", {})
        ap = state.get("awaiting_payment_real", 0)
        n_alert = len(alerts)
        return ("loops: outbox pending=%s sent=%s failed=%s | inbox real_new=%s/%s "
                "total=%s | awaiting_pay=%s | alerts=%d" % (
                    ob.get("pending"), ob.get("sent"), ob.get("failed"),
                    ib.get("recent_200_real_new"), ib.get("recent_200_real"),
                    ib.get("total_rows"), ap, n_alert))

    def act(self, decision: str) -> dict:
        try:
            d = json.loads(decision) if isinstance(decision, str) else decision
        except Exception:
            d = {"alerts": [], "summary": str(decision)[:120]}
        digest = {"ts": _now_iso(), "state": self._last_state, "alerts": d.get("alerts", []),
                  "summary": d.get("summary", "")}
        # append to jsonl
        with (AGENT_DIR / "ops_digest.jsonl").open("a") as f:
            f.write(json.dumps(digest, default=str) + "\n")
        # latest snapshot
        with (AGENT_DIR / "latest.json").open("w") as f:
            json.dump(digest, f, default=str, indent=2)
        return {"summary": d.get("summary", ""), "alerts": len(d.get("alerts", []))}

    def tick(self) -> dict:
        self._last_state = self.observe()
        decision = self.reason(self._last_state)
        return self.act(decision)


if __name__ == "__main__":
    # health server thread
    from http.server import BaseHTTPRequestHandler, HTTPServer
    import threading

    agent = BusinessOpsAgent(
        name="business-ops",
        role=ROLE,
        disable_llm=True,  # rule-based, no Ollama dependency
        health_url="http://localhost:%d/health" % PORT,
    )

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{"status":"ok"}')
            else:
                self.send_response(404)
                self.end_headers()
        def log_message(self, *a):
            pass

    t = threading.Thread(target=lambda: HTTPServer(("0.0.0.0", PORT), H).serve_forever(), daemon=True)
    t.start()

    print("Business Ops agent starting — tick interval %ds, port %d" % (TICK_INTERVAL, PORT))
    consecutive_failures = 0
    while True:
        try:
            result = agent.tick()
            consecutive_failures = 0
            print(json.dumps({"summary": result.get("summary", ""), "alerts": result.get("alerts", 0)}))
        except Exception as e:
            consecutive_failures += 1
            backoff = min(60 * consecutive_failures, 600)
            print(json.dumps({"error": str(e), "backoff": backoff, "failures": consecutive_failures}))
            time.sleep(backoff)
            continue
        time.sleep(TICK_INTERVAL)
