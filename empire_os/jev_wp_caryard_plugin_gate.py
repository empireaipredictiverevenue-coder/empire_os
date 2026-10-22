"""Static car-yard plugin audit plus isolated SQL uniqueness reference test.

Not a PHP parser, not a WordPress runtime, not a real booking or vehicle
inventory availability test. Functional duplicate-slot model uses SQLite as
an *independent model*, not evidence that MySQL/WP integration has run.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Mapping
import sqlite3

SCHEMA="empire.jev.wp_caryard_inventory_booking_gate.v1"
REQUIRED={
    "empire-caryard-gated.php",
    "includes/class-eacy-vehicles.php",
    "includes/class-eacy-repair-slots.php",
}


def _read_plugin(root:Path)->dict[str,str]:
    if root.is_symlink() or not root.is_dir():
        raise ValueError("missing isolated WordPress plugin package")
    result={}
    for rel in REQUIRED:
        p=root/rel
        if p.is_symlink() or not p.is_file() or not 0<p.stat().st_size<=40000:
            raise ValueError("missing or unsafe WordPress demo file: "+rel)
        body=p.read_text("utf8")
        if not body.startswith("<?php") or "if ( ! defined( 'ABSPATH' ) )" not in body:
            raise ValueError("PHP source must be WordPress-gated")
        result[rel]=body
    return result


def sql_unique_slot_reference_test(*,attempts:int=10)->dict[str,int]:
    if type(attempts) is not int or not 2<=attempts<=25:
        raise ValueError("bounded independent conflict reference")
    with TemporaryDirectory(prefix="eacy_sqlite_slot_reference_") as directory:
        db=Path(directory)/"slots.sqlite3"
        with sqlite3.connect(db) as conn:
            conn.execute(
                "CREATE TABLE demo_slots ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "slot_start_utc TEXT NOT NULL UNIQUE, "
                "status TEXT NOT NULL CHECK(status='admin_demo_hold'))"
            )
        def try_hold(index:int)->int:
            connection=sqlite3.connect(db,timeout=15,isolation_level=None)
            try:
                connection.execute("PRAGMA busy_timeout=15000")
                # The same-key conflict test is an *independent* SQLite
                # reference for atomic uniqueness. It never executes PHP.
                cur=connection.execute(
                    "INSERT OR IGNORE INTO demo_slots(slot_start_utc,status) "
                    "VALUES(?,?)",
                    ("2026-11-02 10:00:00","admin_demo_hold")
                )
                return cur.rowcount
            finally:
                connection.close()
        with ThreadPoolExecutor(max_workers=min(attempts,12)) as pool:
            outcomes=list(pool.map(try_hold,range(attempts)))
        with sqlite3.connect(db) as conn:
            final_count=conn.execute("SELECT COUNT(*) FROM demo_slots").fetchone()[0]
        winners=sum(outcomes)
        if winners!=1 or final_count!=1 or any(x not in (0,1) for x in outcomes):
            raise ValueError("independent SQL model fails unique-slot property")
        return {
            "attempts":attempts,
            "successful_slot_holds":winners,
            "duplicate_or_conflicting_holds_rejected":attempts-winners,
            "rows_after_race":final_count,
        }


def review_wp_caryard_plugin(root:Path,*,source_review:Mapping[str,Any])->dict[str,Any]:
    if (not isinstance(source_review,Mapping)
        or source_review.get("schema_version")!="empire.jev.wordpress_delivery_capability_preflight.v1"
        or source_review.get("status")!="WORDPRESS_BLOCK_THEME_STATIC_PREFLIGHT_PASS_RUNTIME_REQUIRED"
        or source_review.get("commercial_proposals_ready")!=0
        or source_review.get("wp_php_runtime_available_or_tested") is not False
        or source_review.get("outbound_sent")!=0
        or source_review.get("production_changes") is not False
        or source_review.get("execution_authority")!="none"):
        raise ValueError("parent WordPress capability research cannot authorize product")
    files=_read_plugin(Path(root))
    main=files["empire-caryard-gated.php"]
    vehicle=files["includes/class-eacy-vehicles.php"]
    slots=files["includes/class-eacy-repair-slots.php"]
    if (not all(word in main for word in (
        "Plugin Name: Empire Car-Yard Capability Demo",
        "register_activation_hook",
        "rest_api_init",
        "EACY_Repair_Slots', 'activate_schema'",
        "EACY_Vehicles', 'register'",
    ))
        or "EACY_DEMO_ADMIN_SLOT_TEST_ENABLED" in main):
        raise ValueError("plugin installation or default activation gate corrupted")
    if (not all(word in vehicle for word in (
        "register_post_type(", "register_post_meta(",
        "self::POST_TYPE", "'show_in_rest' => true",
        "'post_status' => 'publish'",
        "'posts_per_page' => 12", "wp_reset_postdata(",
        "'_eacy_year'","'_eacy_price_aud'","'_eacy_stock_state'",
        "esc_html(", "esc_url(", "esc_html( get_the_title(", "add_shortcode(",
        "Capability demo only:",
    ))
        or vehicle.count("register_post_meta(")!=3
        or "wp_mail(" in vehicle):
        raise ValueError("vehicle CPT, editor meta or public display gate missing")
    if (not all(word in slots for word in (
        "register_rest_route(",
        "permission_callback", "'can_test_slot'",
        "EACY_DEMO_ADMIN_SLOT_TEST_ENABLED === true",
        "current_user_can( 'manage_options' )",
        "INSERT IGNORE INTO",
        "UNIQUE KEY unique_slot_start (slot_start_utc)",
        "dbDelta( $sql )",
        "DateTimeImmutable::createFromFormat",
        "eacy_conflict", "'status' => 409",
        "'admin_demo_hold'",
        "'customer_booking_accepted' => false",
        "'public_booking_endpoint_enabled' => false",
    ))
        or slots.count("register_rest_route(")!=2
        or slots.count("'permission_callback'")!=2
        or "__return_true" in slots
        or "$_POST" in slots
        or "wp_mail(" in slots
        or "customer_email" in slots
        or "customer_name" in slots):
        raise ValueError("privacy gate or slot uniqueness guard missing")
    if not all(word in slots for word in (
        "'/admin-slot-hold'","'/admin-slot-count'",
        "'methods' => 'POST'","'methods' => 'GET'",
        "self::admin_test_enabled() && current_user_can( 'manage_options' )",
        "if ( ! self::can_test_slot() )",
    )):
        raise ValueError("administrator-only slot permission contract broken")

    model=sql_unique_slot_reference_test()
    return {
        "schema_version":SCHEMA,
        "mode":"OBSERVE",
        "status":"WP_CARYARD_PLUGIN_STATIC_GATES_PASS_RUNTIME_INTEGRATION_REQUIRED",
        "plugin_source_sha256":dict(sorted(
            (name,sha256(body.encode("utf8")).hexdigest())
            for name,body in files.items()
        )),
        "source_files_checked":len(files),
        "vehicle_post_type_and_editor_meta_source_present":True,
        "vehicle_display_source_present":True,
        "booking_conflict_unique_key_source_present":True,
        "booking_admin_permission_source_present":True,
        "public_booking_api_source_present":False,
        "owner_opt_in_required_on_disposable_wp_instance":True,
        "sqlite_reference_conflict_model":model,
        "actual_wordpress_php_and_mysql_semantics_tested":False,
        "wp_admin_vehicle_crud_tested":False,
        "vehicle_image_upload_and_rest_tested":False,
        "real_inventory_sync_and_pricing_verified":False,
        "wp_repair_slot_concurrent_requests_tested":False,
        "public_customer_booking_or_calendar_implemented":False,
        "date_timezone_owner_service_hours_verified":False,
        "customer_identity_consent_notification_and_retention_tested":False,
        "buyer_project_still_open_verified":False,
        "contract_and_payment_terms_approved":False,
        "commercial_offer_ready":False,
        "production_inventory_or_booking_activated":False,
        "contacts_collected":0,
        "crm_writes":False,
        "outbound_sent":0,
        "database_writes":False,
        "execution_authority":"none",
    }
