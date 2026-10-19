"""Read-only backup filename inventory for old LXD Twenty / Listmonk.

Run with sudo ONLY when the original volume recovery owner authorises a
metadata-only audit. Does not open archives, list private DB rows, print
environment variables, extract files, copy storage, or alter services.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path

SCHEMA = "empire.legacy_crm_lxd_backup_metadata.v1"
ROOTS = (
    Path("/var/snap/lxd/common/lxd/backups"),
    Path("/var/backups"),
)
MAX_SCANNED = 12000
MATCH = ("twenty", "listmonk", "lxd", "incus")


def inspect_backup_metadata(roots=ROOTS) -> dict:
    sources = []
    matches = []
    count = 0
    permission_holds = []
    for root in roots:
        if not root.is_dir() or root.is_symlink():
            sources.append({"root": str(root), "present": False})
            continue
        summary = {"root": str(root), "present": True,
                   "entries_seen": 0, "archive_name_hits": 0}
        if not os.access(root, os.R_OK | os.X_OK):
            permission_holds.append(str(root))
            sources.append({**summary, "access": "OWNER_REQUIRED"})
            continue
        def onerror(exc):
            permission_holds.append(type(exc).__name__)
        for base, folders, files in os.walk(root, followlinks=False, onerror=onerror):
            relative = len(Path(base).relative_to(root).parts)
            if relative >= 5:
                folders[:] = []
            for name in folders + files:
                count += 1
                summary["entries_seen"] += 1
                if count > MAX_SCANNED:
                    return {
                        "schema_version": SCHEMA, "state": "HOLD_SCAN_BUDGET_EXCEEDED",
                        "original_database_restored": False,
                        "execution_authority": "none",
                    }
                if any(word in name.lower() for word in MATCH):
                    summary["archive_name_hits"] += 1
                    if len(matches) < 70:
                        matches.append({"root": str(root),
                                        "matched_basename": name[:120],
                                        "directory": name in folders})
        sources.append(summary)
    return {
        "schema_version": SCHEMA,
        "state": ("PARTIAL_OWNER_ACCESS_REQUIRED" if permission_holds
                  else "BACKUP_NAMES_REVIEWED_NO_CONTENT_VERIFICATION"),
        "owner_access_gaps": len(permission_holds),
        "sources": sources,
        "matched_names": matches,
        "old_db_backup_content_verified": False,
        "old_twenty_workspace_verified": False,
        "old_listmonk_subscribers_verified": False,
        "restoration_authorized": False,
        "services_started": False,
        "database_writes": False,
        "email_sent": False,
        "execution_authority": "none",
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--read-only", action="store_true", required=True)
    p.parse_args(argv)
    print(json.dumps(inspect_backup_metadata(), sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
