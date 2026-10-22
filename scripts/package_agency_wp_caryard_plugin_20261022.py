"""Deterministic offline *source* ZIP for a gated, uninstalled demo plugin."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from empire_os.jev_wp_caryard_plugin_gate import review_wp_caryard_plugin, REQUIRED

ROOT=Path(__file__).resolve().parents[1]
TOP=ROOT/"prototypes/agency_wordpress_service_handoff_20261022"
PLUGIN=TOP/"plugins/empire-caryard-gated"
PARENT=ROOT/"docs/commercial/JEV_WORDPRESS_SERVICE_HANDOVER_PREFLIGHT_20261022.json"
ZIP=TOP/"dist/empire-caryard-gated-demo-plugin-0.1.0.zip"
INCLUDE=sorted(REQUIRED | {"README.md"})


def make_offline_zip(*,destination:Path)->dict:
    p=json.loads(PARENT.read_text())
    report=review_wp_caryard_plugin(PLUGIN,source_review=p)
    if (report["status"]!="WP_CARYARD_PLUGIN_STATIC_GATES_PASS_RUNTIME_INTEGRATION_REQUIRED"
        or report["public_customer_booking_or_calendar_implemented"] is not False
        or report["commercial_offer_ready"] is not False
        or report["production_inventory_or_booking_activated"] is not False):
        raise ValueError("commercial permission cannot be granted by ZIP packaging")
    if destination.exists() or destination.is_symlink():
        raise ValueError("cannot overwrite reviewed source ZIP")
    destination.parent.mkdir(parents=True,exist_ok=True)
    with ZipFile(destination,"x",compression=ZIP_DEFLATED,compresslevel=9) as z:
        for relative in INCLUDE:
            file=PLUGIN/relative
            if file.is_symlink() or not file.is_file() or file.stat().st_size>100000:
                raise ValueError("untrusted package member")
            arcname="empire-caryard-gated/"+relative
            info=ZipInfo(arcname,date_time=(2026,10,22,0,0,0))
            info.compress_type=ZIP_DEFLATED
            info.external_attr=(0o644<<16)
            z.writestr(info,file.read_bytes(),compress_type=ZIP_DEFLATED,compresslevel=9)
    content=destination.read_bytes()
    with ZipFile(destination,"r") as z:
        if (set(z.namelist())!={"empire-caryard-gated/"+x for x in INCLUDE}
            or z.testzip() is not None
            or any(name.startswith("/") or ".." in name for name in z.namelist())):
            raise ValueError("invalid package payload")
    return {
        "status":"WORDPRESS_CARYARD_PLUGIN_OFFLINE_SOURCE_PACKAGE_ONLY",
        "file_count":len(INCLUDE),
        "zip_bytes":len(content),
        "zip_sha256":sha256(content).hexdigest(),
        "wordpress_runtime_tested":False,
        "plugin_installed_or_activated":False,
        "customer_booking_live":False,
        "production_changes":False,
    }


def main()->None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--package-offline",required=True,action="store_true")
    parser.parse_args()
    print(json.dumps(make_offline_zip(destination=ZIP),sort_keys=True))


if __name__=="__main__":
    main()
