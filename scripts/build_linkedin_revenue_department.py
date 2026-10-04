#!/usr/bin/env python3
"""Build the governed LinkedIn Revenue Department review snapshot."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from empire_os.linkedin_revenue_department import (
    refresh_linkedin_revenue_department,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="/srv/empire_os")
    args = parser.parse_args()

    payload = refresh_linkedin_revenue_department(
        Path(args.repo_root).resolve()
    )
    print(json.dumps({
        "ok": True,
        "mode": payload["mode"],
        "candidate_count": payload["candidate_count"],
        "observed_signal_candidate_count": payload[
            "observed_signal_candidate_count"
        ],
        "resolved_decision_maker_count": payload[
            "resolved_decision_maker_count"
        ],
        "verified_contact_count": payload["verified_contact_count"],
        "outreach_draft_count": payload["outreach_draft_count"],
        "human_review_ready_count": payload[
            "human_review_ready_count"
        ],
        "economic_value_available_count": payload[
            "economic_value_available_count"
        ],
        "predicted_expected_revenue_value_cents_total": payload[
            "predicted_expected_revenue_value_cents_total"
        ],
        "linkedin_automation_enabled": payload[
            "linkedin_automation_enabled"
        ],
        "live_outbound_enabled": payload["live_outbound_enabled"],
        "execution_authority": payload["execution_authority"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
