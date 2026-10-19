"""Inventory only original Twenty container/volume names, no secrets or writes.

Can be run by an authorised Docker operator. Does not show container
configuration, env vars, credentials, DB contents, or any other app's data.
"""
from __future__ import annotations
import argparse
import json
import subprocess


def inspect_docker(*, runner=subprocess.run) -> dict:
    commands = (
        ["docker", "ps", "-a", "--format", "{{.Names}}|{{.Image}}|{{.Status}}"],
        ["docker", "volume", "ls", "--format", "{{.Name}}"],
    )
    results = []
    for command in commands:
        try:
            r = runner(command, capture_output=True, timeout=9,
                       text=True, check=False)
        except (OSError, subprocess.TimeoutExpired):
            return {"state": "DOCKER_OWNER_ACCESS_REQUIRED",
                    "twenty_volumes_verified": False, "twenty_data_restored": False}
        if r.returncode != 0:
            return {"state": "DOCKER_OWNER_ACCESS_REQUIRED",
                    "twenty_volumes_verified": False, "twenty_data_restored": False}
        results.append(r.stdout[:120_000])
    containers = []
    for line in results[0].splitlines():
        parts = line.split("|")
        if len(parts) == 3 and "twenty" in (parts[0] + " " + parts[1]).lower():
            containers.append({"name": parts[0][:100],
                               "image": parts[1][:120], "status": parts[2][:80]})
    volumes = [name[:100] for name in results[1].splitlines()
               if "twenty" in name.lower()]
    return {
        "state": "READ_ONLY_METADATA_INVENTORY_COMPLETE",
        "twenty_containers": containers[:25],
        "twenty_named_volumes": volumes[:50],
        "twenty_volumes_verified": bool(volumes),
        "original_postgresql_content_restored": False,
        "volume_names_alone_do_not_prove_original_data": True,
        "secrets_read": False, "service_started": False,
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--read-only", required=True, action="store_true")
    p.parse_args(argv)
    report = inspect_docker()
    report.update({"schema_version": "empire.twenty_docker_owner_inventory.v1",
                   "canonical_empiredb_writes": False,
                   "outbound_authorized": False,
                   "execution_authority": "none"})
    print(json.dumps(report, sort_keys=True))
    return 0 if report["state"] == "READ_ONLY_METADATA_INVENTORY_COMPLETE" else 2

if __name__ == "__main__":
    raise SystemExit(main())
