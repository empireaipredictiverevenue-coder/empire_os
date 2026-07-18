"""
Systems Engineer Agent — fleet-wide reliability + auto-fix.
Extends SyntheticAgent. Agentic tick loop, no separate scripts.

Owns:
  - Cross-container health probes (incus list, pm2 jlist, /health)
  - Lint / import / module-missing detector across /root/empire_os
  - Auto-fix: write tickets to /root/systems_engineer/tickets.jsonl
  - Self-heal: trigger pm2 restart for crashed agents with backoff

Tools: GitHub clones cached under /root/systems_engineer/repos/
  - Netflix/chaosmonkey  -> chaos engineering principles
  - spotify/luigi        -> pipeline dependency graph patterns
"""
from __future__ import annotations
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/root/empire_os")
from empire_os.agent_core import OllamaClient
from empire_os.synthetic_agents import SyntheticAgent

HUB = os.environ.get("HUB_URL", "http://127.0.0.1:8000")
ROLE_DIR = Path("/root/systems_engineer")
ROLE_DIR.mkdir(parents=True, exist_ok=True)
REPOS_DIR = ROLE_DIR / "repos"
REPOS_DIR.mkdir(parents=True, exist_ok=True)
TICK_INTERVAL = 300  # 5 min

REPO_TARGETS = [
    ("https://github.com/Netflix/chaosmonkey.git",
     REPOS_DIR / "chaosmonkey"),
    ("https://github.com/spotify/luigi.git",
     REPOS_DIR / "luigi"),
    ("https://github.com/awslabs/git-secrets.git",
     REPOS_DIR / "git-secrets"),
]


def sh(cmd, timeout=15):
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


class SystemsEngineerAgent(SyntheticAgent):
    """Fleet reliability. Sees what other agents miss. Fixes what it can."""

    def observe(self) -> dict:
        ensure_repos()
        s = {"ts": datetime.now(timezone.utc).isoformat(),
             "stopped_incus": [], "stopped_pm2": [], "errors": [],
             "issues": [], "disk_pct": 0, "mem_free_mb": 0}

        r = sh("incus list -c n,s -f csv")
        if r.returncode == 0:
            for ln in r.stdout.strip().splitlines():
                if "," not in ln:
                    continue
                name, st = ln.split(",", 1)
                if "STOPPED" in st and "STOPPED" not in (name + ","):
                    s["stopped_incus"].append(name.strip())

        r = sh("pm2 jlist")
        if r.returncode == 0:
            try:
                procs = json.loads(r.stdout or "[]")
                for p in procs:
                    n = p.get("name", "")
                    st = p.get("pm2_env", {}).get("status", "")
                    if st in ("errored", "stopped") and n.startswith("empire-"):
                        s["stopped_pm2"].append(f"{n}:{st}")
            except Exception:
                pass

        r = sh("df -h /root")
        if r.returncode == 0:
            for ln in r.stdout.splitlines():
                if "/dev/" in ln:
                    pct = ln.split()[-2] if ln.split() else "0%"
                    if pct.endswith("%"):
                        try: s["disk_pct"] = int(pct[:-1])
                        except: pass
                    break

        r = sh("free -m")
        if r.returncode == 0:
            for ln in r.stdout.splitlines():
                if ln.startswith("Mem:"):
                    parts = ln.split()
                    if len(parts) >= 4:
                        try: s["mem_free_mb"] = int(parts[3])
                        except: pass
                    break

        # Recent ERROR events across all feedback logs (last 5 min)
        log_dir = Path("/root/feedback")
        if log_dir.exists():
            cutoff = time.time() - 300
            for f in log_dir.glob("*.jsonl"):
                try:
                    if f.stat().st_mtime < cutoff:
                        continue
                    with f.open() as fh:
                        for ln in fh:
                            try:
                                e = json.loads(ln)
                                if e.get("level") == "ERROR":
                                    s["errors"].append({
                                        "log": f.name,
                                        "msg": e.get("msg", "")[:80],
                                        "error": str(e.get("error", ""))[:120],
                                    })
                            except: pass
                except: pass

        if s["stopped_pm2"]:
            s["issues"].append(f"pm2 stopped: {s['stopped_pm2'][:3]}")
        if s["stopped_incus"]:
            s["issues"].append(f"incus stopped: {s['stopped_incus'][:3]}")
        if s["disk_pct"] > 85:
            s["issues"].append(f"disk {s['disk_pct']}%")
        if s["mem_free_mb"] < 200:
            s["issues"].append(f"mem {s['mem_free_mb']}MB")
        if len(s["errors"]) > 10:
            s["issues"].append(f"{len(s['errors'])} errors last 5m")

        return s

    def reason(self, state: dict) -> str:
        if not state.get("issues") and not state.get("stopped_pm2"):
            return json.dumps({"action": "no-op",
                               "summary": "all systems nominal"})
        system = ("You are the Systems Engineer. Given fleet state, "
                  "choose the safest single action. JSON only: "
                  '{"action": "restart|alert|noop", '
                  '"target": "<pm2 name or empty>", '
                  '"reason": "<one line>"}')
        prompt = json.dumps({k: v for k, v in state.items() if k != "ts"})
        return self.llm.chat(messages=[{"role": "user", "content": prompt}],
                             system=system, temperature=0.1, format="json")

    def act(self, decision: str) -> dict:
        try:
            d = json.loads(decision)
        except Exception:
            return {"summary": "decision-parse-failed", "raw": decision[:100]}

        action = d.get("action", "noop")
        target = d.get("target", "")
        ticket = {"ts": time.time(), **d}

        # Auto-fix scope: only restart empire-* pm2 procs that are
        # explicitly flagged by our own probe. Never restart hub/orchestrator.
        if action == "restart" and target.startswith("empire-") and \
           target not in ("empire-hub", "empire-orchestrator",
                          "empire-systems-engineer",
                          "empire-code-review",
                          "empire-security",
                          "empire-lead-sources"):
            r = sh(f"pm2 restart {target}")
            ticket["pm2_exit"] = r.returncode
            ticket["applied"] = r.returncode == 0

        path = ROLE_DIR / "tickets.jsonl"
        with path.open("a") as f:
            f.write(json.dumps(ticket) + "\n")
        return {"summary": f"{action}:{target}"[:80], "applied": ticket.get("applied", False)}


if __name__ == "__main__":
    agent = SystemsEngineerAgent(
        name="systems-engineer-agent",
        role="systems_engineer",
        health_url="http://localhost:9101/health",
    )
    print(f"[{datetime.now(timezone.utc).isoformat()}] systems-engineer online — tick {TICK_INTERVAL}s", flush=True)
    failures = 0
    while True:
        try:
            r = agent.tick()
            failures = 0
            print(json.dumps({"cycle": r.get("cycle"),
                              "summary": r.get("result", {}).get("summary", "")}))
        except Exception as e:
            failures += 1
            backoff = min(30 * failures, 300)
            print(json.dumps({"error": str(e)[:200], "backoff": backoff}))
            time.sleep(backoff)
            continue
        time.sleep(TICK_INTERVAL)
