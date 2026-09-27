"""Unified read-only readiness snapshot for Empire Data Cloud."""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import sys
from typing import Any

from empire_os.data_cloud_discovery import RUNTIME_COUPLING_MARKERS, discover_vendor_dependencies
from empire_os.data_cloud_infrastructure import (
    HostObservation,
    evaluate_foundation_readiness,
    observe_local_host,
)


def build_readiness_snapshot(
    repo_root: str | Path,
    *,
    host_observation: HostObservation | None = None,
    foundation_contract_verified: bool = False,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    host = host_observation or observe_local_host("/")

    findings = discover_vendor_dependencies(root)
    marker_counts = Counter(row.marker for row in findings)
    file_counts = Counter(row.path for row in findings)
    classification_counts = Counter(row.classification for row in findings)
    runtime_classes = {
        "production_runtime",
        "application_runtime",
        "runtime_integration",
    }
    runtime_findings = [
        row for row in findings if row.classification in runtime_classes
    ]
    runtime_file_counts = Counter(row.path for row in runtime_findings)
    requires_review_count = classification_counts.get("requires_review", 0)

    return {
        "schema_version": "empire.data-cloud-readiness.v1",
        "repo_root": str(root),
        "host": evaluate_foundation_readiness(host),
        "dependency_inventory": {
            "finding_count": len(findings),
            "file_count": len(file_counts),
            "marker_counts": dict(sorted(marker_counts.items())),
            "classification_counts": dict(sorted(classification_counts.items())),
            "runtime_finding_count": len(runtime_findings),
            "runtime_file_count": len(runtime_file_counts),
            "requires_review_count": requires_review_count,
            "runtime_scan_clear": (
                len(runtime_findings) == 0 and requires_review_count == 0
            ),
            "top_files": [
                {"path": path, "finding_count": count}
                for path, count in sorted(
                    file_counts.items(),
                    key=lambda item: (-item[1], item[0]),
                )[:25]
            ],
            "runtime_top_files": [
                {"path": path, "finding_count": count}
                for path, count in sorted(
                    runtime_file_counts.items(),
                    key=lambda item: (-item[1], item[0]),
                )[:25]
            ],
        },
        "gates": {
            "foundation_contract_present": (
                root.joinpath("docs", "EMPIRE_DATA_CLOUD_ARCHITECTURE.md").exists()
            ),
            "foundation_contract_verified": bool(foundation_contract_verified),
            "postgres_runtime_verified": False,
            "schema_compatibility_verified": False,
            "backup_restore_verified": False,
            "migration_copy_verified": False,
            "production_cutover_approved": False,
        },
        "authority": {
            "package_install": False,
            "service_mutation": False,
            "database_mutation": False,
            "schema_mutation": False,
            "production_cutover": False,
        },
    }


def compact_readiness_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    host = snapshot["host"]
    inventory = snapshot["dependency_inventory"]
    observed = host["host"]
    gib = 1024 ** 3
    return {
        "capacity_ready": host["capacity_ready"],
        "cpu_count": observed["cpu_count"],
        "memory_gib": round(observed["memory_bytes"] / gib, 2),
        "disk_free_gib": round(observed["disk_free_bytes"] / gib, 2),
        "missing_packages": host["missing_packages"],
        "runtime_vendor_findings": inventory["runtime_finding_count"],
        "runtime_vendor_files": inventory["runtime_file_count"],
        "requires_review": inventory["requires_review_count"],
        "runtime_scan_clear": inventory["runtime_scan_clear"],
        "runtime_top_files": inventory["runtime_top_files"][:10],
    }


def main() -> int:
    snapshot = build_readiness_snapshot(Path.cwd())
    if "--full-json" in sys.argv[1:]:
        payload = snapshot
    else:
        payload = compact_readiness_snapshot(snapshot)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
