"""Prove plugin source gate safety; separate genuine WordPress smoke receipt."""
from __future__ import annotations

from pathlib import Path
from shutil import copytree
from hashlib import sha256
import json
import pytest

from empire_os.jev_car_yard_plugin_preflight import inspect_car_yard_private_plugin

ROOT=Path(__file__).resolve().parents[1]
PLUGIN=ROOT/"prototypes/agency_wordpress_service_handoff_20261022/empire-car-yard-internal"
SMOKE=ROOT/"docs/commercial/JEV_CAR_YARD_PLAYGROUND_RUNTIME_SMOKE_20261022.json"
BOOT="empire-car-yard-internal.php"
BOOK="includes/class-empire-yard-bookings.php"


def isolated(tmp_path):
    dest=tmp_path/"plugin"
    copytree(PLUGIN,dest)
    return dest


def modify(tmp_path,rel,old,new):
    dest=isolated(tmp_path)
    file=dest/rel
    s=file.read_text()
    assert old in s
    file.write_text(s.replace(old,new,1))
    return dest


def test_admin_only_inventory_storage_and_internal_scheduler_source():
    audit=inspect_car_yard_private_plugin(PLUGIN)
    assert audit["status"]=="PRIVATE_CAR_YARD_PHP_STATIC_PREFLIGHT_PASS_RUNTIME_REQUIRED"
    assert audit["admin_only_rest_permission_callbacks_checked"]==3
    assert audit["vehicle_inventory_admin_only_source_verified"] is True
    assert audit["transactional_slot_uniqueness_source_verified"] is True
    assert audit["vehicle_stock_status_enum_present"] is True
    assert audit["internal_booking_constant_default_false"] is True
    assert audit["source_php_linted_by_real_php"] is False
    assert audit["word_press_php_runtime_executed"] is False
    assert audit["real_mysql_innodb_overlap_tested"] is False
    assert audit["public_customer_booking_enabled"] is False
    assert audit["execution_authority"]=="none"


def test_disposable_reference_sqlite_canary_is_not_wordpress_proof():
    model=inspect_car_yard_private_plugin(PLUGIN)["reference_booking_sqlite_canary"]
    for field in (
        "fictional_held_booking_accepted","overlap_same_bay_rejected",
        "failed_hold_rolled_back","same_utc_slot_distinct_bay_allowed",
        "cancel_releases_claimed_slots","cancelled_audit_record_retained",
        "new_hold_after_release_allowed",
    ):
        assert model[field] is True
    assert model["final_reference_slot_rows"]==4
    assert model["real_mysql_or_wordpress_writes"]==0


@pytest.mark.parametrize("original,replacement",[
    ("define( 'EMPIRE_CAR_YARD_ENABLE_INTERNAL_BOOKINGS', false )",
     "define( 'EMPIRE_CAR_YARD_ENABLE_INTERNAL_BOOKINGS', true )"),
    ("'public'              => false","'public'              => true"),
    ("'publicly_queryable'  => false","'publicly_queryable'  => true"),
    ("'show_in_rest'        => true","'show_in_rest'        => false"),
    ("'capability_type'     => array( 'empire_vehicle', 'empire_vehicles' )",
     "'capability_type'     => 'post'"),
    ("'map_meta_cap'        => true","'map_meta_cap'        => false"),
    ("UNIQUE KEY resource_slot (resource_key,slot_utc)","KEY resource_slot (resource_key,slot_utc)"),
    ("service_code varchar(20) NOT NULL","missing_column varchar(20) NOT NULL"),
    ("vehicle_id bigint(20) unsigned NOT NULL","removed_column bigint(20) unsigned NOT NULL"),
    ("ENGINE=InnoDB","ENGINE=MyISAM"),
    ("register_activation_hook(","register_deactivation_hook("),
])
def test_activation_inventory_or_slot_schema_tamper_refused(tmp_path,original,replacement):
    with pytest.raises(ValueError):
        inspect_car_yard_private_plugin(modify(tmp_path,BOOT,original,replacement))


