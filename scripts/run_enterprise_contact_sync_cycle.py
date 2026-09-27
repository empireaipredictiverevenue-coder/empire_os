#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import subprocess

from empire_os.enterprise_contact_repair import record_incident


ROOT = Path("/srv/empire_os")
PYTHON = ROOT / ".venv/bin/python"

STAGES = (
    (
        "runtime_sync_failure",
        "enterprise contact intelligence sync",
        [
            str(PYTHON),
            str(ROOT / "scripts/run_enterprise_contact_intelligence.py"),
        ],
    ),
    (
        "buyer_acquisition_refresh_failure",
        "buyer acquisition refresh",
        [
            str(PYTHON),
            str(ROOT / "scripts/refresh_buyer_acquisition_team.py"),
            "--repo-root",
            str(ROOT),
        ],
    ),
    (
        "post_install_verification_failure",
        "enterprise contact verification",
        [
            str(PYTHON),
            str(ROOT / "scripts/verify_enterprise_contact_intelligence.py"),
        ],
    ),
)


def _head() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=20,
    )
    return completed.stdout.strip()


def main() -> int:
    outcomes = []
    for kind, label, command in STAGES:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
            timeout=180,
        )
        combined = (
            (completed.stdout or "")
            + "\n"
            + (completed.stderr or "")
        )[-16000:]
        outcomes.append({
            "stage": label,
            "returncode": int(completed.returncode),
            "output_tail": combined[-3000:],
        })
        if completed.returncode != 0:
            incident = record_incident(
                kind=kind,
                log_text=combined,
                command=" ".join(command),
                returncode=int(completed.returncode),
                base_head=_head(),
            )
            print(json.dumps({
                "ok": False,
                "failed_stage": label,
                "classification": incident["classification"],
                "incident_fingerprint": incident["fingerprint"],
                "outcomes": outcomes,
                "live_outbound_send": False,
                "payment_action": False,
                "actual_revenue": False,
            }, indent=2, sort_keys=True))
            return int(completed.returncode) or 1

    print(json.dumps({
        "ok": True,
        "outcomes": outcomes,
        "live_outbound_send": False,
        "payment_action": False,
        "actual_revenue": False,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
