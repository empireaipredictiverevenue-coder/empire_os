"""One-shot static WordPress theme readiness review for two public offers.

No WordPress/PHP runtime, app submission, deployment, contact form,
buyer outreach, CRM entries or payment authorization is implied.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

from empire_os.jev_wp_delivery_capability import review_wordpress_delivery

THEME=Path("prototypes/agency_wordpress_service_handoff_20261022/empire-local-services")
RESEARCH=Path("docs/commercial/JEV_DIRECT_B2B_PURCHASE_NEED_PRIORITY_20261022.json")
OUTPUT=Path("docs/commercial/JEV_WORDPRESS_SERVICE_HANDOVER_PREFLIGHT_20261022.json")


def run()->dict:
    root=Path(__file__).resolve().parents[1]
    source=root/RESEARCH
    if source.is_symlink() or not source.is_file() or source.stat().st_size>200000:
        raise ValueError("original buyer research receipt unavailable")
    raw=source.read_bytes()
    research=json.loads(raw)
    result=review_wordpress_delivery(root/THEME,research=research)
    result["original_demand_receipt_sha256"]=sha256(raw).hexdigest()
    result["observed_at_utc"]=datetime.now(timezone.utc).isoformat()
    result["php_executable_observed_on_host"]=False
    result["docker_user_daemon_access_observed"]=False
    result["wordpress_run_or_browser_rendering_performed"]=False
    result["website_team_only_internal_source_package"]=True
    result["existing_empire_public_site_replaced"]=False
    return result


def main()->None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--read-only",action="store_true",required=True)
    parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    target=root/OUTPUT
    if target.exists() or target.is_symlink() or not target.parent.is_dir():
        raise ValueError("refuse overwrite of initial WordPress preflight evidence")
    report=run()
    with target.open("x",encoding="utf-8") as f:
        json.dump(report,f,sort_keys=True,indent=2)
        f.write("\n")
    print(json.dumps({
        "status":report["status"],
        "source_theme_files":report["theme_files_count"],
        "runtime_tested":report["wp_php_runtime_available_or_tested"],
        "car_inventory_booking":report["car_yard_complete_fulfilment_verified"],
        "agency_client_handover":report["agency_client_site_complete_fulfilment_verified"],
        "offers_ready":report["commercial_proposals_ready"],
        "production_changes":report["production_changes"],
    },sort_keys=True))


if __name__=="__main__":
    main()