@pytest.mark.parametrize("original,replacement",[
    ("EMPIRE_CAR_YARD_ENABLE_INTERNAL_BOOKINGS === true","EMPIRE_CAR_YARD_ENABLE_INTERNAL_BOOKINGS !== true"),
    ("current_user_can( 'manage_options' )","is_user_logged_in()"),
    ("'permission_callback'","'request_callback'"),
    ("'START TRANSACTION'","'NO_TRANSACTION'"),
    ("'ROLLBACK'","'NO_ROLLBACK'"),
    ("'COMMIT'","'NO_COMMIT'"),
    ("information_schema.TABLES","information_schema.COLUMNS"),
    ("'InnoDB'","'MyISAM'"),
    ("FOR UPDATE","NO_LOCK"),
    ("time() + 1800","time() - 1000"),
    ("90 * DAY_IN_SECONDS","999 * DAY_IN_SECONDS"),
    ("'customer_booking_created' => false","'customer_booking_created' => true"),
    ("'payment_captured' => false","'payment_captured' => true"),
])
def test_internal_booking_change_rejected(tmp_path,original,replacement):
    with pytest.raises(ValueError):
        inspect_car_yard_private_plugin(modify(tmp_path,BOOK,original,replacement))


@pytest.mark.parametrize("injected",[
    "wp_mail( 'fake@example.invalid', 'test','hello' );",
    "wp_remote_post('https://example.invalid/collect');",
    "register_rest_route('public', '/send', array('permission_callback'=>'__return_true'));",
    "customer_phone",
    "stripe",
    "recipient_email",
])
def test_unapproved_external_send_contact_or_public_route_rejected(tmp_path,injected):
    path=isolated(tmp_path)
    with (path/BOOK).open("a") as f:
        f.write("\n// "+injected+"\n")
    with pytest.raises(ValueError):
        inspect_car_yard_private_plugin(path)


def test_unknown_symlinked_plugin_source_rejected(tmp_path):
    path=tmp_path/"symlink"
    path.symlink_to(PLUGIN,target_is_directory=True)
    with pytest.raises(ValueError):
        inspect_car_yard_private_plugin(path)


def test_actual_runtime_smoke_receipt_is_not_innodb_or_live_booking_claim():
    report=json.loads(SMOKE.read_text())
    assert report["status"]=="REAL_PLAYGROUND_WORDPRESS_PHP_THEME_AND_PRIVATE_ROUTE_SMOKE_PASS"
    assert report["runtime_kind"]=="OFFICIAL_WORDPRESS_PLAYGROUND_CLI_EPHEMERAL_LOCALHOST"
    assert len(report["five_wp_page_renderings"])==5
    assert len(report["unauthed_private_write_and_booking_routes_rejected"])==4
    assert report["private_vehicle_cpt_registered"] is True
    assert report["mysql_innodb_booking_transactions_tested"] is False
    assert report["wordpress_vehicle_admin_crud_tested"] is False
    assert report["wordpress_staff_internal_booking_tested"] is False
    assert report["public_person_data_collection_enabled"] is False
    assert report["production_changes"] is False


def test_readme_holds_consent_and_sandbox_registration_gates():
    text=(PLUGIN/"readme.txt").read_text()
    assert "EMPIRE_CAR_YARD_ENABLE_INTERNAL_BOOKINGS" in text
    assert "No unauthenticated route exists" in text
    assert "InnoDB" in text
    assert "consumer personal" in text.lower() or "personal" in text.lower()
    assert "source-level safety checks" in text.lower()


def test_reproducible_offline_private_plugin_zip(tmp_path):
    from zipfile import ZipFile
    from scripts.review_jev_car_yard_private_plugin_20261022 import (
        assemble_private_prototype,
    )
    a=assemble_private_prototype(to=tmp_path/"a.zip")
    b=assemble_private_prototype(to=tmp_path/"b.zip")
    assert a["review_status"]=="REAL_WP_THEME_AND_INVENTORY_CRUD_PASS_BOOKING_TRANSACTIONS_HELD"
    assert a["offline_internal_plugin_zip_sha256"]==b["offline_internal_plugin_zip_sha256"]
    assert a["offline_internal_plugin_zip_bytes"]==b["offline_internal_plugin_zip_bytes"]
    assert a["offline_internal_plugin_files"]==3
    assert a["word_press_php_runtime_executed"] is False  # static model itself
    assert a["php_wordpress_bootstrap_and_theme_smoke_observed"] is True
    assert a["wordpress_mysql_innodb_active_booking_tested"] is False
    assert a["production_plugin_installed"] is False
    assert a["production_changes"] is False
    assert a["outbound_sent"]==0
    with ZipFile(tmp_path/"a.zip") as z:
        assert set(z.namelist())=={
            "empire-car-yard-internal/empire-car-yard-internal.php",
            "empire-car-yard-internal/includes/class-empire-yard-bookings.php",
            "empire-car-yard-internal/readme.txt",
        }
        assert z.testzip() is None


