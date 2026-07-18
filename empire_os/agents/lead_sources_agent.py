"""
Lead Sources Agent — discovers, evaluates, and ranks new lead-source
candidates. Agentic tick loop, no separate scripts.

Owns:
  - Probes Reddit, Craigslist, county permits, BBB, Google Places
    for new verticals that fit Empire OS buyer subscriptions.
  - Maintains /root/lead_sources/sources.json (active + scoring).
  - Emits 'NEW_SOURCE' alert when a source scores > threshold.
  - Coordinates with existing reddit_sniper / b2b_scraper / contractor_scraper.

GitHub tooling cloned at bootstrap:
  - josephmisiti/awesome-machine-learning  -> inspiration, not used in prod
  - public-apis/public-apis                -> API discovery reference
"""
from __future__ import annotations
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/root/empire_os")
from empire_os.agent_core import OllamaClient
from empire_os.synthetic_agents import SyntheticAgent

HUB = os.environ.get("HUB_URL", "http://127.0.0.1:8000")
ROLE_DIR = Path("/root/lead_sources")
ROLE_DIR.mkdir(parents=True, exist_ok=True)
REPOS_DIR = ROLE_DIR / "repos"
REPOS_DIR.mkdir(parents=True, exist_ok=True)
TICK_INTERVAL = 1800  # 30 min

SOURCES_FILE = ROLE_DIR / "sources.json"
DISCOVERY_LOG = ROLE_DIR / "discovery.jsonl"

REPO_TARGETS = [
    ("https://github.com/public-apis/public-apis.git",
     REPOS_DIR / "public-apis"),
]

# Niches that map to existing buyer subscriptions
KNOWN_NICHES = {
    "general_contractor", "plumbing", "hvac", "roofing",
    "landscaping", "pest_control", "mold_remediation",
    "painting", "electrical", "water_damage", "storm_damage",
    "weight_loss", "addiction", "mortgage", "debt_relief",
    "insurance", "cybersecurity", "managed_it", "marketing",
    "real_estate", "lawyer", "camp_lejeune", "afff",
    "ozempic", "hormone_therapy", "investing", "vision",
    "global_matchmaker", "consulting", "software_dev",
    "cloud", "roundup", "disaster_restoration",
    "residential_roofing", "emergency_plumbing",
    "emergency_hvac", "roof_repair",
}


def sh(cmd, timeout=60):
    try:
        return subprocess.run(cmd, shell=True, capture_output=True,
                              text=True, timeout=timeout)
    except Exception as e:
        return type("R", (), {"returncode": -1, "stdout": "", "stderr": str(e)})()


def ensure_repos():
    log = ROLE_DIR / "repos_bootstrap.jsonl"
    done = set()
    if log.exists():
        for ln in log.open():
            try: done.add(json.loads(ln)["repo"])
            except: pass
    for url, dest in REPO_TARGETS:
        if dest.exists() or dest.name in done:
            continue
        r = sh(f"git clone --depth 1 {url} {dest}")
        with log.open("a") as f:
            f.write(json.dumps({"repo": dest.name, "ok": r.returncode == 0,
                                "stderr": r.stderr[:200]}) + "\n")


def load_sources() -> dict:
    if SOURCES_FILE.exists():
        try: return json.loads(SOURCES_FILE.read_text())
        except: pass
    return {"active": [], "candidates": [], "last_discovery": None}


def save_sources(s: dict):
    SOURCES_FILE.write_text(json.dumps(s, indent=2))


class LeadSourcesAgent(SyntheticAgent):
    """Discovers and ranks new lead sources. Files ideas, scores them."""

    def observe(self) -> dict:
        ensure_repos()
        s = load_sources()

        # Probe hub for currently active source adapters
        try:
            r = sh(f"curl -s --max-time 5 {HUB}/v1/lead_sources")
            active = json.loads(r.stdout) if r.returncode == 0 else []
        except Exception:
            active = []

        # Probe feedback logs for source adapter health
        # (any source that hasn't emitted in 6h is "stale")
        cutoff = time.time() - 21600
        live_sources = set()
        for log in Path("/root/feedback").glob("*_log.jsonl"):
            try:
                if log.stat().st_mtime < cutoff:
                    continue
            except OSError:
                continue
            live_sources.add(log.stem.replace("_log", ""))

        return {
            "ts": datetime.now(timezone.utc).isoformat(),
            "active_sources": active,
            "live_log_sources": sorted(live_sources),
            "known_niches": sorted(KNOWN_NICHES),
            "n_active": len(active),
            "n_live_logs": len(live_sources),
        }

    def reason(self, state: dict) -> str:
        system = ("You are the Lead Sources Agent. Suggest the SINGLE most "
                  "promising NEW lead source Empire OS should add. "
                  "JSON: {\"name\": \"...\", \"niche\": \"<one of known>\", "
                  "\"expected_yield_per_day\": int, "
                  "\"integration_effort\": \"low|medium|high\", "
                  "\"source_url\": \"...\", \"reason\": \"<one line>\"}")
        prompt = (
            f"Active sources: {state['n_active']}. Live logs: "
            f"{state['n_live_logs']}. Known niches: "
            f"{', '.join(state['known_niches'][:15])}..."
        )
        return self.llm.chat(messages=[{"role": "user", "content": prompt}],
                             system=system, temperature=0.7, format="json")

    def act(self, decision: str) -> dict:
        try:
            d = json.loads(decision)
        except Exception:
            return {"summary": "decision-parse-failed"}

        # Validate niche against known set
        niche = d.get("niche", "")
        if niche and niche not in KNOWN_NICHES:
            d["niche_unknown"] = True

        s = load_sources()
        s["candidates"].append(d)
        s["candidates"] = s["candidates"][-50:]  # ring buffer
        s["last_discovery"] = datetime.now(timezone.utc).isoformat()
        save_sources(s)

        with DISCOVERY_LOG.open("a") as f:
            f.write(json.dumps({"ts": time.time(), **d}) + "\n")

        # Auto-elevate if integration is low-effort and yield > 5/day
        if d.get("integration_effort") == "low" and \
           int(d.get("expected_yield_per_day", 0)) >= 5 and \
           d.get("niche") in KNOWN_NICHES:
            try:
                from empire_os.alerting import emit
                emit("NEW_SOURCE",
                     f"[lead-sources] {d.get('name', '?')} -> {niche}",
                     json.dumps(d, indent=2)[:1500],
                     severity="info")
            except Exception as e:
                return {"summary": f"discovered but alert failed: {e}"}

        return {"summary": f"candidate: {d.get('name', '?')[:30]} ({niche})"}


if __name__ == "__main__":
    agent = LeadSourcesAgent(
        name="lead-sources-agent",
        role="lead_sources",
        health_url="http://localhost:9104/health",
    )
    print(f"[{datetime.now(timezone.utc).isoformat()}] lead-sources online — tick {TICK_INTERVAL}s", flush=True)
    failures = 0
    while True:
        try:
            r = agent.tick()
            failures = 0
            print(json.dumps({"cycle": r.get("cycle"),
                              "summary": r.get("result", {}).get("summary", "")}))
        except Exception as e:
            failures += 1
            backoff = min(60 * failures, 600)
            print(json.dumps({"error": str(e)[:200], "backoff": backoff}))
            time.sleep(backoff)
            continue
        time.sleep(TICK_INTERVAL)
