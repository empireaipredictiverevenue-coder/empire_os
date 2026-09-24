"""Bounded production qualification cycle for canonical Lead Scoring v2."""
from __future__ import annotations

import fcntl
import json
import os
from pathlib import Path
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

from empire_os.prospect_enrichment import enrich_prospect_for_scoring
from empire_os.qualification_v2 import build_v2_qualification_payload
from empire_os.runtime_env import load_runtime_env
from empire_os.singleton_identity_plan import (
    SingletonIdentityPlanError,
    build_singleton_identity_plan,
)

ENV_PATH = "/etc/empire_os.env"
SCORING_ENGINE = "empire_os.lead_scoring"
SCORING_VERSION = "v2"

_EGRESS_STATE_PATH = Path(os.getenv(
    "EMPIRE_SUPABASE_EGRESS_STATE_PATH",
    "/srv/empire_os/runtime/control/supabase_egress_state.json",
))
_EGRESS_LOCK_PATH = Path(os.getenv(
    "EMPIRE_SUPABASE_EGRESS_LOCK_PATH",
    "/srv/empire_os/runtime/control/supabase_egress_state.lock",
))
_DEFAULT_HOURLY_BUDGET = 3000
_DEFAULT_DAILY_BUDGET = 25000
_DEFAULT_PROBE_SECONDS = 1800


def _env_int(name: str, default: int, *, minimum: int = 1) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(minimum, value)


def _egress_now() -> float:
    return time.time()


