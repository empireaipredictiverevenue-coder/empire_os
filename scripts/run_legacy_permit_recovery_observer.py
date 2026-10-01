#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from empire_os.legacy_permit_recovery import (
    refresh_legacy_permit_recovery_observer,
)
from empire_os.legacy_permit_inventory import update_cumulative_inventory
import os
from datetime import datetime, timezone
from pathlib import Path


def main() -> int:
    backend = os.getenv(
        "EMPIRE_DATA_BACKEND",
        "",
    ).strip().lower()

    if backend == "empiredb":
        payload = {
            "schema_version": (
                "empire.legacy-permit-recovery-runtime.v1"
            ),
            "observed_at": datetime.now(
                timezone.utc
            ).isoformat(),
            "mode": "OBSERVE",
            "state": "LEGACY_SOURCE_UNAVAILABLE",
            "canonical_backend": "empiredb",
            "source_store": (
                "legacy_supabase.public.lane_leads"
            ),
            "reason": (
                "lane_leads is retired legacy recovery state "
                "and is intentionally not materialized in EmpireDB"
            ),
            "database_write_performed": False,
            "canonical_promotion_performed": False,
            "outbound_sent": False,
            "commercial_terms_created": False,
            "actual_revenue": False,
            "execution_authority": "none",
        }

        status_path = Path(
            "/srv/empire_os/runtime/recovery/"
            "legacy_permit_recovery_runtime_status.json"
        )
        status_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        tmp = status_path.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(
                payload,
                indent=2,
                sort_keys=True,
            ) + "\n",
            encoding="utf-8",
        )
        tmp.replace(status_path)

        print(
            json.dumps(
                payload,
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="/srv/empire_os")
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--offset", type=int)
    args = parser.parse_args()

    payload = refresh_legacy_permit_recovery_observer(
        args.repo_root,
        batch_size=args.batch_size,
        offset=args.offset,
    )
    inventory = update_cumulative_inventory(
        args.repo_root,
        payload,
    )
    print(json.dumps({
        "ok": True,
        "mode": payload["mode"],
        "scanned_row_count": payload["scanned_row_count"],
        "processed_count": payload["processed_count"],
        "classification_counts": payload["classification_counts"],
        "recovery_state_counts": payload["recovery_state_counts"],
        "identity_match_counts": payload["identity_match_counts"],
        "source_owner_identity_counts": payload[
            "source_owner_identity_counts"
        ],
        "source_permittee_phone_counts": payload[
            "source_permittee_phone_counts"
        ],
        "inventory_identity_mode_counts": payload[
            "inventory_identity_mode_counts"
        ],
        "cumulative_unique_inventory": inventory[
            "unique_inventory_records"
        ],
        "cumulative_verified_current": inventory[
            "verified_current_inventory"
        ],
        "cumulative_owner_identified": inventory[
            "verified_current_owner_identified"
        ],
        "cumulative_project_only": inventory[
            "verified_current_project_only"
        ],
        "cumulative_full_scan_complete": inventory[
            "full_scan_complete"
        ],
        "next_offset": payload["next_offset"],
        "historical_omega_is_current_truth": payload[
            "historical_omega_is_current_truth"
        ],
        "database_write_performed": payload["database_write_performed"],
        "canonical_promotion_performed": payload[
            "canonical_promotion_performed"
        ],
        "outbound_sent": payload["outbound_sent"],
        "actual_revenue": payload["actual_revenue"],
        "execution_authority": payload["execution_authority"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
