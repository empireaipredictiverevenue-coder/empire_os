#!/usr/bin/env python3
"""Diagnose the governed Aider -> OmniRoute path without exposing secrets."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile
from urllib import request

from empire_os.aider_builder import (
    AiderMutationRequest,
    _protected_omniroute_env,
    _sanitize_output,
    aider_health,
    build_aider_command,
    resolved_aider_model,
)


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
        "direct_model": str(
            provider.get("EMPIRE_HERMES_MODEL") or "auto"
        ),
        "aider_model": resolved_aider_model(),
    }, indent=2, sort_keys=True))

    if not base or not key:
        print("DIAG=PROVIDER_CONFIG_MISSING")
        return 2

    direct_model = str(
        provider.get("EMPIRE_HERMES_MODEL") or "auto"
    ).strip() or "auto"
    aider_model = resolved_aider_model()

    payload = json.dumps({
        "model": direct_model,
        "messages": [
            {
                "role": "user",
                "content": "Reply exactly EMPIRE_AIDER_GATEWAY_OK.",
            }
        ],
        "max_tokens": 32,
    }).encode("utf-8")
    req = request.Request(
        base + "/chat/completions",
        data=payload,
        headers={
            "Authorization": "Bearer " + key,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=90) as response:
            gateway_status = int(response.status)
            gateway_body = json.load(response)
    except Exception as exc:
        print(json.dumps({
            "gateway_ready": False,
            "reason": f"{type(exc).__name__}:{exc}",
            "secret_printed": False,
        }, indent=2, sort_keys=True))
        print("DIAG=OMNIROUTE_REQUEST_FAILED")
        return 3

    content = str(
        (((gateway_body.get("choices") or [{}])[0].get("message") or {})
        .get("content") or "")
    )
    print(json.dumps({
        "gateway_ready": gateway_status == 200 and bool(content),
        "gateway_status": gateway_status,
        "gateway_response_present": bool(content),
        "gateway_response": content[:200],
        "secret_printed": False,
    }, indent=2, sort_keys=True))
    if gateway_status != 200 or not content:
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