def _load_egress_state(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _write_egress_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(state, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)


def _with_egress_lock(fn):
    _EGRESS_LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _EGRESS_LOCK_PATH.open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            return fn()
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def _reserve_supabase_request() -> None:
    """Fail closed before a runaway REST loop can exhaust hosted egress."""
    now = _egress_now()
    hourly_budget = _env_int(
        "EMPIRE_SUPABASE_MAX_REQUESTS_PER_HOUR",
        _DEFAULT_HOURLY_BUDGET,
    )
    daily_budget = _env_int(
        "EMPIRE_SUPABASE_MAX_REQUESTS_PER_DAY",
        _DEFAULT_DAILY_BUDGET,
    )
    probe_seconds = _env_int(
        "EMPIRE_SUPABASE_EGRESS_PROBE_SECONDS",
        _DEFAULT_PROBE_SECONDS,
        minimum=60,
    )

    def reserve():
        state = _load_egress_state(_EGRESS_STATE_PATH)
        circuit = state.get("circuit")
        if isinstance(circuit, dict) and circuit.get("open") is True:
            next_probe_at = float(circuit.get("next_probe_at") or 0)
            if now < next_probe_at:
                remaining = max(1, int(next_probe_at - now))
                raise RuntimeError(
                    "Supabase egress circuit open locally; "
                    f"next probe in {remaining}s"
                )
            # Reserve the single probe slot before leaving the lock. Other
            # processes fail closed until this probe succeeds or the lease
            # expires.
            circuit["next_probe_at"] = now + probe_seconds
            circuit["last_probe_reserved_at"] = now
            state["circuit"] = circuit
            _write_egress_state(_EGRESS_STATE_PATH, state)
            return

        hour_bucket = int(now // 3600)
        day_bucket = int(now // 86400)
        counts = state.get("counts")
        counts = dict(counts) if isinstance(counts, dict) else {}
        if counts.get("hour_bucket") != hour_bucket:
            counts["hour_bucket"] = hour_bucket
            counts["hour_count"] = 0
        if counts.get("day_bucket") != day_bucket:
            counts["day_bucket"] = day_bucket
            counts["day_count"] = 0

        hour_count = int(counts.get("hour_count") or 0)
        day_count = int(counts.get("day_count") or 0)
        if hour_count >= hourly_budget or day_count >= daily_budget:
            reason = (
                "hourly_request_budget_exceeded"
                if hour_count >= hourly_budget
                else "daily_request_budget_exceeded"
            )
            reset_at = (
                (hour_bucket + 1) * 3600
                if reason.startswith("hourly")
                else (day_bucket + 1) * 86400
            )
            state["circuit"] = {
                "open": True,
                "reason": reason,
                "opened_at": now,
                "next_probe_at": reset_at,
                "source": "local_request_budget",
            }
            state["counts"] = counts
            _write_egress_state(_EGRESS_STATE_PATH, state)
            raise RuntimeError(
                "Supabase egress circuit opened locally: " + reason
            )

        counts["hour_count"] = hour_count + 1
        counts["day_count"] = day_count + 1
        counts["updated_at"] = now
        state["counts"] = counts
        _write_egress_state(_EGRESS_STATE_PATH, state)

    _with_egress_lock(reserve)


def _open_supabase_egress_circuit(reason: str) -> None:
    now = _egress_now()
    probe_seconds = _env_int(
        "EMPIRE_SUPABASE_EGRESS_PROBE_SECONDS",
        _DEFAULT_PROBE_SECONDS,
        minimum=60,
    )

    def update():
        state = _load_egress_state(_EGRESS_STATE_PATH)
        state["circuit"] = {
            "open": True,
            "reason": reason,
            "opened_at": now,
            "next_probe_at": now + probe_seconds,
            "source": "supabase_response",
        }
        _write_egress_state(_EGRESS_STATE_PATH, state)

    _with_egress_lock(update)


def _close_supabase_egress_circuit() -> None:
    def update():
        state = _load_egress_state(_EGRESS_STATE_PATH)
        circuit = state.get("circuit")
        if not isinstance(circuit, dict) or circuit.get("open") is not True:
            return
        state["circuit"] = {
            "open": False,
            "reason": "probe_succeeded",
            "closed_at": _egress_now(),
        }
        _write_egress_state(_EGRESS_STATE_PATH, state)

    _with_egress_lock(update)


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
    _reserve_supabase_request()
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
            _close_supabase_egress_circuit()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        if (
            exc.code == 402
            and (
                "exceed_egress_quota" in body
                or "restricted due to the following violations" in body
            )
        ):
            _open_supabase_egress_circuit("exceed_egress_quota")
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


def fetch_unlinked_allocatable_prospects(
    limit: int = 10,
) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit), 25))
    qparams = urllib.parse.urlencode(
        {
            "select": "prospect_id,scored_at,result_payload",
            "scoring_engine": f"eq.{SCORING_ENGINE}",
            "scoring_version": f"eq.{SCORING_VERSION}",
            "status": "eq.scored",
            "tier": "in.(hot,warm)",
            "entity_id": "is.null",
            "order": "scored_at.desc",
            "limit": limit * 5,
        }
    )
    qualifications = request_json(
        "GET", f"/rest/v1/prospect_qualifications?{qparams}"
    ) or []
    ids: list[str] = []
    for row in qualifications:
        if not isinstance(row, dict) or not row.get("prospect_id"):
            continue
        result_payload = row.get("result_payload")
        identity_state = (
            result_payload.get("identity_resolution")
            if isinstance(result_payload, dict)
            else None
        )
        if (
            isinstance(identity_state, dict)
            and identity_state.get("attempted") is True
        ):
            continue
        ids.append(str(row["prospect_id"]))
        if len(ids) >= limit:
            break

    if not ids:
        return []

    select = ",".join(
        (
            "id", "created_at", "business_name", "niche", "metro",
            "phone", "website", "address", "rating", "review_count",
            "buy_signal_score", "runs_ads", "status", "notes",
            "contact_name", "contact_title", "contact_source",
        )
    )
    params = urllib.parse.urlencode(
        {
            "select": select,
            "id": f"in.({','.join(ids)})",
        }
    )
    rows = request_json("GET", f"/rest/v1/prospects?{params}") or []
    by_id = {
        str(row.get("id")): row
        for row in rows
        if isinstance(row, dict) and row.get("id")
    }
    return [by_id[pid] for pid in ids if pid in by_id]


def fetch_latest_acquisition(prospect_id: str) -> dict[str, Any] | None:
    params = urllib.parse.urlencode(
        {
            "select": "prospect_id,source,source_url,evidence,created_at",
            "prospect_id": f"eq.{prospect_id}",
            "order": "created_at.desc",
            "limit": 1,
        }
    )
    rows = request_json(
        "GET", f"/rest/v1/prospect_acquisitions?{params}"
    ) or []
    if not rows:
        return None
    row = rows[0]
    return row if isinstance(row, dict) else None


def acquisition_website(acquisition: dict[str, Any] | None) -> str:
    evidence = (
        acquisition.get("evidence")
        if isinstance(acquisition, dict)
        else None
    )
    raw = evidence.get("raw") if isinstance(evidence, dict) else None
    if not isinstance(raw, dict):
        return ""
    return str(
        raw.get("business_website")
        or (raw.get("osm_tags") or {}).get("website")
        or ""
    ).strip()


