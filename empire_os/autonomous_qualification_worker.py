#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

from empire_os.lead_scoring import compute_lead_score
from empire_os.prospect_enrichment import enrich_prospect_for_scoring


ENV_PATH = "/etc/empire_os.env"


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}

    with open(ENV_PATH, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if (
                line
                and not line.startswith("#")
                and "=" in line
            ):
                key, value = line.split("=", 1)
                env[key] = value

    return env


ENV = load_env()

BASE = ENV["SUPABASE_URL"].rstrip("/")
KEY = ENV["SUPABASE_SERVICE_KEY"]

HEADERS = {
    "apikey": KEY,
    "Authorization": "Bearer " + KEY,
    "Content-Type": "application/json",
    "Accept": "application/json",
}


def request_json(
    method: str,
    path: str,
    payload: Any | None = None,
    *,
    prefer: str | None = None,
) -> Any:
    headers = dict(HEADERS)

    if prefer:
        headers["Prefer"] = prefer

    data = (
        json.dumps(payload).encode("utf-8")
        if payload is not None
        else None
    )

    req = urllib.request.Request(
        BASE + path,
        data=data,
        method=method,
        headers=headers,
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else None

    except urllib.error.HTTPError as exc:
        body = exc.read().decode(
            "utf-8",
            errors="replace",
        )
        raise RuntimeError(
            f"{method} {path} -> HTTP {exc.code}: "
            f"{body[:1000]}"
        ) from exc


def fetch_prospect(prospect_id: str) -> dict[str, Any]:
    select = ",".join(
        (
            "id",
            "created_at",
            "business_name",
            "niche",
            "metro",
            "phone",
            "website",
            "address",
            "rating",
            "review_count",
            "buy_signal_score",
            "runs_ads",
            "status",
            "notes",
            "contacted_at",
            "contact_name",
            "contact_title",
            "contact_source",
            "contacted_status",
        )
    )

    params = urllib.parse.urlencode(
        {
            "select": select,
            "id": f"eq.{prospect_id}",
            "limit": 1,
        }
    )

    rows = request_json(
        "GET",
        f"/rest/v1/prospects?{params}",
    )

    if not rows:
        raise RuntimeError(
            f"prospect not found: {prospect_id}"
        )

    return rows[0]


def upsert_qualification(
    prospect: dict[str, Any],
    result: dict[str, Any],
) -> dict[str, Any]:
    prospect_id = prospect["id"]

    payload = {
        "prospect_id": prospect_id,
        "score": result["composite_score"],
        "tier": result["tier"],
        "data_completeness_score": result["dimensions"].get(
            "data_completeness",
            0,
        ),
        "business_presence_score": result["dimensions"].get(
            "business_presence",
            0,
        ),
        "market_fit_score": result["dimensions"].get(
            "market_fit",
            0,
        ),
        "engagement_potential_score": result["dimensions"].get(
            "engagement_potential",
            0,
        ),
        "enrichment_quality_score": result["dimensions"].get(
            "enrichment_quality",
            0,
        ),
        "recommended_action": result["recommended_action"],
        "scoring_engine": "empire_os.lead_scoring",
        "scoring_version": "v1",
        "input_snapshot": prospect,
        "result_payload": result,
        "status": "scored",
        "scored_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    params = urllib.parse.urlencode(
        {
            "on_conflict": (
                "prospect_id,scoring_engine,"
                "scoring_version"
            )
        }
    )

    rows = request_json(
        "POST",
        f"/rest/v1/prospect_qualifications?{params}",
        payload=payload,
        prefer=(
            "resolution=merge-duplicates,"
            "return=representation"
        ),
    )

    if not rows:
        raise RuntimeError(
            "qualification upsert returned no row"
        )

    return rows[0]


def emit_event(
    *,
    prospect_id: str,
    qualification_id: str,
    result: dict[str, Any],
) -> None:
    event = {
        "event_type": "prospect_qualified",
        "prospect_id": prospect_id,
        "channel": "qualification",
        "actor": "autonomous_qualification_worker_v1",
        "payload": {
            "qualification_id": qualification_id,
            "score": result["composite_score"],
            "tier": result["tier"],
            "scoring_version": "v1",
        },
        "occurred_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "idempotency_key": (
            f"prospect:{prospect_id}:qualified:v1"
        ),
    }

    try:
        request_json(
            "POST",
            "/rest/v1/commercial_events",
            payload=event,
            prefer="return=minimal",
        )
    except RuntimeError as exc:
        message = str(exc)

        duplicate_event = (
            "HTTP 409" in message
            and '"code":"23505"' in message
            and (
                "uq_commercial_events_idempotency_key"
                in message
            )
        )

        if not duplicate_event:
            raise


def qualify(prospect_id: str) -> dict[str, Any]:
    prospect = fetch_prospect(prospect_id)

    score_input = dict(prospect)

    # The current prospects table does not contain all fields
    # expected by the legacy scorer. Missing values remain zero.
    score_input.setdefault("email", None)
    score_input.setdefault(
        "street",
        prospect.get("address"),
    )
    score_input.setdefault("omega_score", 0)
    score_input.setdefault("enrichment_score", 0)
    score_input.setdefault("social_links", [])

    initial_result = compute_lead_score(score_input)
    enrichment: dict[str, Any] | None = None

    # Enrichment is driven by missing evidence, not preliminary tier.
    required_fields = (
        "email",
        "contact_name",
        "website",
        "street",
        "city",
        "state",
        "zip",
        "social_links",
    )
    missing_fields = [
        field
        for field in required_fields
        if not score_input.get(field)
        and score_input.get(field) != 0
    ]

    should_enrich = bool(missing_fields) and (
        initial_result["tier"] in {"cold", "warm"}
        or not score_input.get("enrichment_score")
    )

    if should_enrich:
        enrichment = enrich_prospect_for_scoring(prospect)
        score_input.update(enrichment.get("fields", {}))
        score_input["enrichment_score"] = enrichment.get(
            "enrichment_score",
            0,
        )
        score_input["omega_score"] = prospect.get("omega_score", 0) or 0

        result = compute_lead_score(score_input)
        result["enrichment"] = enrichment
        result["enrichment_trigger"] = {
            "missing_fields": missing_fields,
            "initial_tier": initial_result["tier"],
        }
    else:
        result = initial_result

    qualification = upsert_qualification(
        prospect,
        result,
    )

    emit_event(
        prospect_id=prospect_id,
        qualification_id=str(qualification["id"]),
        result=result,
    )

    return {
        "ok": True,
        "prospect_id": prospect_id,
        "qualification_id": str(qualification["id"]),
        "score": result["composite_score"],
        "tier": result["tier"],
        "dimensions": result["dimensions"],
        "recommended_action": result["recommended_action"],
        "scoring_version": "v1",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--prospect-id",
        required=True,
    )

    args = parser.parse_args()

    result = qualify(args.prospect_id)

    print(
        json.dumps(
            result,
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
