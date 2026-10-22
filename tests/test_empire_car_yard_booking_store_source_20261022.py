"""Security and reproducibility checks for dormant staff-booking storage."""
from pathlib import Path
import shutil
import subprocess
import pytest

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "prototypes/agency_wordpress_service_handoff_20261022/empire-car-yard"
MAIN = BASE / "empire-car-yard.php"
STORE = BASE / "includes/class-empire-yard-booking-store.php"
RULES = BASE / "includes/class-empire-yard-booking-rules.php"
HARNESS = ROOT / "tests/verify_empire_car_yard_store_php_20261022.php"

def test_dormant_code_has_no_unapproved_endpoint_or_automatic_schema_mutation():
    main = MAIN.read_text()
    assert "require_once __DIR__ . '/includes/class-empire-yard-booking-store.php';" in main
    assert "Booking persistence is dormant" in main
    assert "register_activation_hook" not in main
    assert "admin_post_" not in main
    assert "wp_ajax_" not in main
    assert "register_rest_route" not in main
    assert "wp_mail(" not in main

def test_booking_store_safety_contract():
    code = STORE.read_text()
    for required in ("current_user_can('manage_options')", "get_current_user_id()",
        "information_schema.TABLES", "ENGINE=InnoDB",
        "UNIQUE KEY bay_slot (bay,slot_utc)", "GET_LOCK(", "RELEASE_LOCK(",
        "START TRANSACTION", "COMMIT", "ROLLBACK",
        "blackout_dates", "previous_status", "actor_user",
        "Empire_Yard_Booking_Rules::slot", "booking_id"):
        assert required in code, required
    assert "$_POST" not in code and "$_GET" not in code
    assert "wp_mail(" not in code

def test_php_standalone_harness_only_when_php_cli_exists():
    php = shutil.which("php")
    if php is None:
        pytest.skip("EmpireOS PHP CLI absent; no live WordPress or PHP-run claim")
    for src in (MAIN, STORE, RULES, HARNESS):
        run = subprocess.run([php, "-l", str(src)], capture_output=True, text=True)
        assert run.returncode == 0, run.stdout + run.stderr
    run = subprocess.run([php, str(HARNESS)], capture_output=True, text=True)
    assert run.returncode == 0, run.stdout + run.stderr
    assert "EMPIRE_CAR_YARD_STAFF_STORAGE_SHIM_PASS" in run.stdout
