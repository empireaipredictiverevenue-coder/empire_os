"""
Data Analysis Agent — purpose-built pipeline analytics.

Why a dedicated agent (vs reusing scout/engineering):
  - No second-guessing: this agent owns the funnel data layer
  - Numerical, not strategic: outputs numbers, not opinions
  - Read-only: never mutates the pipeline; only reads si_* tables
  - Reproducible: every cycle dumps a deterministic JSON snapshot

Inputs (observe):
  - si_prospect_consent  — opted-in prospects
  - si_funnel_event      — state transitions
  - si_settlements       — paid deals (currently empty in this repo)
  - /root/feedback/*.jsonl — daily agent activity logs

Outputs (act):
  - /root/data_analysis/snapshot.json      — latest numeric snapshot
  - /root/data_analysis/history.jsonl      — append-only time series
  - /root/feedback/data_analysis.jsonl     — alert feed (anomalies)

Cycle: 10 min. Alerts via hermes-gateway when anomaly detected.
"""
from __future__ import annotations
import json
import os
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, "/root/empire_os")

from empire_os.agent_core import OllamaClient
from empire_os.synthetic_agents import SyntheticAgent
from empire_os.predictive import predict_revenue

ROLE_DIR = Path("/root/data_analysis")
ROLE_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_PATH = ROLE_DIR / "snapshot.json"
HISTORY_PATH = ROLE_DIR / "history.jsonl"
TICK_INTERVAL = 600  # 10 min

DB_PATH = os.environ.get(
    "DB_PATH", "/root/empire_os/empire_os.db")
HERMES_GATEWAY_URL = os.environ.get(
    "HERMES_GATEWAY_URL", "http://10.118.155.156:9100")
PROMPTS_DIR = Path("/root/empire_os/empire_os/data/prompts")
SYSTEM_PROMPT = (PROMPTS_DIR / "data_analysis.txt").read_text() \
    if (PROMPTS_DIR / "data_analysis.txt").exists() else \
    "You are a data analysis expert. Output JSON only."


def sh(cmd, timeout=30):
    import subprocess
    try:
        return subprocess.run(cmd, shell=True, capture_output=True,
                              text=True, timeout=timeout)
    except Exception as e:
        return type("R", (), {"returncode": -1, "stdout": "",
                              "stderr": str(e)})()


