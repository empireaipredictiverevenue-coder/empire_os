from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/revenue_runtime_supervisor.sh"


def test_supervisor_does_not_revive_units_while_egress_contained(tmp_path):
    guard = tmp_path / "supabase_egress_guard.json"
    guard.write_text(
        json.dumps({"state": "contained", "contained": True}),
        encoding="utf-8",
    )

    log = tmp_path / "systemctl.log"
    fake = tmp_path / "systemctl"
    fake.write_text(
        "#!/usr/bin/env bash\n"
        'printf "%s\\n" "$*" >> "$EMPIRE_TEST_SYSTEMCTL_LOG"\n'
        "exit 0\n",
        encoding="utf-8",
    )
    fake.chmod(0o755)

    env = {
        **os.environ,
        "EMPIRE_SUPABASE_EGRESS_GUARD_STATE": str(guard),
        "EMPIRE_PYTHON_BIN": sys.executable,
        "EMPIRE_SYSTEMCTL_BIN": str(fake),
        "EMPIRE_TEST_SYSTEMCTL_LOG": str(log),
    }
    result = subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "supervisor inert" in result.stdout
    assert not log.exists() or log.read_text(encoding="utf-8") == ""
