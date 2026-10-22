"""Run V0.3 through official disposable WordPress Playground PHP/WASM + SQLite.

No listener, Docker privilege, production databases, personal data, or outbound.
Evidence file is create-only; never overwrites earlier observations.
"""
from __future__ import annotations
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "prototypes/agency_wordpress_service_handoff_20261022"
THEME = BASE / "empire-local-services"
PLUGIN = BASE / "empire-car-yard"
TEST = ROOT / "scripts/wordpress_e2e_v03"
RECEIPT = ROOT / "docs/commercial/EMPIRE_CAR_YARD_V03_PLAYGROUND_RUNTIME_20261022.json"
SOURCES = [
    THEME / "style.css", THEME / "theme.json",
    PLUGIN / "empire-car-yard.php",
    PLUGIN / "includes/class-empire-yard-booking-rules.php",
    PLUGIN / "includes/class-empire-yard-booking-store.php",
    PLUGIN / "includes/class-empire-yard-staff-ui.php",
    TEST / "integration.php",
]

def manifest() -> dict[str, str]:
    hashes = {}
    for path in SOURCES:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 120_000:
            raise RuntimeError("Unsafe or missing isolated source: " + str(path))
        hashes[str(path.relative_to(ROOT))] = sha256(path.read_bytes()).hexdigest()
    return hashes

def run() -> dict:
    previous = manifest()
    command = [
        "npx", "--yes", "@wp-playground/cli@3.1.60", "php",
        "--wp=6.8", "--php=8.3",
        f"--mount={THEME}:/wordpress/wp-content/themes/empire-local-services",
        f"--mount={PLUGIN}:/wordpress/wp-content/plugins/empire-car-yard",
        f"--mount={TEST}:/wordpress/wp-content/empire-v03-e2e",
        "--", "/wordpress/wp-content/empire-v03-e2e/integration.php",
    ]
    completed = subprocess.run(command, cwd=ROOT, text=True,
                               capture_output=True, timeout=140, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"Playground real WP test failed ({completed.returncode}): "
                           + completed.stderr[-1000:] + completed.stdout[-1000:])
    marker = '{\n    "status": "EMPIRE_V03_WORDPRESS_REAL_PHP_PASS"'
    start = completed.stdout.find(marker)
    if start == -1:
        raise RuntimeError("No trusted PHP WordPress success payload: "
                           + completed.stdout[-900:])
    payload, _ = json.JSONDecoder().raw_decode(completed.stdout[start:])
    expected = {
        "plugin_activation_success", "plugin_active_wordpress", "wordpress_cpt_registered",
        "vehicle_nonpublic", "vehicle_private_rest_search", "theme_discovered",
        "theme_activated", "disposable_admin_exists", "anonymous_not_admin",
        "admin_authorised", "admin_vehicle_write_capability",
        "synthetic_editor_created", "editor_vehicle_write_denied",
        "vehicle_created_wordpress", "vehicle_year_roundtrip",
        "vehicle_status_roundtrip", "anonymous_inventory_demo_visible",
        "fictional_disclosure_present", "archived_hidden", "vehicle_detail_visible",
        "booking_store_loaded", "staff_ui_loaded", "staging_admin_hold_hook",
        "staging_admin_transition_hook", "anonymous_submission_hook_absent",
        "sqlite_innodb_gate_denied", "staff_screen_fail_closed_warning",
        "staff_form_hidden_without_mysql", "staff_no_unverified_db_query",
    }
    checks = payload.get("checks")
    if (not isinstance(checks, dict) or set(checks) != expected
        or any(value is not True for value in checks.values())
        or payload.get("count") != len(expected)
        or not re.fullmatch(r"6\.8\.\d+", str(payload.get("wordpress")))
        or not re.fullmatch(r"8\.3\.\d+", str(payload.get("php")))
        or payload.get("theme") != "empire-local-services"
        or payload.get("production_changes") is not False
        or payload.get("mysql_concurrency_tested") is not False
        or payload.get("browser_rendered") is not False):
        raise RuntimeError("Untrustworthy WordPress acceptance payload")
    if manifest() != previous:
        raise RuntimeError("Source changed while executing integration")
    return {
        "schema_version": "empire.agency.car_yard_v03_wordpress_playground.v1",
        "status": "WORDPRESS_V03_THEME_PLUGIN_RUNTIME_PASS_MYSQL_BROWSER_GATES_SEPARATE",
        "observed_utc": datetime.now(timezone.utc).isoformat(),
        "platform": "OFFICIAL_WORDPRESS_PLAYGROUND_3.1.60_DISPOSABLE_PHP_WASM_SQLITE",
        "wordpress": payload["wordpress"],
        "php": payload["php"],
        "wordpress_checks_passed": len(checks),
        "checks": checks,
        "source_sha256": previous,
        "actual_plugin_activated": True,
        "actual_theme_activated": True,
        "public_customer_booking_enabled": False,
        "mysql_concurrency_tested_in_this_run": False,
        "mysql_innodb_separate_test_required": True,
        "browser_site_editor_mobile_tested": False,
        "backup_restore_tested": False,
        "production_changes": False,
        "crm_or_customer_data_used": False,
        "payments_or_outbound_enabled": False,
    }

if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] != "--execute-disposable-wordpress":
        raise SystemExit("Explicit --execute-disposable-wordpress required")
    if RECEIPT.exists() or RECEIPT.is_symlink():
        raise SystemExit("Existing immutable real-runtime receipt; refusing overwrite")
    result = run()
    with RECEIPT.open("x", encoding="utf8") as f:
        json.dump(result, f, indent=2, sort_keys=True)
        f.write("\n")
    print(json.dumps({
        "status": result["status"], "checks": result["wordpress_checks_passed"],
        "wordpress": result["wordpress"], "php": result["php"],
        "prod_changed": result["production_changes"],
    }, sort_keys=True))
