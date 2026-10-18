"""Read-only stream mining over EXISTING EmpireOS canonical observers.

No new data lake or ingestion queue: source adapters read the existing
acquisition inbox, Opportunity Factory evidence router, Quant Brain and
competitive intelligence. Results are aggregate quality evidence and bounded
OBSERVE department instructions, never identities, buyer intent or economics.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

from empire_os.opportunity_evidence_router import ROUTES

SCHEMA = "empire.revenue_stream_mining.review.v1"
MAX_BYTES = 2_000_000
MAX_ROWS = 4000
SOURCES = {
    "acquisition": ("runtime/acquisition/signal_inbox.json", None, None),
    "opportunity_routes": ("runtime/opportunity_factory/evidence_routes_latest.json",
                           "empire.opportunity_evidence_routes.v1", 24),
    "quant": ("runtime/opportunity_factory/quant_review_latest.json",
              "empire.opportunity_quant_review.v1", 24),
    "competitor": ("runtime/competitive_intelligence/competitor_intelligence_feed_latest.json",
                   "empire.competitor_intelligence_feed.v1", 168),
}
LANES = {
    "acquisition": ("market_intelligence", "mine_new_public_source_signals_and_check_source_quality", 83),
    "public_opportunity": ("market_intelligence", "research_public_evidence_for_existing_opportunity_blockers", 88),
    "commercial_opportunity": ("business_development", "verify_direct_buyer_terms_and_intent_from_first_party_evidence", 96),
    "quant_economics": ("data_quant", "recover_evidenced_conversion_probability_cost_and_unit_economics", 91),
    "competitor": ("marketing_growth", "refresh_competitor_market_and_search_source_evidence", 61),
}


def _time(text: Any) -> datetime | None:
    if not isinstance(text, str) or len(text) > 60:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except (ValueError, OverflowError):
        return None
    return parsed.astimezone(timezone.utc) if parsed.utcoffset() is not None else None


def _source(root: Path, name: str, now: datetime) -> tuple[str, Any]:
    rel, schema, max_age_hours = SOURCES[name]
    file = root / rel
    try:
        if (file.is_symlink() or file.parent.is_symlink()
                or (root / "runtime").is_symlink() or not file.is_file()):
            return "MISSING", None
        if not 0 < file.stat().st_size <= MAX_BYTES:
            return "INVALID", None
        payload = json.loads(file.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        return "UNAVAILABLE", None
    if not isinstance(payload, dict):
        return "INVALID", None
    if schema is None:
        if len(payload) > MAX_ROWS:
            return "INVALID", None
        return "OBSERVED", payload
    if (payload.get("schema_version") != schema
            or payload.get("mode") != "OBSERVE"
            or payload.get("execution_authority") != "none"):
        return "UNTRUSTED", None
    stamp = _time(payload.get("generated_at"))
    if stamp is None:
        return "UNTRUSTED", None
    elapsed = now - stamp
    if elapsed < timedelta(0):
        return "FUTURE_HELD", None
    if elapsed > timedelta(hours=max_age_hours):
        return "STALE", None
    return "FRESH", payload


def _acquisition(data: Mapping[str, Any], now: datetime) -> dict[str, Any] | None:
    family_counts: Counter[str] = Counter()
    new_counts: Counter[str] = Counter()
    repeated = 0
    identities: set[str] = set()
    for key, row in data.items():
        if not isinstance(row, Mapping):
            return None
        fingerprint = row.get("signal_id")
        if (not isinstance(fingerprint, str) or len(fingerprint) != 64
                or any(c not in "0123456789abcdef" for c in fingerprint)
                or fingerprint in identities or fingerprint != key
                or row.get("execution_authority") != "none"):
            return None
        identities.add(fingerprint)
        source = row.get("source")
        if not isinstance(source, str) or not 1 <= len(source) <= 80:
            return None
        from empire_os.permit_intelligence_runtime import PERMIT_SOURCES
        group = (
            "official_permit" if source in PERMIT_SOURCES or "permit" in source
            else "public_event" if source in ("nws_alerts", "chicago_311")
            else "other_pre_identity_signal"
        )
        family_counts[group] += 1
        if type(row.get("seen_count")) is not int or row["seen_count"] < 1:
            return None
        repeated += row["seen_count"] > 1
        created = _time(row.get("created_at"))
        last = _time(row.get("last_seen_at"))
        if created is None or last is None or created > last or last > now:
            return None
        if now - created <= timedelta(hours=24):
            new_counts[group] += 1
    counts = {
        "signal_inventory": len(identities),
        "repeat_observation_records": repeated,
        "new_first_observations_24h": sum(new_counts.values()),
        "permit_source_signals": family_counts["official_permit"],
        "other_source_signals": len(identities) - family_counts["official_permit"],
        "public_source_activity_24h": sum(new_counts.values()),
    }
    fingerprint = sha256(json.dumps(
        [sorted(identities), dict(sorted(family_counts.items()))],
        separators=(",", ":"), sort_keys=True,
    ).encode()).hexdigest()
    return dict(counts=counts, signal_digest=fingerprint,
                evidence_kind="PRE_IDENTITY_SOURCE_EVENTS",
                commercial_proof=False,
                no_automatic_prospect_creation=True)


def _routes(data: Mapping[str, Any]) -> dict[str, Any] | None:
    rows = data.get("items")
    if not isinstance(rows, list) or len(rows) > MAX_ROWS:
        return None
    declared = data.get("opportunity_count")
    if type(declared) is not int or declared != len(rows):
        return None
    public: Counter[str] = Counter()
    commercial: Counter[str] = Counter()
    internal: Counter[str] = Counter()
    keys: set[str] = set()
    for record in rows:
        if not isinstance(record, Mapping) or record.get("execution_authority") != "none":
            return None
        key = record.get("opportunity_key")
        if not isinstance(key, str) or not key or key in keys:
            return None
        keys.add(key)
        if record.get("tenant_id") not in (None, ""):
            return None
        routes = record.get("routes")
        if (not isinstance(routes, list) or len(routes) > 40
                or record.get("route_count") != len(routes)):
            return None
        for route in routes:
            if not isinstance(route, Mapping):
                return None
            blocker = route.get("blocker")
            known = ROUTES.get(blocker)
            if known is None:
                continue  # unknown blocker is not promoted into a miner.
            if any(route.get(field) != value for field, value in known.items()):
                return None
            if known["mode"] == "commercial_observation":
                commercial[blocker] += 1
            elif known["blocker_can_be_satisfied_by_public_search"]:
                public[blocker] += 1
            else:
                internal[blocker] += 1
    return {
        "opportunity_count": len(keys),
        "public_blocker_count": sum(public.values()),
        "commercial_observation_blocker_count": sum(commercial.values()),
        "internal_analysis_blocker_count": sum(internal.values()),
        "public_blockers_by_type": dict(sorted(public.items())),
        "commercial_blockers_by_type": dict(sorted(commercial.items())),
        "internal_blockers_by_type": dict(sorted(internal.items())),
        "evidence_kind": "CANONICAL_OPPORTUNITY_GAPS",
        "commercial_proof": False,
    }


def _quant(data: Mapping[str, Any]) -> dict[str, Any] | None:
    # Use the SAME source revalidation contract from Predictive Formula
    # Evidence, rather than another synthetic probability/ROI calculation.
    from empire_os.predictive_formula_evidence_review import _quant_review_counts
    rows = data.get("items")
    if not isinstance(rows, list) or any(
        not isinstance(row, Mapping) or row.get("tenant_id") not in (None, "")
        for row in rows
    ):
        return None
    return _quant_review_counts(data)


def _competitor(data: Mapping[str, Any]) -> dict[str, Any] | None:
    n = data.get("canonical_company_count")
    if type(n) is not int or not 0 <= n <= MAX_ROWS:
        return None
    if (data.get("buyer_intent_inferred") is not False
            or data.get("commercial_intent_inferred") is not False
            or data.get("revenue_opportunity_inferred") is not False):
        return None
    return {
        "historical_resolved_company_count": n,
        "observed_market_roster_not_sales": True,
        "buyer_intent_inferred": False,
        "revenue_verified": False,
    }


def _lane(name: str, counts: Mapping[str, Any] | None, status: str,
          source: str) -> dict[str, Any]:
    dept, action, priority = LANES[name]
    safe = counts or {}
    if name == "acquisition":
        safe = safe.get("counts") or {}
    # Never serialize raw identifiers or contact fields in department packets.
    if name == "acquisition":
        keys = ("signal_inventory", "new_first_observations_24h",
                "permit_source_signals", "other_source_signals")
    elif name == "public_opportunity":
        keys = ("opportunity_count", "public_blocker_count")
    elif name == "commercial_opportunity":
        keys = ("opportunity_count", "commercial_observation_blocker_count")
    elif name == "quant_economics":
        keys = ("candidate_count", "available_quant_decision_count",
                "missing_quant_economics_count")
    else:
        keys = ("historical_resolved_company_count",)
    filtered = {key: safe[key] for key in keys if type(safe.get(key)) is int}
    review_code = {
        "acquisition": "SOURCE_PRE_IDENTITY_EVENT_TRIAGE",
        "public_opportunity": "RESEARCH_EXISTING_PUBLIC_BLOCKER_PROOFS",
        "commercial_opportunity": "VERIFY_FIRST_PARTY_COMMERCIAL_TERMS",
        "quant_economics": "VERIFY_CANONICAL_QUANT_INPUT_ECONOMICS",
        "competitor": "REFRESH_COMPETITOR_SOURCE_QUALITY",
    }[name]
    value = {
        "stream": name, "status": status,
        "department": dept, "next_internal_action": action,
        "priority": priority, "review_code": review_code,
        "source_ref": "runtime:" + source.removeprefix("runtime/").removesuffix(".json").replace("/", ":"),
        "counts": filtered, "cost_budget_cents": 0,
        "data_mining_mode": "CANONICAL_READ_ONLY_REVIEW",
        "genuine_buyer_proven": False, "revenue_verified": False,
        "external_execution_authorized": False, "execution_authority": "none",
    }
    # Fingerprint only SOURCE-VALUE evidence, not heartbeat timestamps.
    fingerprint_counts = dict(filtered)
    # A rolling 24h window ageing out is not a new source discovery.
    if name == "acquisition":
        fingerprint_counts.pop("new_first_observations_24h", None)
    canonical = json.dumps(
        {"stream": name, "status": status, "counts": fingerprint_counts},
        sort_keys=True, separators=(",", ":"),
    )
    if name == "acquisition" and counts:
        canonical += str(counts.get("signal_digest") or "")
    value["evidence_fingerprint"] = sha256(canonical.encode()).hexdigest()
    return value


def build_revenue_stream_mining(
    repo_root: Path, *, as_of: datetime | None = None,
) -> dict[str, Any]:
    now = as_of or datetime.now(timezone.utc)
    if now.utcoffset() is None:
        raise ValueError("timezone-aware as_of required")
    now = now.astimezone(timezone.utc)
    root = Path(repo_root).resolve()
    raw = {name: _source(root, name, now) for name in SOURCES}
    quality: dict[str, Any] = {}
    for name, (status, data) in raw.items():
        normalized = None
        if data is not None:
            normalized = (
                _acquisition(data, now) if name == "acquisition"
                else _routes(data) if name == "opportunity_routes"
                else _quant(data) if name == "quant"
                else _competitor(data)
            )
            if normalized is None:
                status = "UNTRUSTED"
        quality[name] = {
            "status": status,
            "aggregate": normalized if status in ("OBSERVED", "FRESH") else None,
        }
    acquisition = quality["acquisition"]
    routes = quality["opportunity_routes"]
    quant = quality["quant"]
    comp = quality["competitor"]
    route_count = routes["aggregate"] or {}
    lanes = [
        _lane("acquisition", acquisition["aggregate"], acquisition["status"], SOURCES["acquisition"][0]),
        _lane("public_opportunity", route_count, routes["status"], SOURCES["opportunity_routes"][0]),
        _lane("commercial_opportunity", route_count, routes["status"], SOURCES["opportunity_routes"][0]),
        _lane("quant_economics", quant["aggregate"], quant["status"], SOURCES["quant"][0]),
        _lane("competitor", comp["aggregate"], comp["status"], SOURCES["competitor"][0]),
    ]
    return {
        "schema_version": SCHEMA, "mode": "OBSERVE", "generated_at": now.isoformat(),
        "status": "MINING_REVIEW_READY" if any(
            lane["status"] in ("FRESH", "OBSERVED") for lane in lanes)
            else "SOURCE_REFRESH_REQUIRED",
        "source_count": len(SOURCES),
        "lane_count": len(lanes),
        "sources": quality,
        "department_lanes": lanes,
        "same_source_rows_may_appear_in_multiple_lanes": True,
        "cross_lane_counts_are_not_additive": True,
        "raw_contacts_or_customer_rows_returned": False,
        "new_data_downloaded": False,
        "paid_api_called": False,
        "worker_dispatched": False,
        "commercial_execution_authorized": False,
        "external_outbound_authorized": False,
        "payment_authorized": False,
        "execution_authority": "none",
    }


def enqueue_existing_department_mining(
    repo_root: Path,
    review: Mapping[str, Any],
    *,
    max_jobs: int = 4,
    allow_noncanonical_test: bool = False,
) -> dict[str, Any]:
    """Optional internal handoff to the EXISTING ASTRA department work queue.

    The standard review never enqueues. No new scheduler, worker, DB or
    permissions. Fingerprinted work IDs make replay idempotent; expired/stale,
    tenant-scoped and empty evidence is not dispatched.
    """
    from empire_os.department_work_queue import DepartmentWorkQueue

    root = Path(repo_root).resolve()
    if root != Path("/srv/empire_os") and not allow_noncanonical_test:
        raise PermissionError("ONLY_CANONICAL_DEPARTMENT_QUEUE_OR_EXPLICIT_TEST")
    if type(max_jobs) is not int or not 1 <= max_jobs <= 4:
        raise ValueError("max_jobs must be 1..4")
    if (not isinstance(review, Mapping)
            or review.get("schema_version") != SCHEMA
            or review.get("mode") != "OBSERVE"
            or review.get("worker_dispatched") is not False
            or review.get("execution_authority") != "none"):
        raise ValueError("untrusted mining report")
    if not isinstance(review.get("department_lanes"), list):
        raise ValueError("invalid mining lanes")
    stamp = _time(review.get("generated_at"))
    current = datetime.now(timezone.utc)
    if stamp is None or not timedelta(0) <= current - stamp <= timedelta(minutes=15):
        raise ValueError("mining report timestamp stale or in future")
    verified = build_revenue_stream_mining(root, as_of=current)
    if review.get("source_count") != verified["source_count"]:
        raise ValueError("stream inventory drift")
    current_lanes = {lane["stream"]: lane for lane in verified["department_lanes"]}
    for candidate in review["department_lanes"]:
        if not isinstance(candidate, Mapping):
            raise ValueError("invalid mining lane")
        current_lane = current_lanes.get(candidate.get("stream"))
        # Recheck ALL trusted routing and authority fields. Otherwise a
        # caller could keep the same digest but forge department/source path.
        if current_lane is None or dict(candidate) != current_lane:
            raise ValueError("mining report source drift or tampering")
    lanes = review["department_lanes"]
    if (len(lanes) != len(LANES)
            or {row.get("stream") for row in lanes if isinstance(row, Mapping)}
            != set(LANES)):
        raise ValueError("invalid source-mining lane inventory")
    enqueued: list[dict[str, Any]] = []
    skipped: list[str] = []
    queue = DepartmentWorkQueue(root)
    for row in sorted(lanes, key=lambda item: -int(item["priority"])):
        name = row["stream"]
        expected_dept, expected_action, expected_priority = LANES[name]
        if (row.get("department") != expected_dept
                or row.get("next_internal_action") != expected_action
                or row.get("priority") != expected_priority
                or row.get("execution_authority") != "none"
                or row.get("external_execution_authorized") is not False
                or row.get("revenue_verified") is not False):
            raise ValueError("mining lane authority mismatch")
        fingerprint = row.get("evidence_fingerprint")
        if (not isinstance(fingerprint, str) or len(fingerprint) != 64
                or any(c not in "0123456789abcdef" for c in fingerprint)):
            raise ValueError("untrusted mining fingerprint")
        count = row.get("counts") or {}
        has_work = (
            count.get("other_source_signals", 0) > 0 if name == "acquisition"
            else count.get("public_blocker_count", 0) > 0 if name == "public_opportunity"
            else count.get("commercial_observation_blocker_count", 0) > 0
                if name == "commercial_opportunity"
            else count.get("missing_quant_economics_count", 0) > 0
                if name == "quant_economics"
            else False  # Existing Marketing source team owns stale competitor data.
        )
        if row["status"] not in ("FRESH", "OBSERVED") or not has_work:
            skipped.append(name)
            continue
        if len(enqueued) >= max_jobs:
            skipped.append(name)
            continue
        packet = {
            "step_id": f"mine_{name}_{fingerprint[:16]}",
            "goal_key": "mine_existing_canonical_source_stream_evidence",
            "department_keys": [expected_dept],
            "target_component": "existing_source_intelligence_and_opportunity_factory",
            "action": expected_action,
            "authority": "observe",
            "evidence_refs": [row["source_ref"]],
            "rationale": "Review bounded source/evidence gaps, not prospects, pricing or sales",
            "success_condition": "Evidence-backed internal findings returned to canonical Source Intelligence/Opportunity Factory; no inferred sales",
            "intelligence_request": {
                "stream_mining_review": {
                    "lane": name,
                    "source_ref": row["source_ref"],
                    "evidence_fingerprint": fingerprint,
                    "review_code": row["review_code"],
                    "safe_counts": dict(count),
                    "no_private_customer_rows_or_contact_fields": True,
                    "do_not_infer_probabilities_or_revenue": True,
                },
                "budget": {
                    "requested_model_tokens": 0,
                    "requested_external_cost_cents": 0,
                },
            },
        }
        item, created = queue.enqueue_step(
            plan_id="revenue_stream_mining_v1",
            step=packet,
            priority=expected_priority,
        )
        enqueued.append({
            "stream": name, "department": expected_dept,
            "work_id": item.id,
            "status": "QUEUED" if created else "ALREADY_QUEUED",
        })
    return {
        "schema_version": "empire.revenue_stream_mining.department_handoff.v1",
        "status": "ROUTED_TO_EXISTING_DEPARTMENT_QUEUE",
        "mode": "OBSERVE",
        "jobs_new": sum(item["status"] == "QUEUED" for item in enqueued),
        "jobs_duplicate": sum(item["status"] == "ALREADY_QUEUED" for item in enqueued),
        "jobs": enqueued, "skipped_lanes": skipped,
        "new_queue_created": False, "new_scheduler_created": False,
        "money_spent": False, "external_messages_sent": False,
        "execution_authority": "none",
    }
