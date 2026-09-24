#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import urllib.parse

from empire_os.buyer_probe_worker import rejection_reason, run as probe_buyer
from empire_os.crawler_runner import ingest_candidate
from empire_os.predictive_revenue_enterprise_acquisition import (
    TARGET_ACQUISITION,
    build_enterprise_lead_candidates,
)
from empire_os.predictive_revenue_enterprise_targets import TARGETS
from empire_os.qualification_worker_v2 import qualify_prospect, request_json


OUT = Path(
    "/srv/empire_os/runtime/predictive_revenue/"
    "enterprise_activation_latest.json"
)


def _prospect_id(result: dict) -> str:
    prospect = result.get("prospect")
    if isinstance(prospect, dict) and prospect.get("id"):
        return str(prospect["id"])
    value = result.get("prospect_id")
    return str(value or "").strip()


def _fetch_prospect(prospect_id: str) -> dict:
    params = urllib.parse.urlencode({
        "select": (
            "id,created_at,business_name,niche,metro,phone,website,"
            "address,buy_signal_score,status,notes,contact_name,"
            "contact_title,contact_source,contacted_status"
        ),
        "id": f"eq.{prospect_id}",
        "limit": 1,
    })
    rows = request_json(
        "GET",
        f"/rest/v1/prospects?{params}",
    ) or []
    if not rows or not isinstance(rows[0], dict):
        raise RuntimeError(
            f"canonical prospect not found after ingest:{prospect_id}"
        )
    return rows[0]


def _target_by_name() -> dict[str, object]:
    return {target.account_name: target for target in TARGETS}


def activate(*, probe: bool = True) -> dict:
    candidates = build_enterprise_lead_candidates()
    targets = _target_by_name()
    rows: list[dict] = []
    errors: list[dict] = []

    for candidate in candidates:
        target = targets[candidate.name]
        acquisition = TARGET_ACQUISITION[target.account_key]
        try:
            ingest = ingest_candidate(candidate)
            prospect_id = _prospect_id(ingest)
            if not prospect_id:
                raise RuntimeError(
                    f"ingest returned no prospect id:{candidate.name}"
                )

            prospect = _fetch_prospect(prospect_id)
            qualification = qualify_prospect(prospect)
            prospect = _fetch_prospect(prospect_id)

            probe_result = None
            if probe:
                probe_result = probe_buyer(
                    prospect,
                    max_pages=9,
                    request_timeout=4.0,
                    time_budget_seconds=22.0,
                    allow_company_routed=False,
                )
                probe_result["rejection_reason"] = rejection_reason(
                    probe_result
                )

            company_routes = [
                dict(item)
                for item in acquisition["company_contact_routes"]
            ]
            rows.append({
                "account_key": target.account_key,
                "account_name": target.account_name,
                "wave": target.wave,
                "prospect_id": prospect_id,
                "ingest_decision": ingest.get("decision"),
                "ingest_reason": ingest.get("reason"),
                "canonical_website": prospect.get("website"),
                "qualification": qualification,
                "probe": probe_result,
                "observed_people": [
                    dict(person)
                    for person in target.observed_people
                ],
                "company_contact_routes": company_routes,
                "company_route_count": len(company_routes),
                "person_contact_verified": bool(
                    probe_result
                    and probe_result.get("outreach_ready") is True
                    and probe_result.get("person_bound") is True
                    and probe_result.get("preferred_email")
                ),
                "review_ready": bool(
                    probe_result
                    and probe_result.get("review_ready") is True
                ),
                "outreach_ready": bool(
                    probe_result
                    and probe_result.get("outreach_ready") is True
                ),
                "outreach_authorized": False,
                "binding_intent_verified": False,
                "payment_action": False,
                "actual_revenue": False,
            })
        except Exception as exc:
            errors.append({
                "account_name": candidate.name,
                "error": f"{type(exc).__name__}:{str(exc)[:500]}",
            })

    rows.sort(key=lambda row: (row["wave"], row["account_name"]))
    payload = {
        "schema_version": (
            "empire.predictive-revenue-enterprise-activation.v1"
        ),
        "status": (
            "INTERNAL_REVIEW_READY"
            if rows and not errors
            else "PARTIAL_INTERNAL_REVIEW"
            if rows
            else "FAILED"
        ),
        "target_count": len(candidates),
        "canonical_prospect_count": len(rows),
        "failed_count": len(errors),
        "qualified_count": sum(
            1 for row in rows if row.get("qualification")
        ),
        "review_ready_count": sum(
            1 for row in rows if row["review_ready"]
        ),
        "person_contact_verified_count": sum(
            1 for row in rows if row["person_contact_verified"]
        ),
        "company_route_available_count": sum(
            1 for row in rows if row["company_route_count"] > 0
        ),
        "targets": rows,
        "errors": errors,
        "truth_rules": {
            "public_fit_is_buyer_intent": False,
            "observed_person_is_verified_contact": False,
            "company_route_is_person_bound": False,
            "generated_email_without_verification_is_contact": False,
            "reply_is_revenue": False,
            "meeting_is_revenue": False,
        },
        "mode": "INTERNAL_REVIEW",
        "live_outbound_send": False,
        "outreach_authorized": False,
        "payment_action": False,
        "actual_revenue": False,
        "execution_authority": "internal_write",
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    tmp.replace(OUT)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--skip-probe",
        action="store_true",
        help="ingest and qualify without first-party contact probing",
    )
    args = parser.parse_args()
    payload = activate(probe=not args.skip_probe)

    print(json.dumps({
        "status": payload["status"],
        "target_count": payload["target_count"],
        "canonical_prospect_count": payload[
            "canonical_prospect_count"
        ],
        "qualified_count": payload["qualified_count"],
        "review_ready_count": payload["review_ready_count"],
        "person_contact_verified_count": payload[
            "person_contact_verified_count"
        ],
        "company_route_available_count": payload[
            "company_route_available_count"
        ],
        "failed_count": payload["failed_count"],
        "live_outbound_send": payload["live_outbound_send"],
        "actual_revenue": payload["actual_revenue"],
    }, indent=2, sort_keys=True))
    return 0 if payload["canonical_prospect_count"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
