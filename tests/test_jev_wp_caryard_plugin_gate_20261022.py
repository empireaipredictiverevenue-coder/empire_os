"""Source-only WP car-yard gating and independent SQL uniqueness model."""
from __future__ import annotations

from pathlib import Path
import json
from copy import deepcopy
from hashlib import sha256
import shutil
import pytest

from empire_os.jev_wp_caryard_plugin_gate import (
    review_wp_caryard_plugin, sql_unique_slot_reference_test, REQUIRED
)
from scripts.package_agency_wp_caryard_plugin_20261022 import make_offline_zip

ROOT=Path(__file__).resolve().parents[1]
PLUGIN=ROOT/"prototypes/agency_wordpress_service_handoff_20261022/plugins/empire-caryard-gated"
PARENT=ROOT/"docs/commercial/JEV_WORDPRESS_SERVICE_HANDOVER_PREFLIGHT_20261022.json"
RECEIPT=ROOT/"docs/commercial/JEV_CARYARD_INVENTORY_BOOKING_STATIC_PREFLIGHT_20261022.json"
VEHICLE="includes/class-eacy-vehicles.php"
SLOTS="includes/class-eacy-repair-slots.php"


def parent():
    return json.loads(PARENT.read_text())


def review(root=None,source=None):
    return review_wp_caryard_plugin(
        PLUGIN if root is None else root,
        source_review=parent() if source is None else source
    )


def staged(tmp_path):
    p=tmp_path/"safe-plugin"
    shutil.copytree(PLUGIN,p)
    return p


def test_review_never_claims_wordpress_runtime_or_public_booking():
    r=review()
    assert r["schema_version"]=="empire.jev.wp_caryard_inventory_booking_gate.v1"
    assert r["status"]=="WP_CARYARD_PLUGIN_STATIC_GATES_PASS_RUNTIME_INTEGRATION_REQUIRED"
    assert r["source_files_checked"]==3
    assert r["vehicle_post_type_and_editor_meta_source_present"] is True
    assert r["vehicle_display_source_present"] is True
    assert r["booking_conflict_unique_key_source_present"] is True
    assert r["booking_admin_permission_source_present"] is True
    assert r["public_booking_api_source_present"] is False
    assert r["actual_wordpress_php_and_mysql_semantics_tested"] is False
    assert r["wp_admin_vehicle_crud_tested"] is False
    assert r["public_customer_booking_or_calendar_implemented"] is False
    assert r["owner_opt_in_required_on_disposable_wp_instance"] is True
    assert r["outbound_sent"]==0
    assert r["database_writes"] is False
    assert r["execution_authority"]=="none"


@pytest.mark.parametrize("attempts",[2,5,10,20])
def test_conflicting_slot_reference_accepts_one_admin_hold(attempts):
    a=sql_unique_slot_reference_test(attempts=attempts)
    assert a=={
        "attempts":attempts,
        "successful_slot_holds":1,
        "duplicate_or_conflicting_holds_rejected":attempts-1,
        "rows_after_race":1,
    }


@pytest.mark.parametrize("remove",[
    "empire-caryard-gated.php",VEHICLE,SLOTS,
])
def test_plugin_missing_source_blocks(tmp_path,remove):
    target=staged(tmp_path)
    (target/remove).unlink()
    with pytest.raises(ValueError):
        review(root=target)


