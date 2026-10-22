"""Read only fictional WP CRUD fixture emitted by an isolated PHP Blueprint."""
from __future__ import annotations

from urllib.request import Request,urlopen
from pathlib import Path
from datetime import datetime,timezone
import json,argparse
from hashlib import sha256

ROOT=Path(__file__).resolve().parents[1]
BLUEPRINT=ROOT/"prototypes/agency_wordpress_service_handoff_20261022/playground-local-crud-blueprint.json"
OUTPUT=ROOT/"docs/commercial/JEV_CAR_YARD_PLAYGROUND_INVENTORY_CRUD_20261022.json"
SOURCE="http://127.0.0.1:9479/wp-content/uploads/empire-car-yard-sandbox-inventory-crud-fixture.json"


def read_crud_smoke()->dict:
    with urlopen(Request(SOURCE,headers={"User-Agent":"EmpireOS-Sandbox-Fictional-Inventory-ReadOnly/1.0"}),timeout=8) as f:
        if f.status!=200:
            raise ValueError("original synthetic WP CRUD fixture unavailable")
        raw=f.read(16000)
        obj=json.loads(raw)
    expected={
        "admin_can_manage_site":True,
        "admin_vehicle_role_cap_present":True,
        "inventory_post_type_registered":True,
        "fictional_stock_created":True,
        "fictional_meta_round_trip":True,
        "fictional_stock_read":True,
        "fictional_inventory_update":True,
        "fictional_stock_deleted":True,
        "fictional_post_ids_left_after_test":0,
        "real_business_or_customer_records":0,
        "real_customer_booking_created":0,
        "production_changes":False,
    }
    if obj.get("schema_version")!="empire.jev.wordpress_disposable_inventory_crud.v1":
        raise ValueError("wrong PHP integration source proof")
    for key,value in expected.items():
        if obj.get(key) is not value:
            raise ValueError("WordPress inventory CRUD failed gate "+key+" observed "+str(obj.get(key)))
    return {
        "schema_version":"empire.jev.wordpress_inventory_crud_runtime_smoke.v1",
        "status":"REAL_DISPOSABLE_WP_PHP_ADMIN_INVENTORY_CRUD_SMOKE_PASS",
        "observed_at_utc":datetime.now(timezone.utc).isoformat(),
        "php_crud_output_sha256":sha256(raw).hexdigest(),
        "blueprint_source_sha256":sha256(BLUEPRINT.read_bytes()).hexdigest(),
        "runtime_wordpress":"6.8",
        "runtime_php":"8.3",
        "db_backend":"PLAYGROUND_SQLITE_NOT_MYSQL_INNODB",
        "fictional_inventory_crud_all_passed":True,
        "admin_site_and_vehicle_cap_verified":True,
        "synthetic_vehicle_records_remaining":0,
        "real_customer_data_used":False,
        "mysql_booking_conflict_rollback_tested":False,
        "auth_wp_admin_editor_browser_tested":False,
        "vehicle_listing_front_end_tested":False,
        "production_changes":False,
        "execution_authority":"none",
    }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--probe-loopback-only",required=True,action="store_true")
    parser.parse_args()
    if OUTPUT.exists() or OUTPUT.is_symlink():
        raise ValueError("immutable original WP CRUD smoke already exists")
    report=read_crud_smoke()
    with OUTPUT.open("x",encoding="utf8") as f:
        json.dump(report,f,sort_keys=True,indent=2)
        f.write("\n")
    print(json.dumps(report,sort_keys=True))


if __name__=="__main__":
    main()
