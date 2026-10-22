#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from empire_os.adaptive_outreach_optimizer import load_snapshot
from empire_os.gtm_pipeline_worker import run_gtm_pipeline
from empire_os.gtm_integration_observer import observe_gtm_integration
from empire_os.sb import request_json
def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=25)
    args = parser.parse_args()
    cap = int(os.getenv("EMPIRE_GTM_DAILY_EXTERNAL_CAP", "25"))
    result = run_gtm_pipeline(
        request_json,
        limit=args.limit,
        daily_cap=cap,
        optimizer_snapshot=load_snapshot(),
    )
    payload = result.as_dict()
    payload["ok"] = not payload["proposal_errors"]
    review_path = Path(
        "/srv/empire_os/runtime/gtm_pipeline/"
        "founder_review_required_latest.json"
    )
    review_path.parent.mkdir(parents=True, exist_ok=True)
    review_payload = {
        "schema_version": "empire.gtm-founder-review-required.v1",
        "count": len(payload["founder_review_required"]),
        "items": payload["founder_review_required"],
        "founder_gate_required": bool(
            payload["founder_review_required"]
        ),
        "outbound_authorized": False,
        "execution_authority": "none",
    }
    tmp = review_path.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(review_payload, indent=2, sort_keys=True) + "\n"
    )
    tmp.replace(review_path)
    # Reuse this existing GTM cadence: observe canonical cross-product market
    # evidence and ask the existing GTM Agent for its next decision. No other
    # service/timer is installed, and this adapter cannot send or mutate data.
    try:
        observation = observe_gtm_integration(Path(__file__).resolve().parents[1])
        payload["gtm_integration_observer"] = {
            "agent_id": observation["agent_id"],
            "internal_research_review_count": observation["internal_research_review_count"],
            "held_candidate_count": observation["held_candidate_count"],
            "execution_authority": "none",
        }
    except Exception as exc:
        # A missing/invalid observational feed must not make the governed
        # buyer-review worker fail or grant any downstream authority.
        payload["gtm_integration_observer"] = {
            "status": "HOLD",
            "reason": type(exc).__name__,
            "execution_authority": "none",
        }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
