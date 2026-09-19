#!/usr/bin/env python3
"""Secret-safe Phase 4 Astra runtime activation preflight."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess

from empire_os.astra_preflight import assess_runtime_preflight


def _is_enabled(unit: str) -> bool:
    result = subprocess.run(
        ["systemctl", "is-enabled", unit],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0 and result.stdout.strip() == "enabled"


def _cron_enabled() -> bool:
    result = subprocess.run(
        ["crontab", "-l"],
        capture_output=True,
        text=True,
        check=False,
    )
    return (
        result.returncode == 0
        and "EMPIRE_ASTRA_OBSERVER" in result.stdout
        and "run_astra_observer_cron.sh" in result.stdout
    )


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Phase 4 Astra activation preflight")
    p.add_argument(
        "--env",
        default="/srv/empire_os/.env.astra_observer",
    )
    p.add_argument(
        "--systemd-dir",
        default="/etc/systemd/system",
    )
    return p


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    systemd_dir = Path(args.systemd_dir)
    service = systemd_dir / "empire-astra-observer.service"
    timer = systemd_dir / "empire-astra-observer.timer"
    result = assess_runtime_preflight(
        env_path=args.env,
        service_installed=service.exists(),
        timer_installed=timer.exists(),
        timer_enabled=_is_enabled("empire-astra-observer.timer"),
        cron_scheduler_enabled=_cron_enabled(),
    )
    payload = {
        "mode": "OBSERVE",
        "side_effects": "none",
        "secrets_emitted": False,
        "runtime": result.as_dict(),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if result.runtime_ready else 2


if __name__ == "__main__":
    raise SystemExit(main())
