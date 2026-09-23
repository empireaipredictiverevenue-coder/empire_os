"""Read-only Founder Source Intelligence demo API."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Query

from empire_os.geo_registry import acquisition_markets
from empire_os.source_intelligence import source_plan


def _latest_source_run(
    log_path: Path,
    *,
    source: str,
    niche: str,
) -> dict[str, Any]:
    try:
        lines = log_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return {
            "available": False,
            "source": source,
            "niche": niche,
            "candidates": [],
            "candidate_count": 0,
        }

    rows: list[dict[str, Any]] = []
    for raw in lines[-8000:]:
        try:
            row = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            continue
        if isinstance(row, dict):
            rows.append(row)

    start_index = None
    for index in range(len(rows) - 1, -1, -1):
        row = rows[index]
        if (
            row.get("msg") == "crawler_run_start"
            and str(row.get("source") or "") == source
        ):
            start_index = index
            break

    if start_index is None:
        return {
            "available": False,
            "source": source,
            "niche": niche,
            "candidates": [],
            "candidate_count": 0,
        }

    start = rows[start_index]
    candidates: list[dict[str, Any]] = []
    done: dict[str, Any] | None = None

    for row in rows[start_index + 1 :]:
        msg = str(row.get("msg") or "")
        if msg == "crawler_run_start":
            break
        if msg in {"candidate", "prospect_acquired", "prospect_matched"}:
            if str(row.get("source") or "") != source:
                continue
            if str(row.get("niche") or "") != niche:
                continue
            candidates.append(
                {
                    "name": row.get("name"),
                    "source": row.get("source"),
                    "niche": row.get("niche"),
                    "metro": row.get("metro"),
                    "quality_confidence": row.get("quality_confidence"),
                    "entity_kind": row.get("entity_kind"),
                    "decision": row.get("decision"),
                    "prospect_id": row.get("prospect_id"),
                    "country_code": row.get("country_code"),
                    "language_code": row.get("language_code"),
                    "timezone": row.get("timezone"),
                    "observed_at": row.get("ts"),
                }
            )
        if msg == "crawler_run_done":
            done = row
            break

    return {
        "available": True,
        "source": source,
        "niche": niche,
        "started_at": start.get("ts"),
        "dry_run": start.get("dry_run") is True,
        "canonical_store": start.get("canonical_store"),
        "max_candidates": start.get("max_candidates"),
        "candidate_count": len(candidates),
        "candidates": candidates,
        "run_result": {
            "candidates": done.get("candidates") if done else None,
            "accepted": done.get("accepted") if done else None,
            "errors": done.get("errors") if done else None,
        },
        "actual_revenue": False,
        "execution_authority": "none",
    }


def create_founder_source_intelligence_router(
    repo_root: Path | None = None,
) -> APIRouter:
    root = repo_root or Path(__file__).resolve().parents[1]
    router = APIRouter(
        prefix="/v1/founder-source-intelligence",
        tags=["founder-source-intelligence"],
    )

    @router.get("/solar")
    def solar(country: str = Query(default="GB", min_length=2, max_length=2)):
        code = country.upper()
        plan = source_plan(code, "solar")
        markets = acquisition_markets(countries=[code])
        proof = _latest_source_run(
            root / "runtime" / "feedback" / "crawler_runs.jsonl",
            source="recc_solar" if code == "GB" else str(plan.get("selected_source") or ""),
            niche="solar",
        )
        return {
            "schema_version": "empire.founder_source_intelligence.v1",
            "mode": "OBSERVE",
            "country_code": code,
            "niche": "solar",
            "market_anchor_count": len(markets),
            "source_plan": plan,
            "latest_proof": proof,
            "truth": {
                "verified_source_proof": proof.get("candidate_count", 0) > 0,
                "canonical_write_observed": (
                    proof.get("dry_run") is False
                    and (proof.get("run_result") or {}).get("accepted", 0) > 0
                ),
                "commercial_outcome_observed": False,
                "recognized_revenue_observed": False,
            },
            "execution_authority": "none",
            "actual_revenue": False,
        }

    return router
