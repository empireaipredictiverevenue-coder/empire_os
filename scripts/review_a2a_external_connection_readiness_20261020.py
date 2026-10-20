#!/usr/bin/env python3
"""Read presence-only provider configuration; never print actual credentials.

This is an onboarding checklist, not a live OAuth test or a payment operation.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import tempfile

from empire_os.a2a_external_connection_preflight_v1 import REQUIRED, review_connections
from empire_os.runtime_env import load_runtime_env

REPORT = (Path(__file__).resolve().parents[1] /
          "runtime/a2a_commercial_signal_mining/external_connection_readiness.json")


def main() -> int:
    p = argparse.ArgumentParser(description="Check Meta/Stripe read-only setup blockers")
    p.add_argument("--write-local", action="store_true")
    args = p.parse_args()
    env = load_runtime_env("/etc/empire_os.env")
    names = {name for keys in REQUIRED.values() for name in keys}
    config_presence = {name: bool(env.get(name)) for name in names}
    output = review_connections(config_presence)
    if args.write_local:
        REPORT.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if REPORT.parent.is_symlink() or REPORT.is_symlink():
            raise ValueError("unsafe_preflight_output")
        fd, tmp = tempfile.mkstemp(prefix=".connector_readiness_", dir=REPORT.parent)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf8") as f:
                json.dump(output, f, indent=2, sort_keys=True)
                f.write("\n")
            os.replace(tmp, REPORT)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
    print(json.dumps(output, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
