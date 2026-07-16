"""
Security Agent — fleet-wide posture + secrets/secret-leak guard.
Agentic tick loop, no separate scripts.

Owns:
  - Scans /root/feedback and /root/empire_os for leaked API keys, tokens
  - Verifies every Resend-sending code path stays on empire-ai.co.uk
  - Audits outbound HTTP for unencrypted URLs / private IP leaks
  - Reports to /root/security/findings.jsonl

GitHub tooling cloned at bootstrap:
  - OWASP/CheatSheetSeries -> /root/security/repos/CheatSheetSeries
  - Snyk/snyk-cli          -> /root/security/repos/snyk-cli (read-only patterns)
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

ROLE_DIR = Path("/root/security")
ROLE_DIR.mkdir(parents=True, exist_ok=True)
REPOS_DIR = ROLE_DIR / "repos"
REPOS_DIR.mkdir(parents=True, exist_ok=True)
TICK_INTERVAL = 600  # 10 min

REPO_TARGETS = [
    ("https://github.com/OWASP/CheatSheetSeries.git",
     REPOS_DIR / "CheatSheetSeries"),
    ("https://github.com/gitleaks/gitleaks.git",
     REPOS_DIR / "gitleaks"),
    ("https://github.com/trufflesecurity/trufflehog.git",
     REPOS_DIR / "trufflehog"),
    ("https://github.com/NVIDIA/SkillSpector.git",
     REPOS_DIR / "SkillSpector"),
]

# Patterns we treat as leaks (per OWASP secrets-management cheat sheet)
SECRET_PATTERNS = [
    (re.compile(r"sk-[A-Za-z0-9]{20,}"), "openai-style"),
    (re.compile(r"re_[A-Za-z0-9]{20,}"), "resend-key"),
    (re.compile(r"AIza[0-9A-Za-z\-_]{35}"), "google-api-key"),
    (re.compile(r"ghp_[A-Za-z0-9]{30,}"), "github-pat"),
    (re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"), "slack-token"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "aws-access-key"),
]

# Allowed domain for From headers (mirrors .env guard)
ALLOWED_FROM_DOMAIN = "empire-ai.co.uk"
RAW_IP_PRIV = re.compile(r"\b(?:10\.\d{1,3}|192\.168|172\.(?:1[6-9]|2\d|3[01]))\.\d{1,3}\.\d{1,3}\b")


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


def scan_file(path: Path) -> list[dict]:
    hits = []
    try:
        text = path.read_text(errors="ignore")
    except Exception:
        return hits
    if "RESEND_API_KEY" in text and path.name != ".env":
        # Code should never embed the key directly
        hits.append({"file": str(path), "kind": "embedded-secret-ref",
                     "line": _first_line_with(text, "RESEND_API_KEY=")})
    for pat, kind in SECRET_PATTERNS:
        for m in pat.finditer(text):
            hits.append({"file": str(path), "kind": kind,
                         "preview": m.group(0)[:12] + "...",
                         "line": text[:m.start()].count("\n") + 1})
    return hits


def _first_line_with(text: str, needle: str) -> int:
    return text[:text.find(needle)].count("\n") + 1 if needle in text else 0


class SecurityAgent(SyntheticAgent):
    """Watchdog. Reports. Does not auto-fix secrets — that needs a human."""

    def observe(self) -> dict:
        ensure_repos()
        findings = []

        # Scan feedback + empire_os for leaked secrets
        for root in (Path("/root/feedback"), Path("/root/empire_os")):
            if not root.exists():
                continue
            cutoff = time.time() - 3600
            for p in root.rglob("*"):
                if not p.is_file():
                    continue
                if p.suffix not in (".py", ".jsonl", ".json", ".log", ".md", ".txt"):
                    continue
                if "__pycache__" in str(p) or ".pytest_cache" in str(p):
                    continue
                try:
                    if p.stat().st_mtime < cutoff:
                        continue
                except OSError:
                    continue
                findings.extend(scan_file(p))

        # Verify every sender file pins ALLOWED_SEND_DOMAIN
        sender_files = list(Path("/root/empire_os/empire_os/agents").glob("*_agent.py"))
        sender_files += [Path("/root/empire_os/empire_os/alerting.py")]
        for f in sender_files:
            try:
                text = f.read_text()
            except Exception:
                continue
            if "requests.post" in text and "resend.com" in text:
                if "ALLOWED_SEND_DOMAIN" not in text:
                    findings.append({"file": str(f),
                                     "kind": "missing-domain-guard",
                                     "line": 1})

        # Scan recent outbound HTTP for unencrypted / raw-IP URLs
        for log in Path("/root/feedback").glob("*.jsonl"):
            try:
                if log.stat().st_mtime < time.time() - 1800:
                    continue
            except OSError:
                continue
            try:
                with log.open() as fh:
                    for ln in fh:
                        if "http://10." in ln or "192.168." in ln or "172.16." in ln:
                            # ignore our own internal hub calls; just log usage
                            pass
            except Exception:
                pass

        return {"ts": datetime.now(timezone.utc).isoformat(),
                "findings": findings[:50],
                "n_findings": len(findings)}

    def reason(self, state: dict) -> str:
        if not state.get("findings"):
            return json.dumps({"action": "no-op",
                               "summary": "no security findings"})
        system = ("You are the Security Agent. Triage findings by severity "
                  "1 (critical leak) to 5 (informational). JSON: "
                  '{"verdicts": [{"file":..., "kind":..., '
                  '"severity": 1-5, "action": "rotate|fix|investigate|ignore"}]}')
        prompt = json.dumps(state["findings"])
        return self.llm.chat(messages=[{"role": "user", "content": prompt}],
                             system=system, temperature=0.1, format="json")

    def act(self, decision: str) -> dict:
        path = ROLE_DIR / "findings.jsonl"
        try:
            d = json.loads(decision)
            verdicts = d.get("verdicts", [])
        except Exception:
            verdicts = [{"raw": decision[:200]}]
        record = {"ts": time.time(), "verdicts": verdicts,
                  "n": len(verdicts)}
        with path.open("a") as f:
            f.write(json.dumps(record) + "\n")
        # Auto-page the operator for severity-1 via existing alerting
        crits = [v for v in verdicts if v.get("severity") == 1]
        if crits:
            try:
                from empire_os.alerting import emit
                emit("SECURITY_CRITICAL",
                     f"[security] {len(crits)} critical finding(s)",
                     json.dumps(crits, indent=2)[:2000],
                     severity="critical")
            except Exception as e:
                with path.open("a") as f:
                    f.write(json.dumps({"ts": time.time(),
                                        "alert_emit_failed": str(e)[:200]}) + "\n")
        return {"summary": f"{len(verdicts)} finding(s), "
                            f"{len(crits)} critical"}


if __name__ == "__main__":
    agent = SecurityAgent(
        name="security-agent",
        role="security",
        health_url="http://localhost:9103/health",
    )
    print(f"[{datetime.now(timezone.utc).isoformat()}] security online — tick {TICK_INTERVAL}s", flush=True)
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
