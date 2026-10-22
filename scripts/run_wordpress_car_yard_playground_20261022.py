"""Execute real WordPress 6.8 / PHP 8.3 integration, offline from production.

Uses official Node-based WordPress Playground in a disposable PHP/WASM +
SQLite sandbox; mounts only this isolated worktree's theme, plugin and test.
No Docker, global PHP, production credentials, CRM, mail or customer data.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/"prototypes/agency_wordpress_service_handoff_20261022"
THEME=BASE/"empire-local-services"
PLUGIN=BASE/"empire-car-yard-private"
TEST=ROOT/"scripts/wordpress_e2e"
RESEARCH=ROOT/"docs/commercial/JEV_DIRECT_B2B_PURCHASE_NEED_PRIORITY_20261022.json"
OUTPUT=ROOT/"docs/commercial/JEV_WORDPRESS_REAL_PHP_CAR_YARD_RUNTIME_20261022.json"
REQUIRED=(
    "wp_vehicle_registered","wp_repair_registered","wp_vehicle_nonpublic",
    "wp_repair_nonpublic","wordpress_theme_discovered","wordpress_theme_activated",
    "anonymous_permission_denied","anonymous_inventory_rest_denied",
    "anonymous_book_rest_denied","admin_permission_allowed",
    "fictional_editor_created","editor_role_lacks_admin_authority",
    "editor_cannot_create_private_vehicle","editor_cannot_view_private_vehicle_api",
    "synthetic_vehicle_persisted","private_inventory_rest_200",
    "vehicle_inventory_contains_one","vehicle_meta_year_roundtrip",
    "vehicle_stock_status_roundtrip","sydney_daylight_time_valid",
    "incorrect_sydney_offset_rejected","out_of_hours_rejected",
    "invalid_calendar_date_rejected","past_booking_rejected",
    "short_slot_rejected","synthetic_booking_created_201",
    "synthetic_booking_wp_post_persisted","overlap_conflict_409",
    "adjacent_nonoverlap_created","staff_cancel_rest_200",
    "cancelled_status_persisted","cancelled_slot_can_be_reallocated",
    "booking_lock_released","concurrent_booking_lock_blocks_second_request",
)


def sha(path:Path)->str:
    if path.is_symlink() or not path.is_file() or path.stat().st_size>500000:
        raise ValueError("unsafe local source path")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_payload(payload:dict)->dict:
    if not isinstance(payload,dict):
        raise ValueError("Playground runtime gave no structured integration report")
    if (payload.get("status")!="WORDPRESS_PLAYGROUND_REAL_INTEGRATION_PASS"
        or not re.fullmatch(r"6\.8\.\d+",str(payload.get("wordpress_version","")))
        or not re.fullmatch(r"8\.3\.\d+",str(payload.get("php_version","")))
        or payload.get("theme_activated")!="empire-local-services"
        or payload.get("public_customer_bookings_allowed") is not False
        or payload.get("public_contact_collection_allowed") is not False
        or payload.get("customer_deliveries")!=0
        or payload.get("crm_writes") is not False
        or payload.get("production_changes") is not False
        or payload.get("all_data_synthetic") is not True):
        raise ValueError("untrusted WordPress integration result or customer delivery claim")
    checks=payload.get("checks")
    if (not isinstance(checks,dict) or len(checks)<len(REQUIRED)
        or any(checks.get(name) is not True for name in REQUIRED)
        or payload.get("wordpress_checks_passed")!=len(checks)
        or any(type(x) is not bool or x is not True for x in checks.values())):
        raise ValueError("some required real WordPress runtime checks did not pass")
    return payload


def extract_runtime_json(output:str)->dict:
    # On success the PHP test emits exactly one structured result. The
    # parser never interprets WordPress's HTML fatal-error page as a pass.
    marker='"status": "WORDPRESS_PLAYGROUND_REAL_INTEGRATION_PASS"'
    start=output.find('{\n    '+marker)
    if start < 0:
        start=output.find('{"status":')
    if start < 0:
        raise ValueError("missing PHP-created successful integration result")
    try:
        payload,_end=json.JSONDecoder().raw_decode(output[start:])
    except (json.JSONDecodeError,TypeError) as exc:
        raise ValueError("malformed PHP runtime evidence") from exc
    return validate_payload(payload)


def run()->dict:
    original=json.loads(RESEARCH.read_text())
    if (original.get("schema_version")!="empire.jev.direct_b2b_buying_need_review.v1"
        or original.get("verified_business_buyers")!=0
        or original.get("live_bids_submitted")!=0
        or original.get("outbound_sent")!=0
        or original.get("execution_authority")!="none"):
        raise ValueError("commercial research source is not held")
    filenames=(
        THEME/"theme.json", THEME/"style.css", PLUGIN/"empire-car-yard-private.php",
        TEST/"probe.php", TEST/"integration.php", RESEARCH,
    )
    hashes={str(path.relative_to(ROOT)):sha(path) for path in filenames}
    command=[
        "npx","--yes","@wp-playground/cli@3.1.60","php",
        "--wp=6.8","--php=8.3",
        f"--mount={THEME}:/wordpress/wp-content/themes/empire-local-services",
        f"--mount={PLUGIN}:/wordpress/wp-content/plugins/empire-car-yard-private",
        f"--mount={TEST}:/wordpress/wp-content/empire-e2e",
        "--","/wordpress/wp-content/empire-e2e/integration.php",
    ]
    # 'php' begins with a clean WordPress install, including a disposable
    # SQLite backing store and generated test users; no exposed listener.
    try:
        completed=subprocess.run(command,cwd=ROOT,check=False,
                                 stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                                 text=True,timeout=140)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("bounded isolated WordPress Playground run timed out") from exc
    if completed.returncode!=0:
        raise RuntimeError("isolated WordPress integration failed, exit "+str(completed.returncode))
    result=extract_runtime_json(completed.stdout)
    if (any(sha(ROOT/path)!=hash_value for path,hash_value in hashes.items())):
        raise ValueError("source changed during WordPress integration run")
    return {
        "schema_version":"empire.agency.wordpress_car_yard_real_runtime.v1",
        "status":"REAL_WORDPRESS_PHP_ADMIN_ONLY_E2E_PASS_CLIENT_DELIVERY_HELD",
        "observed_at_utc":datetime.now(timezone.utc).isoformat(),
        "platform":"OFFICIAL_WORDPRESS_PLAYGROUND_CLI_DISPOSABLE_PHP_WASM_SQLITE",
        "playground_cli_pinned_version":"3.1.60",
        "wordpress_version":result["wordpress_version"],
        "php_version":result["php_version"],
        "theme_activated":result["theme_activated"],
        "wordpress_runtime_checks_passed":result["wordpress_checks_passed"],
        "runtime_checks":result["checks"],
        "source_sha256":dict(sorted(hashes.items())),
        "actual_real_wordpress_bootstrap_executed":True,
        "private_rest_inventory_persisted_in_disposable_database":True,
        "private_rest_repair_bookings_persisted_in_disposable_database":True,
        "synthetic_conflict_cancellation_and_lock_tested":True,
        "browser_site_editor_mobile_rendering_tested":False,
        "real_production_mysql_concurrency_tested":False,
        "public_customer_booking_flow_enabled":False,
        "email_transport_and_payment_enabled":False,
        "actual_customer_vehicles_or_contacts_processed":0,
        "contractor_terms_and_bid_approved":False,
        "live_client_handover_tested":False,
        "accepted_revenue_verified":False,
        "crm_writes":False,
        "production_files_or_empiredb_modified":False,
        "execution_authority":"none",
    }


def main()->None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--run-disposable-read-only-production",required=True,action="store_true")
    parser.parse_args()
    if OUTPUT.exists() or OUTPUT.is_symlink():
        raise ValueError("refusing to overwrite original WordPress runtime receipt")
    result=run()
    with OUTPUT.open("x",encoding="utf8") as f:
        json.dump(result,f,sort_keys=True,indent=2)
        f.write("\n")
    print(json.dumps({
        "status":result["status"],
        "wordpress":result["wordpress_version"],
        "php":result["php_version"],
        "runtime_checks":result["wordpress_runtime_checks_passed"],
        "production_changed":result["production_files_or_empiredb_modified"],
        "client_delivery_approved":result["live_client_handover_tested"],
    },sort_keys=True))


if __name__=="__main__":
    main()
