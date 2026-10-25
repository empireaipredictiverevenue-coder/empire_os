#!/usr/bin/env python3
"""V4.9 production readiness INSPECTION: zero writes, zero privileged action.

Original EmpireOS, canonical Founder API, and existing release staging only.
Can be safely executed repeatedly by the unprivileged deployment reviewer.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

REPO = Path("/srv/empire_os")
UNIT = "empire-founder-dashboard-api.service"
DROP_DIR = Path(f"/etc/systemd/system/{UNIT}.d")
DROPIN = DROP_DIR / "zzzzzzzzzzz-predictive-v49-20261025.conf"
CANDIDATE = REPO / "scripts/empire-founder-dashboard-api-v49-readonly.conf"
MODULE = REPO / "empire_os/predictive_cloud_v49_readiness_api.py"
STAGE = Path("/home/ubuntu/empire_releases/predictive_cloud_v49_readonly_20261025")
WRAPPER = STAGE / "predictive_cloud_v49_existing_api_overlay_20261025.py"
OLD_STAGE = "/home/ubuntu/empire_releases/property_birmingham_private_stage_20261022_v3"
OLD_APP = "composite_property_jev_overlay:app"
NEW_APP = "predictive_cloud_v49_existing_api_overlay_20261025:app"
NEW_ENDPOINT = "/v1/predictive-cloud/v4/shadow-readiness"
MODULE_SHA = "192f40374fc5bc76e009d22a13a309f7712c7426b517c2da545c3d1dd027f763"
WRAPPER_SHA = "ba6aad410ec626410e8c50c5ce783535eb9324c156898df93e8f5bcb10fd4c76"


def sha256(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() and not path.is_symlink() else None
    except OSError:
        return None


def service_properties() -> dict[str, str]:
    cmd = ["systemctl", "show", UNIT, "--no-pager",
           "-p", "ActiveState", "-p", "ExecStart", "-p", "MainPID", "-p", "DropInPaths"]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=5, check=False)
    if res.returncode:
        return {}
    return dict(x.split("=", 1) for x in res.stdout.splitlines() if "=" in x)


def response(path: str) -> tuple[int, dict]:
    # All requests are GET and pinned to the existing localhost-only service.
    try:
        with urlopen("http://127.0.0.1:8766" + path, timeout=4) as r:
            raw = r.read(65536)
            return r.status, json.loads(raw) if raw else {}
    except HTTPError as exc:
        return exc.code, {}
    except (URLError, TimeoutError, ValueError):
        return 0, {}


def inspect() -> dict:
    properties = service_properties()
    exec_start = properties.get("ExecStart", "")
    checks = {
        "original_founder_service_active": properties.get("ActiveState") == "active",
        "existing_service_has_pid": properties.get("MainPID", "0").isdigit() and int(properties.get("MainPID", "0")) > 0,
        "original_or_v49_pinned_service": (OLD_STAGE in exec_start and OLD_APP in exec_start) or (str(STAGE) in exec_start and NEW_APP in exec_start),
        "pinned_v49_module_hash": sha256(MODULE) == MODULE_SHA,
        "pinned_v49_overlay_hash": sha256(WRAPPER) == WRAPPER_SHA,
        "release_candidate_present": CANDIDATE.is_file() and not CANDIDATE.is_symlink(),
        "systemd_override_directory_root_owned": DROP_DIR.is_dir() and DROP_DIR.stat().st_uid == 0,
        "stage_directory_present": STAGE.is_dir() and not STAGE.is_symlink(),
    }
    expected = ("[Service]\nExecStart=\nExecStart=/srv/empire_os/.venv/bin/uvicorn"
                f" --app-dir {STAGE} {NEW_APP} --host 127.0.0.1 --port 8766\n")
    checks["exact_override_candidate_matches_pinned_target"] = (
        CANDIDATE.is_file() and CANDIDATE.read_text() == expected)
    health_status, health = response("/health")
    old_status, old_data = response("/v1/predictive-cloud/status")
    new_status, new_data = response(NEW_ENDPOINT)
    checks["live_health_200"] = health_status == 200 and health.get("ok") is True
    checks["live_existing_predictive_status_200_observe"] = (
        old_status == 200 and old_data.get("mode") == "OBSERVE"
        and old_data.get("commercial_prediction_authorized") is False)
    route_active = (
        new_status == 200 and new_data.get("schema_version") ==
        "empire.predictive_cloud.v49.shadow_readiness.v1"
        and new_data.get("mode") == "OBSERVE"
        and new_data.get("commercial_prediction_authorized") is False
        and new_data.get("trading_authorized") is False
    )
    checks["new_readonly_route_valid_if_live"] = new_status in (404, 200) and (new_status != 200 or route_active)
    installed = DROPIN.is_file() and sha256(DROPIN) == sha256(CANDIDATE)
    checks["override_not_modified_if_present"] = not DROPIN.exists() or installed
    preflight_pass = all(checks.values())
    return {
        "status": ("V49_ALREADY_LIVE_READONLY" if route_active and installed and preflight_pass
                   else "V49_OWNER_SYSTEMD_ACTIVATION_PENDING" if preflight_pass and new_status == 404
                   else "V49_ACTIVATION_PREFLIGHT_HELD"),
        "checks": checks,
        "live_v49_http_status": new_status,
        "existing_status_http": old_status,
        "systemd_dropin_installed": installed,
        "root_service_activation_executed": False,
        "redis_activated": False,
        "funds_or_trading_activated": False,
        "other_agent_changes_modified": False,
    }


if __name__ == "__main__":
    if sys.argv[1:] != ["--read-only"]:
        raise SystemExit("V49_READ_ONLY_FLAG_REQUIRED")
    print(json.dumps(inspect(), sort_keys=True))
