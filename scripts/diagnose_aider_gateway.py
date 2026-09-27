#!/usr/bin/env python3
"""Diagnose the governed Aider -> OmniRoute path without exposing secrets."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile

from empire_os.aider_builder import (
    AiderMutationRequest,
    _protected_omniroute_env,
    _sanitize_output,
    aider_health,
    build_aider_command,
)
from empire_os.aider_model_selector import select_usable_aider_model


REPO_ROOT = Path("/srv/empire_os")


def main() -> int:
    provider = _protected_omniroute_env()
    base = str(provider.get("OPENAI_BASE_URL") or "").rstrip("/")
    key = str(provider.get("OPENAI_API_KEY") or "")
    print(json.dumps({
        "aider_health": aider_health(),
        "provider_base_present": bool(base),
        "provider_key_present": bool(key),
        "provider_key_printed": False,
        "preferred_model": str(
            provider.get("EMPIRE_HERMES_MODEL") or "auto"
        ),
    }, indent=2, sort_keys=True))

    if not base or not key:
        print("DIAG=PROVIDER_CONFIG_MISSING")
        return 2

    selection = select_usable_aider_model(
        timeout_seconds=20,
        max_candidates=6,
    )
    safe_selection = {
        "selected": selection.get("selected"),
        "selected_direct_model": selection.get(
            "selected_direct_model"
        ),
        "attempts": selection.get("attempts"),
        "catalog_observed": selection.get("catalog_observed"),
        "reason": selection.get("reason"),
        "execution_authority": "none",
    }
    print(json.dumps(
        {"model_selection": safe_selection},
        indent=2,
        sort_keys=True,
    ))
    aider_model = str(selection.get("selected") or "")
    if not aider_model:
        print("DIAG=OMNIROUTE_NO_USABLE_MODEL")
        return 4

    binary = str(aider_health().get("executable") or "")
    if not binary:
        print("DIAG=AIDER_BINARY_MISSING")
        return 5

    with tempfile.TemporaryDirectory(
        prefix="empire-aider-diag-",
        dir="/var/tmp",
    ) as tmp:
        clone = Path(tmp) / "repo"
        cloned = subprocess.run(
            [
                "git",
                "clone",
                "--no-hardlinks",
                "--single-branch",
                "--branch",
                "feature/revenue-intelligence-v2",
                str(REPO_ROOT),
                str(clone),
            ],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        if cloned.returncode != 0:
            print(json.dumps({
                "clone_ready": False,
                "reason": "diagnostic_clone_failed",
                "secret_printed": False,
            }, indent=2, sort_keys=True))
            print("DIAG=DIAGNOSTIC_CLONE_FAILED")
            return 5

        git_dir = clone / ".git"
        (git_dir / "empire-aider-config.yml").write_text(
            "{}\n",
            encoding="utf-8",
        )
        (git_dir / "empire-aider.env").write_text(
            "",
            encoding="utf-8",
        )

        command = build_aider_command(
            clone,
            AiderMutationRequest(
                objective=(
                    "Do not edit anything. Reply to the task and exit. "
                    "This is a connectivity diagnostic only."
                ),
                allowed_paths=("empire_os/aider_builder.py",),
                model=aider_model,
                max_runtime_seconds=120,
            ),
            executable=binary,
        )
        command.append("--dry-run")

        env = {
            "PATH": "/home/ubuntu/.local/bin:/usr/local/bin:/usr/bin:/bin",
            "HOME": "/var/tmp/empire-aider-home",
            "XDG_CACHE_HOME": "/var/tmp/empire-aider-cache",
            "OPENAI_API_BASE": base,
            "AIDER_OPENAI_API_BASE": base,
            "OPENAI_API_KEY": key,
            "AIDER_OPENAI_API_KEY": key,
            "AIDER_ANALYTICS_DISABLE": "true",
        }
        run = subprocess.run(
            command,
            cwd=str(clone),
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    output = _sanitize_output(
        (run.stdout or "") + "\n" + (run.stderr or ""),
        env,
    )
    print(json.dumps({
        "aider_returncode": run.returncode,
        "aider_output_tail": output,
        "secret_printed": False,
    }, indent=2, sort_keys=True))
    if run.returncode != 0:
        print("DIAG=AIDER_INVOCATION_FAILED")
        return 6

    print("DIAG=READY_FOR_MUTATION_PROBE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
