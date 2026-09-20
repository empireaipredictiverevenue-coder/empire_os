"""Bounded production qualification cycle for canonical Lead Scoring v2."""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

from empire_os.prospect_enrichment import enrich_prospect_for_scoring
from empire_os.qualification_v2 import build_v2_qualification_payload
from empire_os.runtime_env import load_runtime_env

ENV_PATH = "/etc/empire_os.env"
SCORING_ENGINE = "empire_os.lead_scoring"
SCORING_VERSION = "v2"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _client() -> tuple[str, dict[str, str]]:
    env = load_runtime_env(
        ENV_PATH,
        required=("SUPABASE_URL", "SUPABASE_SERVICE_KEY"),
    )
    base = env["SUPABASE_URL"].rstrip("/")
    key = env["SUPABASE_SERVICE_KEY"]
    return base, {
        "apikey": key,
        "Authorization": "Bearer " + key,
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
    base, headers = _client()
    if prefer:
        headers["Prefer"] = prefer
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        base + path,
        data=data,
        method=method,
        headers=headers,
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"{method} {path} -> HTTP {exc.code}: {body[:1000]}"
        ) from exc


def fetch_pending_prospects(limit: int = 10) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit), 25))
    select = ",".join(
        (
            "id", "created_at", "business_name", "niche", "metro",
            "phone", "website", "address", "rating", "review_count",
            "buy_signal_score", "runs_ads", "status", "notes",
            "contact_name", "contact_title", "contact_source",
        )
    )
    params = urllib.parse.urlencode(
        {"select": select, "order": "created_at.desc", "limit": limit * 4}
    )
    prospects = request_json("GET", f"/rest/v1/prospects?{params}") or []
    if not prospects:
        return []

    ids = [str(row["id"]) for row in prospects if row.get("id")]
    quoted = ",".join(ids)
    qparams = urllib.parse.urlencode(
        {
            "select": "prospect_id",
            "scoring_engine": f"eq.{SCORING_ENGINE}",
            "scoring_version": f"eq.{SCORING_VERSION}",
            "prospect_id": f"in.({quoted})",
        }
    )
    existing = request_json(
        "GET", f"/rest/v1/prospect_qualifications?{qparams}"
    ) or []
    done = {str(row.get("prospect_id")) for row in existing}
    return [row for row in prospects if str(row.get("id")) not in done][:limit]


def fetch_acquisition_website(prospect_id: str) -> str:
    params = urllib.parse.urlencode(
        {
            "select": "evidence,created_at",
            "prospect_id": f"eq.{prospect_id}",
            "order": "created_at.desc",
            "limit": 10,
        }
    )
    rows = request_json(
        "GET", f"/rest/v1/prospect_acquisitions?{params}"
    ) or []
    for row in rows:
        evidence = row.get("evidence") if isinstance(row, dict) else None
        raw = evidence.get("raw") if isinstance(evidence, dict) else None
        website = str(raw.get("business_website") or "").strip() if isinstance(raw, dict) else ""
        if website:
            return website
    return ""


def build_evidence_backed_payload(
    prospect: dict[str, Any],
    *,
    acquisition_website: str = "",
) -> dict[str, Any]:
    enrichment_input = dict(prospect)
    if acquisition_website:
        enrichment_input["_acquisition_website"] = acquisition_website

    enrichment = enrich_prospect_for_scoring(enrichment_input)
    scoring_input = dict(prospect)
    scoring_input.update(enrichment.get("fields") or {})
    scoring_input["enrichment_score"] = enrichment.get("enrichment_score", 0)

    evidence = list(enrichment.get("evidence") or [])
    presence_checked = any(
        item.get("source") in {"website", "identity_guard"}
        for item in evidence
        if isinstance(item, dict)
    )

    payload = build_v2_qualification_payload(
        scoring_input,
        buy_signal_observed=False,
        enrichment_observed=True,
        business_presence_checked=presence_checked,
    )
    payload["result_payload"] = {
        **payload["result_payload"],
        "enrichment": enrichment,
    }
    return payload


def upsert_qualification(payload: dict[str, Any]) -> dict[str, Any]:
    params = urllib.parse.urlencode(
        {"on_conflict": "prospect_id,scoring_engine,scoring_version"}
    )
    rows = request_json(
        "POST",
        f"/rest/v1/prospect_qualifications?{params}",
        payload=payload,
        prefer="resolution=merge-duplicates,return=representation",
    )
    if not rows:
        raise RuntimeError("qualification upsert returned no row")
    return rows[0]


def emit_event(
    *,
    prospect_id: str,
    qualification_id: str,
    payload: dict[str, Any],
) -> None:
    event = {
        "event_type": "prospect_qualified_v2",
        "prospect_id": prospect_id,
        "channel": "qualification",
        "actor": "qualification_worker_v2",
        "payload": {
            "qualification_id": qualification_id,
            "score": payload.get("score"),
            "tier": payload.get("tier"),
            "evidence_confidence": payload.get("evidence_confidence"),
            "scoring_version": SCORING_VERSION,
        },
        "occurred_at": _now(),
        "idempotency_key": f"prospect:{prospect_id}:qualified:v2",
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
        duplicate = "HTTP 409" in message and '"code":"23505"' in message
        if not duplicate:
            raise


def qualify_prospect(prospect: dict[str, Any]) -> dict[str, Any]:
    prospect_id = str(prospect["id"])
    website = fetch_acquisition_website(prospect_id)
    payload = build_evidence_backed_payload(
        prospect,
        acquisition_website=website,
    )
    row = upsert_qualification(payload)
    emit_event(
        prospect_id=prospect_id,
        qualification_id=str(row["id"]),
        payload=payload,
    )
    return {
        "prospect_id": prospect_id,
        "qualification_id": str(row["id"]),
        "score": payload.get("score"),
        "tier": payload.get("tier"),
        "evidence_confidence": payload.get("evidence_confidence"),
    }


def run_cycle(limit: int = 10) -> dict[str, Any]:
    prospects = fetch_pending_prospects(limit)
    results: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for prospect in prospects:
        try:
            results.append(qualify_prospect(prospect))
        except Exception as exc:
            errors.append(
                {
                    "prospect_id": str(prospect.get("id") or ""),
                    "error": f"{type(exc).__name__}:{str(exc)[:300]}",
                }
            )
    return {
        "schema_version": "qualification_cycle.v2",
        "ok": not errors,
        "attempted": len(prospects),
        "qualified": len(results),
        "failed": len(errors),
        "results": results,
        "errors": errors,
        "real_data_only": True,
        "outreach_enabled": False,
        "payment_enabled": False,
        "finished_at": _now(),
    }
