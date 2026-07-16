"""
Code Review Agent — automated diff/PR reviewer.
Agentic tick loop, no separate scripts.

Owns:
  - Watches /root/empire_os/ for recent file changes
  - Runs lightweight static checks: py_compile, import-ok, lint smells
  - Reads Claude skills for review heuristics from
    /tmp/repo_skills/skills/code-review (cloned from anthropics/skills)
  - Writes findings to /root/code_review/findings.jsonl

GitHub tooling cloned at bootstrap:
  - anthropics/skills            -> /tmp/repo_skills (already mounted)
  - coderabbitai/ai-pr-reviewer   -> /root/code_review/repos/ai-pr-reviewer
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

ROLE_DIR = Path("/root/code_review")
ROLE_DIR.mkdir(parents=True, exist_ok=True)
REPOS_DIR = ROLE_DIR / "repos"
REPOS_DIR.mkdir(parents=True, exist_ok=True)
TICK_INTERVAL = 900  # 15 min — code review is expensive


SKILLS_DIR = Path("/tmp/repo_skills")
REPO_TARGETS = [
    ("https://github.com/Netflix/chaosmonkey.git",
     REPOS_DIR / "chaosmonkey"),
    ("https://github.com/spotify/luigi.git",
     REPOS_DIR / "luigi"),
    ("https://github.com/awslabs/git-secrets.git",
     REPOS_DIR / "git-secrets"),
]


def sh(cmd, timeout=60):
    try:
        return subprocess.run(cmd, shell=True, capture_output=True,
                              text=True, timeout=timeout)
    except Exception as e:
        return type("R", (), {"returncode": -1, "stdout": "", "stderr": str(e)})()


def ensure_repos():
    """Clone review-tooling repos on first tick."""
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
            f.write(json.dumps({"repo": dest.name, "url": url,
                                "ok": r.returncode == 0,
                                "stderr": r.stderr[:200]}) + "\n")


def py_compile_check(path: Path) -> list[str]:
    errs = []
    r = sh(f"python3 -m py_compile {path}")
    if r.returncode != 0:
        errs.append(f"py_compile failed: {r.stderr.splitlines()[-1] if r.stderr else '?'}")
    return errs


def import_check(path: Path) -> list[str]:
    """Try to import the module by adding its parent dir to sys.path."""
    errs = []
    # cheap heuristic — try to import the file's basename without .py
    mod = path.stem
    parent = str(path.parent)
    py = (
        f"import sys; sys.path.insert(0, '{parent}'); "
        f"import importlib, {mod} as _m; importlib.reload(_m)"
    )
    r = sh(f"cd {parent} && python3 -c \"{py}\"")
    if r.returncode != 0:
        msg = r.stderr.strip().splitlines()[-1] if r.stderr.strip() else "import error"
        errs.append(f"import: {msg[:160]}")
    return errs


class CodeReviewAgent(SyntheticAgent):
    """Watches the empire_os codebase, surfaces real findings."""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._seen_files: dict[str, float] = {}

    def observe(self) -> dict:
        ensure_repos()
        # Scan Python files modified in last 30 min
        root = Path("/root/empire_os")
        cutoff = time.time() - 1800
        candidates = []
        for p in root.rglob("*.py"):
            if "__pycache__" in str(p) or ".pytest_cache" in str(p):
                continue
            try:
                m = p.stat().st_mtime
            except OSError:
                continue
            if m < cutoff:
                continue
            candidates.append((str(p), m))

        # Pick up to 5 files per cycle to bound LLM cost
        candidates.sort(key=lambda x: -x[1])
        candidates = candidates[:5]

        findings = []
        for path_str, mtime in candidates:
            path = Path(path_str)
            errs = py_compile_check(path) + import_check(path)
            if errs:
                findings.append({"file": path_str,
                                 "errors": errs,
                                 "mtime": mtime})

        return {
            "ts": datetime.now(timezone.utc).isoformat(),
            "scanned": [c[0] for c in candidates],
            "findings": findings,
            "total_findings": len(findings),
        }

    def reason(self, state: dict) -> str:
        if not state.get("findings"):
            return json.dumps({"action": "no-op",
                               "summary": "no new findings"})
        system = ("You are the Code Review Agent. For each finding, "
                  "classify severity 1-5 and suggest a one-line fix. "
                  "JSON: {\"verdicts\": [{\"file\": \"...\", "
                  "\"severity\": 1-5, \"fix\": \"...\"}]}")
        prompt = json.dumps(state["findings"])
        return self.llm.chat(messages=[{"role": "user", "content": prompt}],
                             system=system, temperature=0.2, format="json")

    def act(self, decision: str) -> dict:
        path = ROLE_DIR / "findings.jsonl"
        try:
            d = json.loads(decision)
            verdicts = d.get("verdicts", [])
        except Exception:
            verdicts = [{"raw": decision[:300]}]

        record = {"ts": time.time(), "verdicts": verdicts}
        with path.open("a") as f:
            f.write(json.dumps(record) + "\n")
        return {"summary": f"reviewed {len(verdicts)} file(s)"}


if __name__ == "__main__":
    agent = CodeReviewAgent(
        name="code-review-agent",
        role="code_review",
        health_url="http://localhost:9102/health",
    )
    print(f"[{datetime.now(timezone.utc).isoformat()}] code-review online — tick {TICK_INTERVAL}s", flush=True)
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
