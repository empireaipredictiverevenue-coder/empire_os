#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from empire_os.legacy_permit_recovery import (
    refresh_legacy_permit_recovery_observer,
)
from empire_os.legacy_permit_inventory import update_cumulative_inventory


def main() -> int:
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
