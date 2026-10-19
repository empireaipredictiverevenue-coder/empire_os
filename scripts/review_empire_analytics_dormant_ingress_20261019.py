#!/usr/bin/env python3
"""Read-only operational review of the unmounted Empire Analytics intake."""
from __future__ import annotations

import argparse
import json

from empire_os.analytics.measurement_readiness import review_existing_monitor
from empire_os.analytics.dormant_event_ingress import PATH


def inspect() -> dict:
    static = review_existing_monitor()
    verified_static = static["status"] == "STATIC_HOMEPAGE_TAG_SOURCE_OBSERVED_COLLECTOR_HELD"
    # Source contract presence is not permission or proof of a deployed
    # public collector. Never inspect user session data or issue writes.
    return {
        "schema_version": "empire.analytics.intake_rollout_readiness.v1",
        "status": "DORMANT_HTTP_CONTRACT_READY_COLLECTION_NOT_AUTHORISED"
                  if verified_static else "HELD_TAG_INTELLIGENCE_MONITOR_UNVERIFIED",
        "mode": "READ_ONLY",
        "existing_tag_intelligence_observation": static["status"],
        "static_page_observation_verified": verified_static,
        "http_contract_source_present": True,
        "http_simulation_route": PATH,
        "http_simulation_requires_local_test_guard": True,
        "public_route_mounted_verified": False,
        "website_analytics_consent_verified": False,
        "server_side_session_issuer_verified": False,
        "acquisition_ledger_verified": False,
        "actual_website_sessions_verified": False,
        "customer_leads_verified": False,
        "crm_attribution_verified": False,
        "realised_revenue_verified": False,
        "tracking_pixels_added": False,
        "browser_collector_activated": False,
        "database_writes": False,
        "public_website_modified": False,
        "outbound_sent": False,
        "execution_authority": "NONE",
        "next_gate": "OWNER_AND_PRIVACY_APPROVAL_FOR_WEBSITE_ANALYTICS_CONSENT_DESIGN",
    }


def main(argv=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--read-only",action="store_true",required=True)
    parser.parse_args(argv)
    report=inspect()
    print(json.dumps(report,sort_keys=True))
    return 0 if report["status"]=="DORMANT_HTTP_CONTRACT_READY_COLLECTION_NOT_AUTHORISED" else 2


if __name__=="__main__":
    raise SystemExit(main())
