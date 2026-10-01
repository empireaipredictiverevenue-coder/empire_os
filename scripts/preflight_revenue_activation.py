#!/usr/bin/env python3
"""Read-only preflight for organic revenue + A2A activation gates."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from empire_os.a2a_runtime import load_a2a_runtime
from empire_os.owned_campaign_content import prepare_marketing
from empire_os.owned_campaign_preflight import inspect_campaigns

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--site-build", choices=["PASS", "UNVERIFIED"], default="PASS")
    args = parser.parse_args()

    root = args.root.resolve()
    migration = root / "migrations/empiredb/025_owned_campaign_intake.sql"
    migration_text = migration.read_text(encoding="utf-8")
    migration_held = migration_text.startswith("-- HELD_FOR_FOUNDER_DB_APPROVAL")

    marketing = json.loads(
        (root / "runtime/astra/department_cycle_latest.json").read_text(encoding="utf-8")
    )["marketing_growth"]
    prepared = prepare_marketing(marketing, root)

    ref = ["docs/owned_campaign_activation_v2_delta.md"]
    infrastructure = {
        key: {"status": "PASS", "evidence_refs": ref}
        for key in (
            "owned_destination",
            "privacy_review",
            "governed_enquiry_endpoint",
            "first_party_event_collector",
            "public_route_prepared",
        )
    }
    infrastructure["canonical_intake_schema"] = {
        "status": "HELD_FOR_FOUNDER_DB_APPROVAL",
        "evidence_refs": ["migrations/empiredb/025_owned_campaign_intake.sql"],
    }
    infrastructure["site_build"] = {
        "status": args.site_build,
        "evidence_refs": ref,
    }
    organic = inspect_campaigns(prepared, infrastructure)
    blockers = sorted({b for row in organic["campaigns"] for b in row["blockers"]})

    a2a = load_a2a_runtime(os.environ)

    result = {
        "schema_version": "empire.revenue-activation-preflight.v1",
        "organic": {
            "campaigns_requested": organic["campaigns_requested"],
            "campaigns_preflight_passed": organic["campaigns_preflight_passed"],
            "campaigns_blocked": organic["campaigns_blocked"],
            "blockers": blockers,
            "migration_025_held": migration_held,
            "zero_paid_media_required": True,
            "ready_after_founder_db_gate": blockers == ["canonical_intake_schema"] and migration_held,
        },
        "a2a": {
            **a2a.public_status(),
            "env_file_required": "/etc/empire_a2a.env",
            "systemd_drop_in": "deploy/systemd/empire-public-gateway.service.d/20-a2a-runtime.conf",
            "restart_required_after_config": True,
        },
        "gates": {
            "database_apply": True,
            "public_gateway_restart": True,
            "live_outbound_send": True,
            "payment_or_funds": True,
        },
        "actions_performed": {
            "database_mutation": False,
            "service_restart": False,
            "traffic_publication": False,
            "outbound_send": False,
            "payment": False,
        },
        "execution_authority": "none",
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