def test_offline_packager_refuses_overwriting_reviewed_original(tmp_path):
    from scripts.review_jev_car_yard_private_plugin_20261022 import (
        assemble_private_prototype,
    )
    dest=tmp_path/"original.zip"
    assemble_private_prototype(to=dest)
    with pytest.raises(ValueError,match="overwrite"):
        assemble_private_prototype(to=dest)


def test_release_receipt_pins_blueprint_php_and_real_smoke():
    from scripts.review_jev_car_yard_private_plugin_20261022 import (
        RECEIPT,DIST,SMOKE,BLUEPRINT,
    )
    p=json.loads(RECEIPT.read_text())
    assert p["review_status"]=="REAL_WP_THEME_AND_INVENTORY_CRUD_PASS_BOOKING_TRANSACTIONS_HELD"
    assert p["original_runtime_smoke_sha256"]==sha256(SMOKE.read_bytes()).hexdigest()
    assert p["original_blueprint_sha256"]==sha256(BLUEPRINT.read_bytes()).hexdigest()
    assert p["offline_internal_plugin_zip_sha256"]==sha256(DIST.read_bytes()).hexdigest()
    assert p["wordpress_mysql_innodb_active_booking_tested"] is False
    assert p["wordpress_sandbox_sqlite_is_not_innodb"] is True
    assert p["outbound_sent"]==0
    assert p["production_plugin_installed"] is False
    assert p["database_writes"] is False


def test_disposable_blueprint_is_not_an_authenticated_live_customer_site():
    from scripts.review_jev_car_yard_private_plugin_20261022 import BLUEPRINT
    a=json.loads(BLUEPRINT.read_text())
    assert a["features"]["networking"] is False
    assert a["preferredVersions"]=={"php":"8.3","wp":"6.8"}
    assert [step["step"] for step in a["steps"]]==[
        "activateTheme","activatePlugin","runPHP",
    ]
    assert "wp_insert_post" in a["steps"][2]["code"]
    assert "FICTIONAL" in a["steps"][2]["code"].upper()
    assert "login" not in str(a).lower()


def test_real_wordpress_admin_inventory_crud_receipt_and_cleanup():
    from scripts.review_jev_car_yard_private_plugin_20261022 import (
        CRUD,CRUD_BLUEPRINT,
    )
    report=json.loads(CRUD.read_text())
    assert report["status"]=="REAL_DISPOSABLE_WP_PHP_ADMIN_INVENTORY_CRUD_SMOKE_PASS"
    assert report["fictional_inventory_crud_all_passed"] is True
    assert report["admin_site_and_vehicle_cap_verified"] is True
    assert report["synthetic_vehicle_records_remaining"]==0
    assert report["real_customer_data_used"] is False
    assert report["mysql_booking_conflict_rollback_tested"] is False
    assert report["vehicle_listing_front_end_tested"] is False
    assert report["blueprint_source_sha256"]==sha256(CRUD_BLUEPRINT.read_bytes()).hexdigest()


def test_approved_release_manifest_pins_both_wordpress_runtime_receipts():
    from scripts.review_jev_car_yard_private_plugin_20261022 import (
        RECEIPT,CRUD,CRUD_BLUEPRINT,
    )
    report=json.loads(RECEIPT.read_text())
    assert report["review_status"]=="REAL_WP_THEME_AND_INVENTORY_CRUD_PASS_BOOKING_TRANSACTIONS_HELD"
    assert report["original_wordpress_inventory_crud_smoke_sha256"]==sha256(CRUD.read_bytes()).hexdigest()
    assert report["original_wordpress_crud_blueprint_sha256"]==sha256(CRUD_BLUEPRINT.read_bytes()).hexdigest()
    assert report["wp_php_admin_context_inventory_crud_tested"] is True
    assert report["wp_admin_visual_site_editor_tested"] is False
    assert report["wordpress_mysql_innodb_active_booking_tested"] is False
    assert report["production_changes"] is False


def test_existing_owner_handoff_distinguishes_runtime_smoke_from_booking_release():
    p=ROOT/"docs/commercial/EMPIRE_AGENCY_WORDPRESS_CAR_YARD_RUNTIME_HANDOFF_20261022.md"
    h=p.read_text()
    assert "WordPress **6.8**" in h
    assert "PHP **8.3**" in h
    assert "NOT TESTED" in h
    assert "MySQL/InnoDB" in h
    assert "zero" in h.lower()
    assert "no emails" in h.lower()
