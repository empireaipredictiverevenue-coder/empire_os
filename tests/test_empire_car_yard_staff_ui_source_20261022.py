"""Staging-only staff workbench source contract; not a WordPress runtime test."""
from pathlib import Path
import shutil
import subprocess
import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "prototypes/agency_wordpress_service_handoff_20261022/empire-car-yard"
MAIN = (SOURCE / "empire-car-yard.php").read_text()
UI = SOURCE / "includes/class-empire-yard-staff-ui.php"
STORE = (SOURCE / "includes/class-empire-yard-booking-store.php").read_text()

def test_feature_flag_disables_admin_hooks_by_default():
    assert "EMPIRE_YARD_STAGING_STAFF_UI_ENABLED === true && is_admin()" in MAIN
    assert "require_once __DIR__ . '/includes/class-empire-yard-staff-ui.php';" in MAIN
    assert "register_activation_hook" not in MAIN
    assert "admin_post_" not in MAIN
    assert "register_rest_route" not in MAIN
    assert "wp_mail(" not in MAIN

def test_protected_staff_actions_and_no_public_forms():
    src = UI.read_text()
    assert "EMPIRE_YARD_STAGING_STAFF_UI_ENABLED !== true" in src
    assert "current_user_can('manage_options')" in src
    assert "get_current_user_id() <= 0" in src
    assert "admin_post_empire_yard_staff_hold" in src
    assert "admin_post_empire_yard_staff_transition" in src
    assert "admin_post_nopriv" not in src
    assert "check_admin_referer('empire_yard_staff_hold')" in src
    assert "check_admin_referer('empire_yard_staff_transition_' . $id)" in src
    assert "wp_nonce_field('empire_yard_staff_hold')" in src
    assert "wp_nonce_field('empire_yard_staff_transition_' . $id)" in src
    assert "wp_safe_redirect(" in src
    assert "private static function calendar_ready(array $calendar): bool" in src
    assert "if (!self::calendar_ready(self::calendar()) || !self::store()->ready())" in src
    assert "if (!self::calendar_ready($calendar) || !self::store()->ready())" in src
    assert "wp_mail(" not in src
    assert "wp_insert_post(" not in src
    assert "register_rest_route" not in src

def test_db_readiness_enforces_innodb_and_exact_unique_index():
    assert "information_schema.STATISTICS" in STORE
    assert "INDEX_NAME = 'bay_slot' AND NON_UNIQUE = 0" in STORE
    assert "=== 'bay,slot_utc'" not in STORE
    assert "!== 'bay,slot_utc'" in STORE
    assert "public function ready(): bool" in STORE
    assert "public function recent(int $limit = 30): array" in STORE
    assert "min($limit, 50)" in STORE
    assert "FROM {$this->bookings()} ORDER BY id DESC LIMIT %d" in STORE

def test_php_cli_syntax_and_shim_if_available():
    php = shutil.which("php")
    if php is None:
        pytest.skip("No PHP CLI on connected server; PHP and real WP tests pending")
    for rel in ["empire-car-yard.php", "includes/class-empire-yard-booking-rules.php",
                "includes/class-empire-yard-booking-store.php",
                "includes/class-empire-yard-staff-ui.php"]:
        result = subprocess.run([php, "-l", str(SOURCE / rel)], capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr
    result = subprocess.run([php, str(ROOT / "tests/verify_empire_car_yard_store_php_20261022.php")],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "EMPIRE_CAR_YARD_STAFF_STORAGE_SHIM_PASS" in result.stdout
