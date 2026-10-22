"""Make a reproducible private WordPress plugin ZIP with evidence-gated receipt.

No WP production, buyer CRM, contacts or financial actions. The Playground
smoke proves PHP/bootstrap and theme execution only; it cannot validate
InnoDB transactions or authenticated wp-admin booking functionality.
"""
from __future__ import annotations

from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile,ZipInfo,ZIP_DEFLATED
import argparse
import json

from empire_os.jev_car_yard_plugin_preflight import (
    SCHEMA as PREFLIGHT_SCHEMA,
    PLUGIN_FILES,inspect_car_yard_private_plugin,
)

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/"prototypes/agency_wordpress_service_handoff_20261022"
PLUGIN=BASE/"empire-car-yard-internal"
SMOKE=ROOT/"docs/commercial/JEV_CAR_YARD_PLAYGROUND_RUNTIME_SMOKE_20261022.json"
BLUEPRINT=BASE/"playground-local-integration-blueprint.json"
CRUD=ROOT/"docs/commercial/JEV_CAR_YARD_PLAYGROUND_INVENTORY_CRUD_20261022.json"
CRUD_BLUEPRINT=BASE/"playground-local-crud-blueprint.json"
DIST=BASE/"dist/empire-car-yard-internal-prototype-0.1.0.zip"
RECEIPT=ROOT/"docs/commercial/JEV_CAR_YARD_PRIVATE_PLUGIN_CAPABILITY_20261022.json"
SOURCE_FILES=(*PLUGIN_FILES,"readme.txt")


