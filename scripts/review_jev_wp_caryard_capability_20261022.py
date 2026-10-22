"""One-shot WordPress car-yard source and SQLite reference test receipt."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

from empire_os.jev_wp_caryard_plugin_gate import review_wp_caryard_plugin

ROOT=Path(__file__).resolve().parents[1]
PARENT=ROOT/"docs/commercial/JEV_WORDPRESS_SERVICE_HANDOVER_PREFLIGHT_20261022.json"
PLUGIN=ROOT/"prototypes/agency_wordpress_service_handoff_20261022/plugins/empire-caryard-gated"
OUTPUT=ROOT/"docs/commercial/JEV_CARYARD_INVENTORY_BOOKING_STATIC_PREFLIGHT_20261022.json"


def current_review()->dict:
    if PARENT.is_symlink() or not PARENT.is_file() or not 0<PARENT.stat().st_size<100000:
        raise ValueError("parent theme evidence unavailable")
    parent=json.loads(PARENT.read_text("utf8"))
    result=review_wp_caryard_plugin(PLUGIN,source_review=parent)
    result["parent_wordpress_theme_static_review_sha256"]=sha256(PARENT.read_bytes()).hexdigest()
    result["audit_at_utc"]=datetime.now(timezone.utc).isoformat()
    result["plugin_installation_performed"]=False
    result["plugin_activation_or_schema_migration_performed"]=False
    result["php_parser_or_php_lint_executed"]=False
    result["all_tests_in_nonproduction_isolated_worktree"]=True
    result["customer_contact_fields_requested"]=0
    return result


def main()->None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--review-static-only",required=True,action="store_true")
    parser.parse_args()
    if OUTPUT.exists() or OUTPUT.is_symlink() or not OUTPUT.parent.is_dir():
        raise ValueError("original capability evidence receipt cannot be overwritten")
    report=current_review()
    with OUTPUT.open("x",encoding="utf-8") as f:
        json.dump(report,f,sort_keys=True,indent=2)
        f.write("\n")
    print(json.dumps({
        "status":report["status"],
        "php_files_checked":report["source_files_checked"],
        "sqlite_atomic_slots":report["sqlite_reference_conflict_model"],
        "wp_runtime_tested":report["actual_wordpress_php_and_mysql_semantics_tested"],
        "public_booking":report["public_customer_booking_or_calendar_implemented"],
        "production_writes":report["database_writes"],
    },sort_keys=True))


if __name__=="__main__":
    main()
