"""Real WordPress Playground E2E evidence is independently pinned and fail-closed."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import pytest

from scripts.run_wordpress_car_yard_playground_20261022 import (
    ROOT,THEME,PLUGIN,TEST,OUTPUT,REQUIRED,extract_runtime_json,
    validate_payload,
)

PLUGIN_PHP=PLUGIN/"empire-car-yard-private.php"


def report():
    return json.loads(OUTPUT.read_text())


def evidence():
    r=report()
    return {
        "status":"WORDPRESS_PLAYGROUND_REAL_INTEGRATION_PASS",
        "wordpress_version":r["wordpress_version"],
        "php_version":r["php_version"],
        "theme_activated":r["theme_activated"],
        "wordpress_checks_passed":r["wordpress_runtime_checks_passed"],
        "checks":r["runtime_checks"],
        "all_data_synthetic":True,
        "public_customer_bookings_allowed":False,
        "public_contact_collection_allowed":False,
        "customer_deliveries":0,
        "crm_writes":False,
        "production_changes":False,
    }


def test_integration_proves_actual_wordpress_php_runtime_not_static_mock():
    result=report()
    assert result["status"]=="REAL_WORDPRESS_PHP_ADMIN_ONLY_E2E_PASS_CLIENT_DELIVERY_HELD"
    assert result["wordpress_version"]=="6.8.11"
    assert result["php_version"]=="8.3.33"
    assert result["platform"]=="OFFICIAL_WORDPRESS_PLAYGROUND_CLI_DISPOSABLE_PHP_WASM_SQLITE"
    assert result["playground_cli_pinned_version"]=="3.1.60"
    assert result["wordpress_runtime_checks_passed"]>=36
    assert all(result["runtime_checks"].get(n) is True for n in REQUIRED)
    assert result["actual_real_wordpress_bootstrap_executed"] is True


def test_true_admin_inventory_crud_and_rest_controls_tested_in_php():
    checks=report()["runtime_checks"]
    for key in (
        "wp_vehicle_registered","wp_repair_registered","wp_vehicle_nonpublic",
        "wp_repair_nonpublic","repair_cpt_rest_disabled",
        "anonymous_permission_denied","anonymous_inventory_rest_denied",
        "anonymous_book_rest_denied","admin_permission_allowed",
        "fictional_editor_created","editor_role_lacks_admin_authority",
        "editor_cannot_create_private_vehicle","editor_cannot_view_private_vehicle_api",
        "synthetic_vehicle_persisted","private_inventory_rest_200",
        "vehicle_inventory_contains_one","vehicle_meta_year_roundtrip",
        "vehicle_stock_status_roundtrip",
    ):
        assert checks[key] is True


def test_actual_timezone_conflict_cancel_and_lock_e2e_executed():
    result=report()
    assert result["private_rest_repair_bookings_persisted_in_disposable_database"] is True
    for key in (
        "sydney_daylight_time_valid","incorrect_sydney_offset_rejected",
        "out_of_hours_rejected","invalid_calendar_date_rejected",
        "past_booking_rejected","short_slot_rejected",
        "synthetic_booking_created_201",
        "synthetic_booking_wp_post_persisted",
        "overlap_conflict_409","adjacent_nonoverlap_created",
        "staff_cancel_rest_200","cancelled_status_persisted",
        "cancelled_slot_can_be_reallocated","booking_lock_released",
        "concurrent_booking_lock_blocks_second_request",
    ):
        assert result["runtime_checks"][key] is True


def test_no_live_clients_forms_money_or_site_deployment():
    result=report()
    for name in (
        "browser_site_editor_mobile_rendering_tested",
        "real_production_mysql_concurrency_tested",
        "public_customer_booking_flow_enabled",
        "email_transport_and_payment_enabled","contractor_terms_and_bid_approved",
        "live_client_handover_tested","accepted_revenue_verified","crm_writes",
        "production_files_or_empiredb_modified",
    ):
        assert result[name] is False
    assert result["actual_customer_vehicles_or_contacts_processed"]==0
    assert result["execution_authority"]=="none"


def test_runtime_plugin_and_test_pinned_to_original_sha256():
    result=report()
    assert len(result["source_sha256"])==6
    for rel,digest in result["source_sha256"].items():
        path=ROOT/rel
        assert path.exists() and path.is_file()
        assert sha256(path.read_bytes()).hexdigest()==digest


def test_original_wordpress_theme_activated_not_substituted():
    result=report()
    assert result["theme_activated"]=="empire-local-services"
    assert result["runtime_checks"]["wordpress_theme_discovered"] is True
    assert result["runtime_checks"]["wordpress_theme_activated"] is True
    assert (THEME/"theme.json").is_file()


@pytest.mark.parametrize("key,value",[
    ("status","BUILT_WORDPRESS_CUSTOMER_DELIVERY"),
    ("wordpress_version","6.0.0"),
    ("php_version","7.4.33"),
    ("theme_activated","unknown-theme"),
    ("public_customer_bookings_allowed",True),
    ("public_contact_collection_allowed",True),
    ("customer_deliveries",1),
    ("crm_writes",True),("production_changes",True),
    ("all_data_synthetic",False),
])
def test_changed_runtime_evidence_cannot_claim_customer_delivery(key,value):
    data=evidence()
    data[key]=value
    with pytest.raises(ValueError):
        validate_payload(data)


def test_omitted_or_failed_runtime_check_cannot_be_called_pass():
    data=evidence()
    data["checks"]["overlap_conflict_409"]=False
    with pytest.raises(ValueError):
        validate_payload(data)
    data=evidence()
    del data["checks"]["anonymous_book_rest_denied"]
    with pytest.raises(ValueError):
        validate_payload(data)


def test_unstructured_or_html_php_fatal_is_not_a_successful_test():
    with pytest.raises(ValueError):
        extract_runtime_json('<html>There has been a critical error</html>')
    with pytest.raises(ValueError):
        extract_runtime_json('{"status": "NOT_VERIFIED"}')


def test_published_receipt_success_parsed_exactly():
    data=evidence()
    original='{"status":'+json.dumps(data)[len('{"status":'):]
    assert extract_runtime_json(original)==data


def test_admin_only_wordpress_meta_permissions_and_booking_shutdown_switch():
    body=PLUGIN_PHP.read_text()
    assert "current_user_can( 'manage_options' )" in body
    assert "'capabilities'        => empire_car_yard_admin_capabilities()" in body
    assert "EMPIRE_CAR_YARD_SYNTHETIC_TEST" in body
    assert "'public'              => false" in body
    assert "'show_in_rest'        => false" in body
    assert "add_option( $lock" in body
    assert "finally {" in body
    assert "delete_option( $lock )" in body
    assert "register_rest_route" in body
    assert "email" not in body.lower().replace("no public booking, payment, mail or contact collection.","")


def test_wordpress_meta_price_uses_multiarity_sanitizer_not_raw_builtin():
    body=PLUGIN_PHP.read_text()
    assert "function empire_car_yard_sanitize_price( $value, $meta_key = null" in body
    assert "'sanitize_callback' => 'empire_car_yard_sanitize_price'" in body
    assert "'sanitize_callback' => 'floatval'" not in body


def test_development_php_files_contain_only_synthetic_data_and_private_scope():
    probe=(TEST/"probe.php").read_text()
    full=(TEST/"integration.php").read_text()
    assert "require_once '/wordpress/wp-load.php'" in probe
    assert "require_once '/wordpress/wp-load.php'" in full
    assert "FICTIONAL" in full or "SYNTHETIC" in full
    assert "EMPIRE_CAR_YARD_SYNTHETIC_TEST" in full
    assert "wordpress_checks_passed" in full
    assert "actual_customer_contact" not in full