def assemble_private_prototype(*,to:Path)->dict:
    source=inspect_car_yard_private_plugin(PLUGIN)
    if (source.get("schema_version")!=PREFLIGHT_SCHEMA
        or source.get("status")!="PRIVATE_CAR_YARD_PHP_STATIC_PREFLIGHT_PASS_RUNTIME_REQUIRED"
        or source.get("public_customer_booking_enabled") is not False
        or source.get("execution_authority")!="none"):
        raise ValueError("unsafe WordPress source preflight")
    if (SMOKE.is_symlink() or not SMOKE.is_file()
        or not 0<SMOKE.stat().st_size<=40000):
        raise ValueError("real Playground smoke is required to assemble release")
    proof=json.loads(SMOKE.read_text())
    if (proof.get("status")!="REAL_PLAYGROUND_WORDPRESS_PHP_THEME_AND_PRIVATE_ROUTE_SMOKE_PASS"
        or proof.get("private_vehicle_cpt_registered") is not True
        or len(proof.get("five_wp_page_renderings",{}))!=5
        or len(proof.get("unauthed_private_write_and_booking_routes_rejected",{}))!=4
        or proof.get("mysql_innodb_booking_transactions_tested") is not False
        or proof.get("wordpress_staff_internal_booking_tested") is not False
        or proof.get("production_changes") is not False
        or proof.get("execution_authority")!="none"):
        raise ValueError("runtime proof is incomplete, promoted or incompatible")
    blueprint=json.loads(BLUEPRINT.read_text())
    steps=blueprint.get("steps",[])
    if (blueprint.get("features")!={"networking":False}
        or blueprint.get("preferredVersions")!={"php":"8.3","wp":"6.8"}
        or not isinstance(steps,list)
        or len(steps)!=3
        or steps[0]!={"step":"activateTheme","themeFolderName":"empire-local-services"}
        or steps[1]!={"step":"activatePlugin","pluginPath":"empire-car-yard-internal/empire-car-yard-internal.php"}
        or steps[2].get("step")!="runPHP"
        or "FICTIONAL" not in steps[2].get("code", "").upper()
        or "wp_insert_post" not in steps[2].get("code", "")):
        raise ValueError("untrusted disposable WordPress sandbox setup")
    if CRUD.is_symlink() or not CRUD.is_file() or not 0<CRUD.stat().st_size<=15000:
        raise ValueError("actual disposable WP PHP CRUD receipt required")
    crud=json.loads(CRUD.read_text())
    if (crud.get("status")!="REAL_DISPOSABLE_WP_PHP_ADMIN_INVENTORY_CRUD_SMOKE_PASS"
        or crud.get("fictional_inventory_crud_all_passed") is not True
        or crud.get("admin_site_and_vehicle_cap_verified") is not True
        or crud.get("synthetic_vehicle_records_remaining")!=0
        or crud.get("mysql_booking_conflict_rollback_tested") is not False
        or crud.get("production_changes") is not False
        or crud.get("execution_authority")!="none"
        or crud.get("blueprint_source_sha256")!=sha256(CRUD_BLUEPRINT.read_bytes()).hexdigest()):
        raise ValueError("actual WordPress inventory CRUD not correctly verified")
    if to.is_symlink() or to.exists():
        raise ValueError("refuse to overwrite reviewed plugin ZIP")
    to.parent.mkdir(parents=True,exist_ok=True)
    with ZipFile(to,"x",compression=ZIP_DEFLATED,compresslevel=9) as zipfile:
        for rel in SOURCE_FILES:
            path=PLUGIN/rel
            if path.is_symlink() or not path.is_file() or path.stat().st_size>65000:
                raise ValueError("unsafe plugin file")
            info=ZipInfo("empire-car-yard-internal/"+rel,date_time=(2026,10,22,0,0,0))
            info.compress_type=ZIP_DEFLATED
            info.external_attr=0o644<<16
            zipfile.writestr(info,path.read_bytes(),compress_type=ZIP_DEFLATED,compresslevel=9)
    with ZipFile(to) as archive:
        if (set(archive.namelist())!={"empire-car-yard-internal/"+rel for rel in SOURCE_FILES}
            or archive.testzip() is not None
            or any(item.startswith("/") or ".." in item for item in archive.namelist())):
            raise ValueError("invalid release ZIP")
    return {
        **source,
        "review_status":"REAL_WP_THEME_AND_INVENTORY_CRUD_PASS_BOOKING_TRANSACTIONS_HELD",
        "php_wordpress_bootstrap_and_theme_smoke_observed":True,
        "real_wordpress_php_loaded_plugin_privacy_routes":True,
        "original_runtime_smoke_sha256":sha256(SMOKE.read_bytes()).hexdigest(),
        "original_wordpress_inventory_crud_smoke_sha256":sha256(CRUD.read_bytes()).hexdigest(),
        "original_wordpress_crud_blueprint_sha256":sha256(CRUD_BLUEPRINT.read_bytes()).hexdigest(),
        "wp_php_admin_context_inventory_crud_tested":True,
        "wp_admin_visual_site_editor_tested":False,
        "original_blueprint_sha256":sha256(BLUEPRINT.read_bytes()).hexdigest(),
        "offline_internal_plugin_zip_sha256":sha256(to.read_bytes()).hexdigest(),
        "offline_internal_plugin_zip_bytes":to.stat().st_size,
        "offline_internal_plugin_files":len(SOURCE_FILES),
        "wordpress_mysql_innodb_active_booking_tested":False,
        "wordpress_sandbox_sqlite_is_not_innodb":True,
        "production_plugin_installed":False,
        "client_site_delivered":False,
        "outbound_sent":0,
        "database_writes":False,
        "source_revision_audit_at_utc":datetime.now(timezone.utc).isoformat(),
    }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--package-offline-reviewed",required=True,action="store_true")
    parser.parse_args()
    if RECEIPT.is_symlink() or RECEIPT.exists():
        raise ValueError("source review receipt already exists")
    result=assemble_private_prototype(to=DIST)
    with RECEIPT.open("x",encoding="utf8") as f:
        json.dump(result,f,sort_keys=True,indent=2)
        f.write("\n")
    print(json.dumps({
        "review_status":result["review_status"],
        "plugin_zip_bytes":result["offline_internal_plugin_zip_bytes"],
        "theme_php_runtime_smoke":result["php_wordpress_bootstrap_and_theme_smoke_observed"],
        "mysql_innodb_bookings_proven":result["wordpress_mysql_innodb_active_booking_tested"],
        "production_installed":result["production_plugin_installed"],
    },sort_keys=True))


if __name__=="__main__":
    main()
