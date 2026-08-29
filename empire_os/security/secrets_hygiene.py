"""
Audit 6 + secrets hygiene — Secrets scan & log-leak detection.
Real: scans /root/empire_secrets perms, detects plaintext keys/secrets in
log files (masked via pii_masking). MOCKED external: Vault rotation automation.
"""
import os
import re
import json
from pathlib import Path
from empire_os.security.pii_masking import mask_log

SECRETS_DIR = Path("/root/empire_secrets")
LOG_DIRS = [Path("/root/empire_os/feedback"), Path("/root/empire_os")]

SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|token|secret|privkey|password)[\"'\s:=]+[A-Za-z0-9_\-]{8,}"),
    re.compile(r"0x[a-fA-F0-9]{40}"),
]


class SecretsHygiene:
    def __init__(self, secrets_dir=SECRETS_DIR):
        self.secrets_dir = Path(secrets_dir)

    def scan_perms(self):
        """Return secrets files with wrong perms (should be 600)."""
        issues = []
        if not self.secrets_dir.exists():
            return [{"error": "secrets dir missing"}]
        for f in self.secrets_dir.iterdir():
            if f.is_file():
                mode = oct(f.stat().st_mode & 0o777)
                if mode != "0o600":
                    issues.append({"file": str(f), "mode": mode, "fix": "chmod 600"})
        return issues

    def scan_logs_for_leaks(self, limit=200):
        """Detect plaintext secrets/addresses in recent log lines."""
        leaks = []
        for d in LOG_DIRS:
            if not d.exists():
                continue
            for logf in sorted(d.glob("*.jsonl"), reverse=True)[:5]:
                try:
                    for i, line in enumerate(logf.read_text().splitlines()[:limit]):
                        for pat in SECRET_PATTERNS:
                            if pat.search(line):
                                leaks.append({"file": str(logf), "line": i,
                                              "masked": mask_log(line)[:160]})
                                break
                except Exception:
                    continue
        return leaks

    def report(self):
        return {"perm_issues": self.scan_perms(),
                "log_leaks": self.scan_logs_for_leaks()}


def scan_secrets():
    return SecretsHygiene().report()


if __name__ == "__main__":
    print(json.dumps(SecretsHygiene().report(), indent=2))