def resolve_acquisition_website(
    prospect: dict[str, Any],
    acquisition: dict[str, Any] | None,
) -> str:
    """Resolve the strongest current acquisition website evidence.

    Stored evidence wins when present. For sources with a bounded official
    member/detail page resolver, the live source may refresh missing website
    evidence in memory before Search Fabric is needed. This function does not
    mutate the acquisition ledger.
    """
    stored = acquisition_website(acquisition)
    if stored:
        return stored

    if not isinstance(acquisition, dict):
        return ""

    source = str(acquisition.get("source") or "").strip()
    source_url = str(acquisition.get("source_url") or "").strip()
    business_name = str(prospect.get("business_name") or "").strip()

    if (
        source != "recc_solar"
        or not source_url
        or not business_name
    ):
        return ""

    try:
        from empire_os.lead_sources.recc_solar import _detail
        candidate = _detail(business_name, source_url)
    except Exception:
        return ""

    raw = getattr(candidate, "raw", None) if candidate is not None else None
    if not isinstance(raw, dict):
        return ""
    return str(raw.get("business_website") or "").strip()


def fetch_active_identity_link(prospect_id: str) -> dict[str, Any] | None:
    params = urllib.parse.urlencode(
        {
            "select": "prospect_id,entity_id,match_method,match_score,active,created_at",
            "prospect_id": f"eq.{prospect_id}",
            "active": "eq.true",
            "order": "created_at.desc",
            "limit": 2,
        }
    )
    rows = request_json(
        "GET", f"/rest/v1/prospect_entity_links?{params}"
    ) or []
    links = [row for row in rows if isinstance(row, dict)]
    if len(links) > 1:
        raise RuntimeError("multiple active identity links")
    return links[0] if links else None


def resolve_identity(
    prospect: dict[str, Any],
    acquisition: dict[str, Any] | None,
    enrichment: dict[str, Any],
) -> str | None:
    prospect_id = str(prospect["id"])
    existing = fetch_active_identity_link(prospect_id)
    if existing:
        entity_id = str(existing.get("entity_id") or "").strip()
        if not entity_id:
            raise RuntimeError("active identity link missing entity id")
        return entity_id

    if not acquisition:
        return None

    try:
        plan = build_singleton_identity_plan(
            prospect=prospect,
            acquisition=acquisition,
            enrichment=enrichment,
        )
    except SingletonIdentityPlanError:
        return None

    entity_id = str(plan["entity_id_candidate"])
    entity_payload = {
        "id": entity_id,
        "canonical_name": plan["canonical_name_candidate"],
        "normalized_name": str(
            plan["canonical_name_candidate"]
        ).strip().lower(),
        "canonical_niche": plan["canonical_niche_candidate"],
        "canonical_metro": plan["canonical_metro_candidate"],
        "canonical_phone": plan["canonical_phone_candidate"],
        "canonical_website": plan["canonical_website_candidate"],
        "identity_confidence": plan["association_confidence"],
        "resolution_state": plan["resolution_state"],
        "provenance": {
            "resolver": "singleton_identity_plan.v1",
            "confidence_basis": plan["confidence_basis"],
            "evidence_assertions": plan["evidence_assertions"],
            "source": plan["source"],
        },
    }
    entity_params = urllib.parse.urlencode({"on_conflict": "id"})
    request_json(
        "POST",
        f"/rest/v1/business_entities?{entity_params}",
        payload=entity_payload,
        prefer="resolution=ignore-duplicates,return=minimal",
    )

    link_payload = {
        "prospect_id": prospect_id,
        "entity_id": entity_id,
        "match_method": "singleton_evidence_v1",
        "match_score": plan["association_confidence"],
        "evidence": {
            "confidence_basis": plan["confidence_basis"],
            "evidence_assertions": plan["evidence_assertions"],
            "source": plan["source"],
        },
        "active": True,
    }
    link_params = urllib.parse.urlencode(
        {"on_conflict": "prospect_id"}
    )
    request_json(
        "POST",
        f"/rest/v1/prospect_entity_links?{link_params}",
        payload=link_payload,
        prefer="resolution=ignore-duplicates,return=minimal",
    )

    verified = fetch_active_identity_link(prospect_id)
    verified_id = str(
        (verified or {}).get("entity_id") or ""
    ).strip()
    if verified_id != entity_id:
        raise RuntimeError("identity promotion verification failed")
    return entity_id


