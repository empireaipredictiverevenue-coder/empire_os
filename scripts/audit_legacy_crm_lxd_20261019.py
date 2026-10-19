"""Read-only LXD recovery audit for historical Twenty and Listmonk.

Original July 2026 production records show LXD instance names twenty-crm
and listmonk-mail. Docker is not the original runtime. No instance start,
image import, restore, customer data read, network traffic, or service write.
"""
from __future__ import annotations
import argparse
import json
import subprocess

SCHEMA = "empire.legacy_crm_lxd_inventory.v1"
NAMES = ("twenty-crm", "listmonk-mail")

def audit(*, runner=subprocess.run) -> dict:
    results = {}
    for name, cmd in (
        ("instances", ["lxc", "list", "--all-projects", "--format", "json"]),
        ("storage_pools", ["lxc", "storage", "list", "--format", "json"]),
        ("projects", ["lxc", "project", "list", "--format", "json"]),
    ):
        try:
            r = runner(cmd, capture_output=True, text=True,
                       timeout=12, check=False)
            if r.returncode != 0:
                raise ValueError("lxd_readonly_catalog_unavailable")
            data = json.loads(r.stdout)
            if not isinstance(data, list) or len(data) > 2000:
                raise ValueError("unexpected_lxd_catalog_shape")
            results[name] = data
        except (ValueError, json.JSONDecodeError, OSError,
                subprocess.TimeoutExpired):
            return {
                "schema_version": SCHEMA,
                "state": "HOLD_LXD_METADATA_UNAVAILABLE",
                "services_started": False, "canonical_empiredb_writes": False,
                "execution_authority": "none",
            }
    instances = results["instances"]
    pools = results["storage_pools"]
    history = {}
    for expected in NAMES:
        matched = [x for x in instances
                   if x.get("name") == expected]
        history[expected] = {
            "currently_registered": len(matched) > 0,
            "current_status": matched[0].get("status") if matched else None,
            "original_data_proven": False,
        }
    return {
        "schema_version": SCHEMA,
        "mode": "READ_ONLY_LXD_METADATA",
        "state": "CURRENT_LXD_HAS_NO_HISTORICAL_INSTANCES"
                 if not any(v["currently_registered"] for v in history.values())
                 else "NAMED_INSTANCES_REQUIRE_ORIGINAL_DATA_REVIEW",
        "historic_runtime": "LXD (Incus-compatible lineage)",
        "historic_containers": history,
        "instance_count_all_projects": len(instances),
        "storage_pool_count": len(pools),
        "project_count": len(results["projects"]),
        "original_database_backup_restored": False,
        "original_customer_records_verified": False,
        "unregistered_offline_backup_may_still_exist": True,
        "docker_is_not_historic_runtime": True,
        "services_started": False, "subscriber_imports": 0,
        "outbound_authorized": False,
        "canonical_empiredb_writes": False, "execution_authority": "none",
    }

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--read-only", required=True, action="store_true")
    parser.parse_args(argv)
    result = audit()
    print(json.dumps(result, sort_keys=True))
    return 0 if result.get("mode") == "READ_ONLY_LXD_METADATA" else 2

if __name__ == "__main__":
    raise SystemExit(main())
