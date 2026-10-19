"""Operator-only source-epoch check; strictly no producer writes."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from empire_os.flagship_source_epoch_reconciliation import (
    review_source_epoch_reconciliation_runtime,
)
from empire_os.flagship_first_payer_owner_handoff import (
    review_current_first_payer_owner_handoff,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Existing four-stage evidence freshness check")
    parser.add_argument("--read-only", action="store_true", required=True)
    parser.add_argument("--repo-root", type=Path, default=Path("/srv/empire_os"))
    options = parser.parse_args()
    now = datetime.now(timezone.utc)
    epoch = review_source_epoch_reconciliation_runtime(options.repo_root, as_of=now)
    owner = review_current_first_payer_owner_handoff(options.repo_root, as_of=now)
    payload = {
        "schema_version": "empire.flagship.source_epoch_operator_readonly.v1",
        "mode": "OBSERVE",
        "epoch": epoch,
        "owner_status": owner["status"],
        "owner_first_priority": owner["first_priority_owner"],
        "owner_first_action": owner["first_priority_action"],
        "opportunity_ref": owner["opaque_opportunity_ref"],
        "forecasts_issued": False,
        "producer_snapshots_modified": False,
        "database_writes": False,
        "emails_sent": False,
        "payments_moved": False,
    }
    print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    main()
