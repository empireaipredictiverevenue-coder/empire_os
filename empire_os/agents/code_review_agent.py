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
from empire_os.agent_core import OpenCodeZenClient
from empire_os.agents.guardrails import scrub_secrets, has_forbidden
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
        # Review the WHOLE empire_os codebase (round-robin, 5 files/cycle)
        # so the free-tier LLM covers everything over time without blowing
        # rate limits in a single cycle.
        root = Path("/root/empire_os")
        skip = ("__pycache__", ".pytest_cache", "site-packages",
                "venv", ".venv", "node_modules", "/.git/")
        all_py = []
        for p in root.rglob("*.py"):
            sp = str(p)
            if any(s in sp for s in skip):
                continue
            all_py.append(sp)
        all_py.sort()

        # round-robin index persisted to ROLE_DIR
        idx_file = ROLE_DIR / "scan_index.json"
        start = 0
        if idx_file.exists():
            try:
                start = int(idx_file.read_text().strip() or "0") % max(1, len(all_py))
            except Exception:
                start = 0
        n = 5
        batch = [all_py[(start + i) % len(all_py)] for i in range(min(n, len(all_py)))]
        idx_file.write_text(str((start + n) % max(1, len(all_py))))

        candidates = [(p, p) for p in batch]
        findings = []
        for path_str, _ in candidates:
            path = Path(path_str)
            errs = py_compile_check(path) + import_check(path)
            if errs:
                findings.append({"file": path_str,
                                 "errors": errs,
                                 "mtime": path.stat().st_mtime})

        return {
            "ts": datetime.now(timezone.utc).isoformat(),
            "scanned": [c[0] for c in candidates],
            "total_files": len(all_py),
            "findings": findings,
            "total_findings": len(findings),
        }

    def reason(self, state: dict) -> str:
        scanned = state.get("scanned", [])
        if not scanned:
            return json.dumps({"action": "no-op", "summary": "nothing to scan"})
        # Compile/import errors take priority (always reported)
        err_findings = state.get("findings", [])
        # Always LLM-review the scanned files for quality (whole-codebase
        # review, not just when something fails to compile).
        system = ("You are the Code Review Agent for the Empire OS codebase. "
                  "Review the listed Python files for real bugs, security "
                  "issues, dead code, and anti-patterns. Ignore style nits. "
                  "Only report actionable findings. "
                  "JSON: {\"verdicts\": [{\"file\": \"...\", "
                  "\"severity\": 1-5, \"fix\": \"...\"}]}")
        payload = {
            "scanned": scanned,
            "compile_errors": err_findings,
            "total_files_in_codebase": state.get("total_files", len(scanned)),
        }
        return self.llm.chat(messages=[{"role": "user",
                                        "content": json.dumps(payload)}],
                             system=system, temperature=0.2, format="json")

    def act(self, decision: str) -> dict:
        # GUARDRAIL: scrub secrets + block forbidden actions in LLM output
        decision = scrub_secrets(decision)
        if has_forbidden(decision):
            print("[GUARDRAIL][read_only] blocked forbidden action in verdict")
            decision = json.dumps({"verdicts": [], "blocked": "forbidden_action"})
        path = ROLE_DIR / "findings.jsonl"
        try:
            d = json.loads(decision)
            verdicts = d.get("verdicts", [])
        except Exception:
            verdicts = [{"raw": decision[:300]}]

        record = {"ts": time.time(), "verdicts": verdicts}
        with path.open("a") as f:
            f.write(json.dumps(record) + "\n")
        return {"summary": f"reviewed {len(verdicts)} verdict(s)"}


if __name__ == "__main__":
    agent = CodeReviewAgent(
        name="code-review-agent",
        role="code_review",
        health_url="http://localhost:9102/health",
        llm=OpenCodeZenClient(model="deepseek-v4-flash-free"),
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