class DataAnalysisAgent(SyntheticAgent):
    """Pipeline analytics. Owns si_* table reads. No mutations."""

    def _db_query(self, sql: str, params: tuple = ()) -> list[dict]:
        try:
            cnx = sqlite3.connect(DB_PATH)
            cnx.row_factory = sqlite3.Row
            rows = [dict(r) for r in cnx.execute(sql, params).fetchall()]
            cnx.close()
            return rows
        except Exception as e:
            return [{"_error": str(e)[:200]}]

    def observe(self) -> dict:
        # Funnel: state distribution
        by_state = self._db_query(
            "SELECT to_state, count(*) c FROM si_funnel_event "
            "GROUP BY to_state")
        # Per-day throughput
        daily = self._db_query(
            "SELECT substr(occurred_at,1,10) day, count(*) c "
            "FROM si_funnel_event GROUP BY day ORDER BY day DESC LIMIT 14")
        # Per-actor activity
        actors = self._db_query(
            "SELECT actor, count(*) c FROM si_funnel_event "
            "GROUP BY actor ORDER BY c DESC LIMIT 10")
        # Consent table
        consent_total = self._db_query(
            "SELECT count(*) c FROM si_prospect_consent")[0].get("c", 0)
        # Settlements
        settlements_total = self._db_query(
            "SELECT count(*) c FROM si_settlements")[0].get("c", 0)
        # Recent log activity
        log_dir = Path("/root/feedback")
        recent_log_files = 0
        log_errors_5min = 0
        if log_dir.exists():
            cutoff = time.time() - 300
            for f in log_dir.glob("*.jsonl"):
                try:
                    if f.stat().st_mtime > cutoff:
                        recent_log_files += 1
                except OSError:
                    continue
                try:
                    with f.open() as fh:
                        for ln in fh:
                            try:
                                if '"level": "ERROR"' in ln:
                                    log_errors_5min += 1
                            except Exception:
                                pass
                except Exception:
                    pass
        return {
            "ts": datetime.now(timezone.utc).isoformat(),
            "by_state": {r["to_state"]: r["c"] for r in by_state
                         if "to_state" in r},
            "daily_throughput": {r["day"]: r["c"] for r in daily
                                 if "day" in r},
            "top_actors": {r["actor"]: r["c"] for r in actors
                           if "actor" in r},
            "consent_total": consent_total,
            "settlements_total": settlements_total,
            "recent_log_files_5min": recent_log_files,
            "log_errors_5min": log_errors_5min,
        }

    def reason(self, state: dict) -> str:
        # Deterministic: if anomalies -> page; else -> no-op
        anomalies = []
        if state["log_errors_5min"] > 20:
            anomalies.append(f"{state['log_errors_5min']} ERROR events in 5m")
        if state["consent_total"] > 0 and state["settlements_total"] == 0:
            anomalies.append(
                f"{state['consent_total']} consents, 0 settlements")
        daily = state["daily_throughput"]
        if daily:
            recent_days = list(daily.values())[:3]
            if recent_days and all(v == 0 for v in recent_days):
                anomalies.append("zero funnel events for last 3 days")
        if not anomalies:
            return json.dumps({
                "action": "snapshot",
                "anomalies": [],
                "summary": "no anomalies",
            })
        # Anomalies -> LLM decides severity + recommended action
        prompt = json.dumps(state, indent=2)[:3000]
        try:
            res = self.llm.chat(
                messages=[{"role": "user",
                           "content": f"Analyze these pipeline metrics and "
                                      f"classify each anomaly. JSON: "
                                      f"{{anomalies: [{{issue, severity, "
                                      f"recommendation}}]}}"}],
                system=SYSTEM_PROMPT[:1500],
                temperature=0.2,
                format="json",
            )
            return res if isinstance(res, str) else json.dumps(res)
        except Exception:
            return json.dumps({
                "action": "alert",
                "anomalies": [{"issue": a, "severity": "warn",
                               "recommendation": "investigate"} for a in anomalies],
            })

    def act(self, decision: str) -> dict:
        try:
            d = json.loads(decision)
        except Exception:
            d = {"action": "snapshot"}

        # Compute predictive revenue (the formula the user wants wired in)
        revenue_projection = self._project_revenue()

        snapshot = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "cycle": self.context.cycle,
            "decision": d,
            "snapshot_ts": self.context.last_result,
            "revenue_projection": revenue_projection,
        }
        # Re-run observe to embed latest numbers
        snapshot["metrics"] = self.observe()
        # Save snapshot + history
        SNAPSHOT_PATH.write_text(json.dumps(snapshot, indent=2, default=str))
        with HISTORY_PATH.open("a") as f:
            f.write(json.dumps(snapshot, default=str) + "\n")

        # Alert if anomalies present
        if d.get("anomalies"):
            try:
                import requests
                body = json.dumps(d["anomalies"], indent=2)[:1800]
                requests.post(
                    f"{HERMES_GATEWAY_URL}/v1/notify/alert",
                    json={"title": f"data-analysis: "
                                  f"{len(d['anomalies'])} anomaly(s)",
                          "body": body,
                          "severity": "high",
                          "source": "data-analysis-agent"},
                    timeout=5)
            except Exception as e:
                snapshot["alert_emit_error"] = str(e)[:200]

        # Alert on MRR drop > 10% vs previous cycle
        prev_mrr = self._last_predicted_mrr()
        new_mrr = revenue_projection.get("total_predicted_mrr", 0)
        if prev_mrr and new_mrr and prev_mrr > 100:
            change_pct = (new_mrr - prev_mrr) / prev_mrr * 100
            if change_pct < -10:
                try:
                    import requests
                    requests.post(
                        f"{HERMES_GATEWAY_URL}/v1/notify/alert",
                        json={"title": f"data-analysis: MRR {change_pct:.1f}%",
                              "body": (f"prev=${prev_mrr:.0f} "
                                       f"new=${new_mrr:.0f}"),
                              "severity": "high",
                              "source": "data-analysis-agent"},
                        timeout=5)
                except Exception:
                    pass

        snapshot["summary"] = (
            f"snapshot saved; anomalies={len(d.get('anomalies', []))}; "
            f"predicted_mrr=${new_mrr:.0f}")
        return snapshot

    def _project_revenue(self) -> dict:
        """Run predict_revenue() against current DB state."""
        try:
            cnx = sqlite3.connect(DB_PATH)
            cnx.row_factory = sqlite3.Row
            # Count total leads (proxy = funnel events touching discovered)
            leads_total = cnx.execute(
                "SELECT count(*) c FROM si_funnel_event "
                "WHERE to_state = 'discovered'").fetchone()["c"]
            # Lane count: distinct niche from si_funnel_event.
            # Notes are key=value plain text (e.g. "niche=roofing source=test")
            # so we parse them with a simple regex.
            from collections import defaultdict
            import re as _re
            c = defaultdict(int)
            for r in cnx.execute(
                "SELECT notes FROM si_funnel_event WHERE notes IS NOT NULL"
            ).fetchall():
                m = _re.search(r"\bniche=([^\s,;]+)", r["notes"] or "")
                if m:
                    c[m.group(1).lower().strip()] += 1
            cnx.close()
            lane_count = max(len(c), 1)
            occupied = len([n for n, v in c.items() if v > 0])
            # Funnel by state
            cnx = sqlite3.connect(DB_PATH)
            cnx.row_factory = sqlite3.Row
            state_rows = cnx.execute(
                "SELECT to_state, count(*) c FROM si_funnel_event "
                "GROUP BY to_state").fetchall()
            cnx.close()
            funnel = {r["to_state"]: r["c"] for r in state_rows}
        except Exception as e:
            return {"error": f"db query failed: {e}"}

        return predict_revenue(
            lane_count=lane_count,
            occupied_lanes=occupied,
            leads_total=leads_total,
            funnel_by_state=funnel,
        )

    def _last_predicted_mrr(self) -> float:
        """Read most recent snapshot's total_predicted_mrr."""
        if not SNAPSHOT_PATH.exists():
            return 0.0
        try:
            d = json.loads(SNAPSHOT_PATH.read_text())
            return d.get("revenue_projection", {}).get(
                "total_predicted_mrr", 0.0)
        except Exception:
            return 0.0


if __name__ == "__main__":
    agent = DataAnalysisAgent(
        name="data-analysis-agent",
        role="data_analysis",
        health_url="http://localhost:9105/health",
    )
    print(f"[{datetime.now(timezone.utc).isoformat()}] "
          f"data-analysis online — tick {TICK_INTERVAL}s", flush=True)
    failures = 0
    while True:
        try:
            r = agent.tick()
            failures = 0
            summ = (r.get("result") or {}).get("summary", "")
            print(json.dumps({"cycle": r.get("cycle"), "summary": summ}))
        except Exception as e:
            failures += 1
            backoff = min(30 * failures, 300)
            print(json.dumps({"error": str(e)[:200], "backoff": backoff}))
            time.sleep(backoff)
            continue
        time.sleep(TICK_INTERVAL)
