"""Package only an independently static-verified WordPress demo block theme.

Produces a local offline upload ZIP. No WordPress runtime, deployment,
marketplace application, CRM writes, mail or customer information.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED, ZipInfo
import hashlib
import json

from empire_os.jev_wp_delivery_capability import (
    review_wordpress_delivery,THEME_REQUIRED,
)

REPO=Path(__file__).resolve().parents[1]
DIR=REPO/"prototypes/agency_wordpress_service_handoff_20261022"
THEME=DIR/"empire-local-services"
SOURCE=REPO/"docs/commercial/JEV_DIRECT_B2B_PURCHASE_NEED_PRIORITY_20261022.json"
DIST=DIR/"dist/empire-local-services-capability-demo-0.1.0.zip"


def validate_and_pack(*,destination:Path)->dict:
    research=json.loads(SOURCE.read_text())
    checks=review_wordpress_delivery(THEME,research=research)
    if (checks["status"]!="WORDPRESS_BLOCK_THEME_STATIC_PREFLIGHT_PASS_RUNTIME_REQUIRED"
        or checks["website_client_handover_authorized"] is not False
        or checks["commercial_proposals_ready"]!=0
        or checks["wp_php_runtime_available_or_tested"] is not False
        or checks["outbound_sent"]!=0):
        raise ValueError("source package not in explicitly held development state")
    if destination.exists() or destination.is_symlink():
        raise ValueError("refuse overwrite original package")
    destination.parent.mkdir(parents=True,exist_ok=True)
    with ZipFile(destination,"x",compression=ZIP_DEFLATED,compresslevel=9) as z:
        for rel in THEME_REQUIRED:
            source=THEME/rel
            name="empire-local-services/"+rel
            info=ZipInfo(name,date_time=(2026,10,22,0,0,0))
            info.compress_type=ZIP_DEFLATED
            info.external_attr=(0o644<<16)
            z.writestr(info,source.read_bytes(),compress_type=ZIP_DEFLATED,compresslevel=9)
    content=destination.read_bytes()
    with ZipFile(destination,"r") as z:
        names=z.namelist()
        if (len(names)!=len(THEME_REQUIRED)
            or set(names)!={"empire-local-services/"+n for n in THEME_REQUIRED}
            or any(".." in n or n.startswith("/") for n in names)
            or z.testzip() is not None):
            raise ValueError("unsafe WordPress theme ZIP contents")
    return {
        "status":"OFFLINE_WORDPRESS_SOURCE_PACKAGE_ONLY",
        "zip_sha256":hashlib.sha256(content).hexdigest(),
        "zip_bytes":len(content),
        "theme_files":len(names),
        "wordpress_runtime_or_plugin_compatibility_tested":False,
        "current_client_delivery_ready":False,
        "businesses_contacted":0,
        "production_changes":False,
    }


def main()->None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--package-offline",action="store_true",required=True)
    args=parser.parse_args()
    result=validate_and_pack(destination=DIST)
    print(json.dumps(result,sort_keys=True))


if __name__=="__main__":
    main()