def verified_enrichment_website(
    prospect: dict[str, Any],
    enrichment: dict[str, Any],
) -> str:
    """Return only an identity-accepted discovered first-party website."""
    if str(prospect.get("website") or "").strip():
        return ""

    fields = enrichment.get("fields")
    if not isinstance(fields, dict):
        return ""
    website = str(fields.get("website") or "").strip()
    if not website:
        return ""

    evidence = enrichment.get("evidence")
    evidence = evidence if isinstance(evidence, list) else []
    guard_ok = any(
        isinstance(item, dict)
        and item.get("source") == "identity_guard"
        and item.get("accepted") is True
        for item in evidence
    )
    site_ok = any(
        isinstance(item, dict)
        and item.get("source") == "website"
        and item.get("accepted") is True
        for item in evidence
    )
    return website if guard_ok and site_ok else ""


def promote_verified_website(
    prospect: dict[str, Any],
    enrichment: dict[str, Any],
) -> str:
    """Persist a verified first-party site without overwriting canonical data."""
    website = verified_enrichment_website(prospect, enrichment)
    if not website:
        return ""

    prospect_id = str(prospect.get("id") or "").strip()
    if not prospect_id:
        raise RuntimeError("prospect id required for website promotion")

    params = urllib.parse.urlencode({"id": f"eq.{prospect_id}"})
    request_json(
        "PATCH",
        f"/rest/v1/prospects?{params}",
        payload={"website": website},
        prefer="return=minimal",
    )

    verify_params = urllib.parse.urlencode({
        "select": "id,website",
        "id": f"eq.{prospect_id}",
        "limit": 1,
    })
    rows = request_json(
        "GET",
        f"/rest/v1/prospects?{verify_params}",
    ) or []
    if (
        not isinstance(rows, list)
        or not rows
        or str(rows[0].get("website") or "").strip() != website
    ):
        raise RuntimeError("verified website promotion did not persist")
    return website


def build_evidence_backed_payload(
    prospect: dict[str, Any],
    *,
    acquisition_website: str = "",
    enrichment: dict[str, Any] | None = None,
    entity_id: str | None = None,
) -> dict[str, Any]:
    if enrichment is None:
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
        entity_id=entity_id,
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
    acquisition = fetch_latest_acquisition(prospect_id)
    website = resolve_acquisition_website(
        prospect,
        acquisition,
    )

    enrichment_input = dict(prospect)
    if website:
        enrichment_input["_acquisition_website"] = website
    enrichment = enrich_prospect_for_scoring(enrichment_input)

    promoted_website = promote_verified_website(
        prospect,
        enrichment,
    )
    if promoted_website:
        prospect = {
            **prospect,
            "website": promoted_website,
        }

    entity_id = resolve_identity(
        prospect,
        acquisition,
        enrichment,
    )
    payload = build_evidence_backed_payload(
        prospect,
        acquisition_website=website,
        enrichment=enrichment,
        entity_id=entity_id,
    )
    payload["result_payload"] = {
        **payload["result_payload"],
        "identity_resolution": {
            "attempted": True,
            "resolved": bool(entity_id),
            "entity_id": entity_id,
            "method": (
                "canonical_link_or_singleton_evidence"
                if entity_id
                else "singleton_evidence_unresolved"
            ),
            "attempted_at": _now(),
        },
    }
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
        "entity_id": entity_id,
        "identity_resolved": bool(entity_id),
        "verified_website_promoted": promoted_website or None,
    }


def _run_prospects(
    prospects: list[dict[str, Any]],
    *,
    schema_version: str,
) -> dict[str, Any]:
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
        "schema_version": schema_version,
        "ok": not errors,
        "attempted": len(prospects),
        "qualified": len(results),
        "failed": len(errors),
        "identity_resolved": sum(
            1 for row in results if row.get("identity_resolved")
        ),
        "results": results,
        "errors": errors,
        "real_data_only": True,
        "outreach_enabled": False,
        "payment_enabled": False,
        "finished_at": _now(),
    }


def run_cycle(limit: int = 10) -> dict[str, Any]:
    return _run_prospects(
        fetch_pending_prospects(limit),
        schema_version="qualification_cycle.v2",
    )


def run_identity_catchup(limit: int = 10) -> dict[str, Any]:
    return _run_prospects(
        fetch_unlinked_allocatable_prospects(limit),
        schema_version="qualification_identity_catchup.v1",
    )
