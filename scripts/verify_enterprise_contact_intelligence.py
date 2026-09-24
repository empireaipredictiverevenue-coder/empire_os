#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import urllib.parse

from empire_os.qualification_worker_v2 import request_json


ROOT = Path("/srv/empire_os")
INTEL = ROOT / "runtime/predictive_revenue/enterprise_contact_intelligence_latest.json"
ACTIVATION = ROOT / "runtime/predictive_revenue/enterprise_activation_latest.json"
BUYER = ROOT / "runtime/buyer_acquisition/latest.json"


def _read(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"runtime snapshot root not object:{path}")
    return value


def main() -> int:
    intel = _read(INTEL)
    activation = _read(ACTIVATION)
    buyer = _read(BUYER)

    ids = [
        str(row.get("prospect_id") or "").strip()
        for row in activation.get("targets") or []
        if isinstance(row, dict) and row.get("prospect_id")
    ]

    reviews = []
    if ids:
        params = urllib.parse.urlencode({
            "select": (
                "id,prospect_id,contact_name,contact_title,contact_email,"
                "offer_key,status,proposed_at"
            ),
            "prospect_id": f"in.({','.join(ids)})",
            "order": "proposed_at.desc",
            "limit": 50,
        })
        reviews = request_json(
            "GET",
            f"/rest/v1/buyer_candidate_reviews?{params}",
        ) or []

    summary = buyer.get(
        "predictive_revenue_enterprise_contact_intelligence"
    )
    if not isinstance(summary, dict):
        raise RuntimeError(
            "buyer acquisition missing enterprise contact intelligence summary"
        )

    payload = {
        "ok": (
            int(intel.get("error_count") or 0) == 0
            and intel.get("live_outbound_send") is False
            and intel.get("actual_revenue") is False
            and summary.get("live_outbound_send") is False
            and summary.get("actual_revenue") is False
        ),
        "proposed_review_count": int(
            intel.get("proposed_review_count") or 0
        ),
        "targeted_retry_queued_count": int(
            intel.get("targeted_retry_queued_count") or 0
        ),
        "error_count": int(intel.get("error_count") or 0),
        "enterprise_review_row_count": len(reviews),
        "reviews": [
            {
                "status": row.get("status"),
                "contact_name": row.get("contact_name"),
                "contact_title": row.get("contact_title"),
                "contact_email": row.get("contact_email"),
                "offer_key": row.get("offer_key"),
            }
            for row in reviews
            if isinstance(row, dict)
        ],
        "live_outbound_send": False,
        "payment_action": False,
        "actual_revenue": False,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))

    if intel.get("reviews_approved") not in (0, None):
        raise RuntimeError("enterprise contact sync approved buyer reviews")
    if intel.get("payment_action") is not False:
        raise RuntimeError("enterprise contact sync exposed payment action")
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
