#!/usr/bin/env python3
from __future__ import annotations

import json

from empire_os.pi_sandbox_runner import PiSandboxJob, run_pi_sandbox_job


def main() -> int:
    result = run_pi_sandbox_job(
        "/srv/empire_os",
        PiSandboxJob(
            job_id="pi-runtime-smoke",
            prompt=(
                "Read the repository README only if useful. Do not edit or create "
                "any files. Reply with a concise confirmation that the bounded "
                "sandbox is operational."
            ),
            allowed_paths=("tests/",),
            lease_resources=("domain:pi_runtime_smoke",),
            pytest_targets=(),
            max_runtime_seconds=180,
        ),
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("status") == "COMPLETED_NO_CHANGES" else 2


if __name__ == "__main__":
    raise SystemExit(main())
