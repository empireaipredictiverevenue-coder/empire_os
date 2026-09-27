"""Production buyer-recovery capability for EmpireOS.

This module owns the last-known-good opportunity seed snapshot and the bounded
local buyer-recovery action used when legacy hosted-data egress is contained.

It never writes canonical database state, sends outbound, accepts terms, moves
funds, recognizes revenue, or expands authority. Buyer Scout must still re-probe
first-party websites before a recovered seed becomes a research candidate.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Callable, Mapping

from empire_os.buyer_acquisition_scout import refresh_buyer_scout
from empire_os.buyer_recovery_repository import (
    BuyerRecoveryRepository,
    CanonicalBuyerRecoveryRepository,
    RequestBuyerRecoveryRepository,
)
from empire_os.supabase_egress_guard import supabase_egress_contained


RECOVERY_SEED_SNAPSHOT = Path(
    "runtime/buyer_acquisition/opportunity_seed_recovery.json"
)
RECOVERY_HEARTBEAT = Path(
    "runtime/buyer_acquisition/local_recovery_latest.json"
)

HOME_SERVICE_NICHES = frozenset({
    "plumbing",
    "general_contractor",
    "roofing",
    "residential_roofing",
    "roof_repair",
    "restoration",
    "water_damage_restoration",
    "hvac",
    "solar",
})


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(dict(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)
    return path


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def load_buyer_plan(repo_root: str | Path) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    return _load_json(root / "runtime/buyer_acquisition/latest.json")


def load_local_recovery_seeds(
    repo_root: str | Path,
    *,
    limit: int = 50,
) -> list[dict[str, Any]]:
    root = Path(repo_root).resolve()
    payload = _load_json(root / RECOVERY_SEED_SNAPSHOT)
    raw_rows = payload.get("seeds")
    if not isinstance(raw_rows, list):
        return []

    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for raw in raw_rows[:max(1, min(int(limit), 100))]:
        if not isinstance(raw, Mapping):
            continue
        row = dict(raw)
        prospect_id = str(row.get("id") or "").strip()
        website = str(row.get("website") or "").strip()
        opportunity_key = str(
            row.get("seed_opportunity_key") or ""
        ).strip()
        if not prospect_id or not website or not opportunity_key:
            continue
        key = (prospect_id, opportunity_key)
        if key in seen:
            continue
        seen.add(key)
        row["recovery_source"] = "last_known_good_snapshot"
        row["database_write_performed"] = False
        row["outbound_authorized"] = False
        rows.append(row)
    return rows


def write_local_recovery_snapshot(
    repo_root: str | Path,
    rows: list[Mapping[str, Any]],
    *,
    source: str = "canonical_rest_refresh",
) -> Path | None:
    """Persist only a non-empty, validated last-known-good seed set."""
    valid: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for raw in rows[:100]:
        if not isinstance(raw, Mapping):
            continue
        row = dict(raw)
        prospect_id = str(row.get("id") or "").strip()
        website = str(row.get("website") or "").strip()
        opportunity_key = str(
            row.get("seed_opportunity_key") or ""
        ).strip()
        if not prospect_id or not website or not opportunity_key:
            continue
        key = (prospect_id, opportunity_key)
        if key in seen:
            continue
        seen.add(key)
        row.pop("database_write_performed", None)
        row.pop("outbound_authorized", None)
        valid.append(row)

    if not valid:
        return None

    root = Path(repo_root).resolve()
    return _atomic_json(
        root / RECOVERY_SEED_SNAPSHOT,
        {
            "schema_version": "empire.opportunity_seed_recovery.v1",
            "generated_at": _utc_now(),
            "mode": "OBSERVE",
            "source": source,
            "database_write_performed": False,
            "outbound_authorized": False,
            "seeds": valid,
        },
    )


def query_opportunity_validation_seeds(
    plan: Mapping[str, Any],
    *,
    per_target: int = 6,
    request: Callable[..., Any] | None = None,
    repository: BuyerRecoveryRepository | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Read canonical prospects for qualified opportunities.

    A failed read is diagnostic evidence only. It never clears the last-known-
    good local snapshot.
    """
    validation = plan.get("opportunity_validation")
    validation = validation if isinstance(validation, Mapping) else {}
    targets = validation.get("targets")
    targets = targets if isinstance(targets, list) else []
    per_target = max(1, min(int(per_target), 10))
    if request is not None and repository is not None:
        raise ValueError("provide request or repository, not both")
    store = (
        repository
        if repository is not None
        else RequestBuyerRecoveryRepository(request)
        if request is not None
        else CanonicalBuyerRecoveryRepository.from_environment()
    )

    rows: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for target in targets[:10]:
        if not isinstance(target, Mapping):
            continue
        opportunity_key = str(
            target.get("opportunity_key") or ""
        ).strip()
        niche = str(target.get("niche_family") or "").strip()
        territory = str(target.get("territory") or "").strip()
        if not opportunity_key or not niche:
            continue

        try:
            batch = store.prospects_for_target(
                niche=niche,
                territory=territory,
                limit=per_target,
            )
        except Exception as exc:
            diagnostics.append({
                "opportunity_key": opportunity_key,
                "niche": niche,
                "territory": territory or None,
                "state": "ERROR",
                "row_count": 0,
                "error": f"{type(exc).__name__}:{str(exc)[:240]}",
            })
            continue

        diagnostics.append({
            "opportunity_key": opportunity_key,
            "niche": niche,
            "territory": territory or None,
            "state": "OK",
            "row_count": len(batch),
            "error": None,
        })

        for raw in batch:
            if not isinstance(raw, Mapping):
                continue
            prospect_id = str(raw.get("id") or "").strip()
            business_name = str(
                raw.get("business_name") or ""
            ).strip()
            website = str(raw.get("website") or "").strip()
            if not prospect_id or not business_name or not website:
                continue
            key = (prospect_id, opportunity_key)
            if key in seen:
                continue
            seen.add(key)

            row = dict(raw)
            row["seed_opportunity_key"] = opportunity_key
            row["seed_corridor_key"] = target.get("corridor_key")
            row["seed_product_code"] = target.get("product_code")
            row["seed_buyer_pools"] = [
                "end_service_buyers",
                "local_and_smb_buyers",
            ]
            if niche.casefold() in HOME_SERVICE_NICHES:
                row["icp_profile_key"] = "high_ticket_home_service"
            rows.append(row)

    return rows, diagnostics


