"""Static PHP WordPress car-yard plugin safety review + separate SQL canary.

The SQLite transaction exercise tests an analogous slot uniqueness rule. It
DOES NOT execute PHP, WordPress, InnoDB or a real customer booking. Produces
aggregate-only evidence with no contacts and no production changes.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import re
import sqlite3

SCHEMA="empire.jev.car_yard_private_plugin_preflight.v1"
PLUGIN_FILES=(
    "empire-car-yard-internal.php",
    "includes/class-empire-yard-bookings.php",
)


def _required(source:str,tokens:tuple[str,...],which:str)->None:
    missing=[token for token in tokens if token not in source]
    if missing:
        raise ValueError(f"Unsafe or incomplete {which}: {','.join(missing[:3])}")


def _sqlite_reference_canary()->dict[str,int|bool]:
    """Reference schedule-slot model, not executable WP booking proof."""
    with TemporaryDirectory(prefix="empire-yard-fixture-") as folder:
        db=Path(folder)/"fictional_booking.sqlite"
        con=sqlite3.connect(str(db))
        con.execute("PRAGMA foreign_keys=ON")
        con.execute("CREATE TABLE bookings (id INTEGER PRIMARY KEY, resource TEXT NOT NULL, status TEXT NOT NULL)")
        con.execute("""CREATE TABLE slots (
            booking_id INTEGER NOT NULL, resource TEXT NOT NULL, slot TEXT NOT NULL,
            UNIQUE(resource,slot),
            FOREIGN KEY(booking_id) REFERENCES bookings(id))""")
        first_slots=("2026-12-20 09:00:00","2026-12-20 09:30:00")
        second_slots=("2026-12-20 09:30:00","2026-12-20 10:00:00")
        def claim(resource:str,slots:tuple[str,...])->int|None:
            con.execute("BEGIN IMMEDIATE")
            try:
                cursor=con.execute("INSERT INTO bookings (resource,status) VALUES (?,?)",
                                   (resource,"held"))
                ident=cursor.lastrowid
                for slot in slots:
                    con.execute("INSERT INTO slots (booking_id,resource,slot) VALUES (?,?,?)",
                                (ident,resource,slot))
                con.commit()
                return ident
            except sqlite3.IntegrityError:
                con.rollback()
                return None
        first=claim("bay-1",first_slots)
        overlap=claim("bay-1",second_slots)
        independent=claim("bay-2",second_slots)
        assert first is not None and overlap is None and independent is not None
        assert con.execute("SELECT COUNT(*) FROM bookings").fetchone()[0]==2
        assert con.execute("SELECT COUNT(*) FROM slots").fetchone()[0]==4
        con.execute("BEGIN IMMEDIATE")
        con.execute("UPDATE bookings SET status='cancelled' WHERE id=? AND status='held'",(first,))
        con.execute("DELETE FROM slots WHERE booking_id=?",(first,))
        con.commit()
        rebook=claim("bay-1",second_slots)
        assert rebook is not None
        retained=con.execute("SELECT COUNT(*) FROM bookings WHERE status='cancelled'").fetchone()[0]
        assert retained==1
        slot_count=con.execute("SELECT COUNT(*) FROM slots").fetchone()[0]
        con.close()
    return {
        "fictional_held_booking_accepted":True,
        "overlap_same_bay_rejected":True,
        "failed_hold_rolled_back":True,
        "same_utc_slot_distinct_bay_allowed":True,
        "cancel_releases_claimed_slots":True,
        "cancelled_audit_record_retained":True,
        "new_hold_after_release_allowed":True,
        "final_reference_slot_rows":slot_count,
        "real_mysql_or_wordpress_writes":0,
    }


def inspect_car_yard_private_plugin(plugin:Path)->dict:
    if plugin.is_symlink() or not plugin.is_dir():
        raise ValueError("isolated plugin source unavailable")
    files={}
    for name in PLUGIN_FILES:
        file=plugin/name
        if file.is_symlink() or not file.is_file() or not 0<file.stat().st_size<65000:
            raise ValueError("expected private PHP file not present")
        raw=file.read_bytes()
        files[name]=sha256(raw).hexdigest()
    bootstrap=(plugin/PLUGIN_FILES[0]).read_text()
    booking=(plugin/PLUGIN_FILES[1]).read_text()
    _required(bootstrap,(
        "Plugin Name: Empire Car Yard Internal Prototype",
        "defined( 'ABSPATH' ) || exit",
        "define( 'EMPIRE_CAR_YARD_ENABLE_INTERNAL_BOOKINGS', false )",
        "register_post_type(", "'empire_vehicle'",
        "'public'              => false",
        "'publicly_queryable'  => false",
        "'show_in_rest'        => true",
        "'capability_type'     => array( 'empire_vehicle', 'empire_vehicles' )",
        "'map_meta_cap'        => true",
        "register_post_meta(", "'_empire_stock_status'",
        "'available', 'reserved', 'sold', 'archived'",
        "'_empire_make'", "'_empire_model'", "'_empire_stock_code'",
        "'_empire_mileage_km'", "'_empire_model_year'",
        "'_empire_price_aud_cents'",
        "current_user_can( 'manage_options' )",
        "register_activation_hook(", "get_role( 'administrator' )",
        "dbDelta(", "ENGINE=InnoDB", "service_code varchar(20) NOT NULL",
        "vehicle_id bigint(20) unsigned NOT NULL",
        "UNIQUE KEY resource_slot (resource_key,slot_utc)",
    ),"admin-only inventory and storage schema")
    _required(booking,(
        "EMPIRE_CAR_YARD_ENABLE_INTERNAL_BOOKINGS === true",
        "current_user_can( 'manage_options' )",
        "register_rest_route(", "'permission_callback'",
        "'/internal/reservations'",
        "private, no-store, max-age=0",
        "information_schema.TABLES",
        "InnoDB", "START TRANSACTION", "ROLLBACK", "COMMIT",
        "SELECT id, status FROM", "FOR UPDATE",
        "resource_key", "starts_at_utc", "service_code", "vehicle_id",
        "get_post( $vehicle )", "'empire_vehicle' !== $post->post_type",
        "INTERVAL_SECONDS = 1800", "MAX_DURATION_SECONDS = 7200",
        "time() + 1800", "90 * DAY_IN_SECONDS",
        "'status' => 'held'", "'status' => 'cancelled'",
        "slot_conflict", "outbound_notifications",
        "'customer_booking_created' => false",
        "'notification_sent' => false",
        "'payment_captured' => false",
    ),"private booking transaction")
    if len(re.findall(r"'permission_callback'\s*=>",booking))!=3:
        raise ValueError("one or more route permission callbacks absent")
    # Transactional correctness must be present at *every* usage site,
    # not merely mentioned once in a comment or another SQL statement.
    exact_tokens={
        "bootstrap ENGINE=InnoDB":(bootstrap,"ENGINE=InnoDB",2),
        "START TRANSACTION":(booking,"'START TRANSACTION'",2),
        "ROLLBACK":(booking,"'ROLLBACK'",5),
        "COMMIT":(booking,"'COMMIT'",2),
        "engine guard":(booking,"'InnoDB'",1),
    }
    for description,(source,token,count) in exact_tokens.items():
        if source.count(token)!=count:
            raise ValueError("transaction count changed: "+description)
    if any(item in (bootstrap+"\n"+booking).lower() for item in (
        "wp_mail(", "wp_remote_post(", "stripe", "paypal",
        "recipient_email", "customer_phone", "customer_address",
        "__return_true", "register_uninstall_hook(",
    )):
        raise ValueError("customer data, payments or public unauthenticated routes prohibited")
    return {
        "schema_version":SCHEMA,
        "mode":"OBSERVE",
        "status":"PRIVATE_CAR_YARD_PHP_STATIC_PREFLIGHT_PASS_RUNTIME_REQUIRED",
        "plugin_file_sha256":dict(sorted(files.items())),
        "vehicle_inventory_admin_only_source_verified":True,
        "vehicle_stock_status_enum_present":True,
        "stock_vehicle_price_is_display_metadata_not_payment":True,
        "admin_only_rest_permission_callbacks_checked":3,
        "internal_booking_constant_default_false":True,
        "transactional_slot_uniqueness_source_verified":True,
        "reference_booking_sqlite_canary":_sqlite_reference_canary(),
        "source_php_linted_by_real_php":False,
        "word_press_php_runtime_executed":False,
        "word_press_plugin_activation_and_dbdelta_tested":False,
        "real_mysql_innodb_overlap_tested":False,
        "wp_admin_inventory_crud_tested":False,
        "end_to_end_staff_booking_tested":False,
        "real_website_responsive_render_tested":False,
        "real_visitor_contact_form_enabled":False,
        "public_customer_booking_enabled":False,
        "vehicle_inventory_public_listing_implemented":False,
        "booking_time_zone_and_opening_hours_policy_implemented":False,
        "customer_or_personal_contact_records_processed":0,
        "payment_actions":0,"messages_sent":0,
        "production_changes":False,
        "execution_authority":"none",
    }