@pytest.mark.parametrize("field,old,new",[
    (SLOTS,"UNIQUE KEY unique_slot_start (slot_start_utc)","KEY slot_start (slot_start_utc)"),
    (SLOTS,"INSERT IGNORE INTO","INSERT INTO"),
    (SLOTS,"current_user_can( 'manage_options' )","is_user_logged_in()"),
    (SLOTS,"'permission_callback' => array( __CLASS__, 'can_test_slot' )","'permission_callback' => '__return_true'"),
    (SLOTS,"EACY_DEMO_ADMIN_SLOT_TEST_ENABLED === true","EACY_DEMO_ADMIN_SLOT_TEST_ENABLED !== false"),
    (SLOTS,"'customer_booking_accepted' => false","'customer_booking_accepted' => true"),
    (SLOTS,"'status' => 409","'status' => 200"),
    (VEHICLE,"'posts_per_page' => 12","'posts_per_page' => -1"),
    (VEHICLE,"'post_status' => 'publish'","'post_status' => 'any'"),
    (VEHICLE,"esc_html( get_the_title(","get_the_title("),
])
def test_gates_cannot_be_removed_or_weakened(tmp_path,field,old,new):
    target=staged(tmp_path)
    file=target/field
    data=file.read_text()
    assert old in data
    file.write_text(data.replace(old,new,1))
    with pytest.raises(ValueError):
        review(root=target)


def test_no_real_person_email_fields_in_php_or_plugin_rest_api():
    for relative in REQUIRED:
        src=(PLUGIN/relative).read_text()
        assert "$_POST" not in src
        assert "wp_mail(" not in src
        assert "contact_email" not in src
        assert "customer_email" not in src
    vehicle=(PLUGIN/VEHICLE).read_text()
    assert vehicle.count("register_post_meta(")==3
    assert "FILTER_VALIDATE_INT" in vehicle
    assert "absint( $value )" not in vehicle
    slots=(PLUGIN/SLOTS).read_text()
    assert slots.count("register_rest_route(")==2
    assert "'/admin-slot-hold'" in slots
    assert "'/admin-slot-count'" in slots


def test_independent_aggregate_evidence_cannot_be_upgraded_to_live_sale():
    p=parent()
    p["commercial_proposals_ready"]=1
    with pytest.raises(ValueError):
        review(source=p)


def test_review_receipt_sha_and_zero_production_claims():
    r=json.loads(RECEIPT.read_text())
    assert r["source_files_checked"]==3
    assert r["parent_wordpress_theme_static_review_sha256"]==sha256(PARENT.read_bytes()).hexdigest()
    assert r["actual_wordpress_php_and_mysql_semantics_tested"] is False
    assert r["php_parser_or_php_lint_executed"] is False
    assert r["plugin_installation_performed"] is False
    assert r["plugin_activation_or_schema_migration_performed"] is False
    assert r["production_inventory_or_booking_activated"] is False
    assert r["commercial_offer_ready"] is False
    assert r["contacts_collected"]==0
    assert r["customer_contact_fields_requested"]==0
    assert r["crm_writes"] is False
    assert r["outbound_sent"]==0
    assert r["database_writes"] is False
    assert r["execution_authority"]=="none"
    for name,digest in r["plugin_source_sha256"].items():
        assert sha256((PLUGIN/name).read_bytes()).hexdigest()==digest


def test_offline_plugin_zip_is_exact_and_reproducible(tmp_path):
    from zipfile import ZipFile
    x=make_offline_zip(destination=tmp_path/"a.zip")
    y=make_offline_zip(destination=tmp_path/"b.zip")
    assert x["status"]=="WORDPRESS_CARYARD_PLUGIN_OFFLINE_SOURCE_PACKAGE_ONLY"
    assert x["file_count"]==4
    assert x["zip_sha256"]==y["zip_sha256"]
    assert x["zip_sha256"]==sha256((tmp_path/"a.zip").read_bytes()).hexdigest()
    assert x["wordpress_runtime_tested"] is False
    assert x["plugin_installed_or_activated"] is False
    assert x["production_changes"] is False
    with ZipFile(tmp_path/"a.zip") as z:
        assert set(z.namelist())=={
            "empire-caryard-gated/"+n for n in
            (REQUIRED|{"README.md"})
        }


def test_plugin_zip_does_not_silently_overwrite(tmp_path):
    path=tmp_path/"single.zip"
    make_offline_zip(destination=path)
    with pytest.raises(ValueError,match="overwrite"):
        make_offline_zip(destination=path)