def refresh_last_known_good_snapshot(
    repo_root: str | Path,
    *,
    request: Callable[..., Any] | None = None,
    repository: BuyerRecoveryRepository | None = None,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    plan = load_buyer_plan(root)
    rows, diagnostics = query_opportunity_validation_seeds(
        plan,
        request=request,
        repository=repository,
    )
    errors = [
        row for row in diagnostics
        if row.get("state") == "ERROR"
    ]

    refreshed = False
    path: Path | None = None
    if rows and not errors:
        path = write_local_recovery_snapshot(root, rows)
        refreshed = path is not None

    return {
        "ok": not errors,
        "state": (
            "REFRESHED"
            if refreshed
            else "PRESERVED_LAST_KNOWN_GOOD"
        ),
        "seed_count": len(rows),
        "query_error_count": len(errors),
        "diagnostics": diagnostics,
        "snapshot_refreshed": refreshed,
        "snapshot_path": str(path) if path else None,
        "database_write_performed": False,
        "outbound_sent": False,
        "execution_authority": "none",
    }


def run_local_buyer_recovery(
    repo_root: str | Path,
    *,
    max_domains: int = 20,
    max_probes: int = 12,
    require_containment: bool = True,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    guard_path = root / "runtime/control/supabase_egress_guard.json"

    if require_containment and not supabase_egress_contained(guard_path):
        payload = {
            "schema_version": "empire.buyer-local-recovery.v1",
            "observed_at": _utc_now(),
            "ok": True,
            "state": "IDLE_GUARD_HEALTHY",
            "contained": False,
            "seed_count": 0,
            "candidate_count": 0,
            "database_write_performed": False,
            "outbound_sent": False,
            "execution_authority": "none",
        }
        _atomic_json(root / RECOVERY_HEARTBEAT, payload)
        return payload

    seeds = load_local_recovery_seeds(root)
    if not seeds:
        payload = {
            "schema_version": "empire.buyer-local-recovery.v1",
            "observed_at": _utc_now(),
            "ok": False,
            "state": "CONTAINED_NO_RECOVERY_SEEDS",
            "contained": True,
            "seed_count": 0,
            "candidate_count": 0,
            "database_write_performed": False,
            "outbound_sent": False,
            "execution_authority": "none",
        }
        _atomic_json(root / RECOVERY_HEARTBEAT, payload)
        return payload

    scout = refresh_buyer_scout(
        root,
        max_queries=1,
        results_per_query=1,
        max_domains=max_domains,
        max_probes=max_probes,
        canonical_seed_records=seeds,
        search_enabled=False,
    )

    if scout.get("database_write_performed") is not False:
        raise RuntimeError("local recovery attempted database write")
    if scout.get("outbound_sent") is not False:
        raise RuntimeError("local recovery attempted outbound")
    if scout.get("execution_authority") != "none":
        raise RuntimeError("local recovery expanded execution authority")

    payload = {
        "schema_version": "empire.buyer-local-recovery.v1",
        "observed_at": _utc_now(),
        "ok": True,
        "state": "LOCAL_RECOVERY_EXECUTED",
        "contained": True,
        "seed_count": len(seeds),
        "search_enabled": scout.get("search_enabled"),
        "opportunity_seed_domain_count": int(
            scout.get("opportunity_seed_domain_count") or 0
        ),
        "probed_domain_count": int(
            scout.get("probed_domain_count") or 0
        ),
        "candidate_count": int(
            scout.get("candidate_count") or 0
        ),
        "probe_failure_counts": dict(
            scout.get("probe_failure_counts") or {}
        ),
        "database_write_performed": False,
        "outbound_sent": False,
        "execution_authority": "none",
    }
    _atomic_json(root / RECOVERY_HEARTBEAT, payload)
    return payload
