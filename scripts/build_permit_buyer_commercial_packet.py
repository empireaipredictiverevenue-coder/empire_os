#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import urllib.parse
from pathlib import Path

from empire_os.permit_buyer_commercial_packet import (
    build_permit_buyer_packet,
    write_permit_buyer_packet,
)
from empire_os.qualification_worker_v2 import request_json


def _candidate(domain: str) -> dict:
    query = urllib.parse.urlencode({
        "select": (
            "id,domain,business_name,website,buyer_type,"
            "target_product_codes,target_corridor_keys,site_evidence,"
            "reconciliation_state,review_state,last_seen_at"
        ),
        "domain": f"eq.{domain}",
        "order": "last_seen_at.desc",
        "limit": "1",
    })
    rows = request_json(
        "GET",
        "/rest/v1/buyer_scout_candidates?" + query,
    ) or []
    if not isinstance(rows, list) or len(rows) != 1:
        raise RuntimeError("exactly one buyer scout candidate required")
    if not isinstance(rows[0], dict):
        raise RuntimeError("buyer scout candidate payload invalid")
    return rows[0]


def _catalog() -> dict:
    rows = request_json(
        "POST",
        "/rest/v1/rpc/get_commercial_product_catalog",
        payload={
            "p_product_code": "permit_intelligence",
            "p_limit": 10,
        },
    ) or []
    if isinstance(rows, dict):
        rows = [rows]
    if not isinstance(rows, list):
        raise RuntimeError("commercial catalog payload invalid")
    matches = [
        dict(row)
        for row in rows
        if isinstance(row, dict)
        and row.get("product_code") == "permit_intelligence"
    ]
    if len(matches) != 1:
        raise RuntimeError("exact permit_intelligence catalog row required")
    return matches[0]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="/srv/empire_os")
    parser.add_argument("--domain", required=True)
    parser.add_argument("--evidence-file")
    args = parser.parse_args()

    root = Path(args.repo_root).resolve()
    domain = str(args.domain).strip().lower()
    evidence_path = (
        Path(args.evidence_file).resolve()
        if args.evidence_file
        else root / "evidence" / "buyers" / f"{domain}.json"
    )
    inventory_path = (
        root
        / "runtime/recovery/legacy_permit_inventory_summary.json"
    )

    candidate = _candidate(domain)
    catalog = _catalog()
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    public_evidence = json.loads(
        evidence_path.read_text(encoding="utf-8")
    )

    packet = build_permit_buyer_packet(
        candidate=candidate,
        inventory_summary=inventory,
        catalog=catalog,
        public_evidence=public_evidence,
    )
    output = write_permit_buyer_packet(root, packet)

    print(json.dumps({
        "ok": True,
        "output": str(output),
        "business_name": packet["buyer"]["business_name"],
        "conversation_ready": packet["conversation_ready"],
        "decision_maker_count": len(packet["decision_makers"]),
        "company_email_count": len(
            packet["contact_routes"]["emails"]
        ),
        "company_phone_count": len(
            packet["contact_routes"]["phones"]
        ),
        "verified_current_inventory": packet["supply"][
            "verified_current_inventory"
        ],
        "owner_identified_inventory": packet["supply"][
            "verified_current_owner_identified"
        ],
        "project_only_inventory": packet["supply"][
            "verified_current_project_only"
        ],
        "offer_amount_cents": packet["offer"]["amount_cents"],
        "offer_currency": packet["offer"]["currency"],
        "offer_unit": packet["offer"]["unit"],
        "live_outbound_send": packet["live_outbound_send"],
        "terms_accepted": packet["terms_accepted"],
        "actual_revenue": packet["actual_revenue"],
        "execution_authority": packet["execution_authority"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
