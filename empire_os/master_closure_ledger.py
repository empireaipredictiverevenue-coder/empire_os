"""Read-only master closure ledger for EmpireOS loose ends."""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Mapping

EXPECTED_MIGRATION_018_SHA256 = (
    "e7edcfe1d0f94c3898437e68db0714557370b7b86f9b21ee76cc04be60bc3c21"
)

CATEGORIES = {
    "INTERNAL_REVERSIBLE",
    "FOUNDER_GATE",
    "EXTERNAL_SEND_GATE",
    "CANDIDATE_PROMOTION",
    "CLEANUP",
    "VERIFIED_COMPLETE",
}


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _item(
    key: str,
    category: str,
    state: str,
    *,
    blocker: str | None,
    next_action: str | None,
    founder_approval_required: bool = False,
    evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if category not in CATEGORIES:
        raise ValueError("invalid closure category")
    return {
        "key": key,
        "category": category,
        "state": state,
        "blocker": blocker,
        "next_action": next_action,
        "founder_approval_required": founder_approval_required,
        "evidence": dict(evidence or {}),
        "execution_authority": "none",
    }


def classify_closure(
    *,
    revenue_pulse: Mapping[str, Any] | None,
    sell_now: Mapping[str, Any] | None,
    buyer_acquisition: Mapping[str, Any] | None,
    commercial_exchange: Mapping[str, Any] | None,
    owned_campaigns: Mapping[str, Any] | None,
    a2a_authentication_status: str | None,
    production_dirty_total: int | None,
    production_failed_units: int | None,
    getlead_candidate_count: int | None,
    migration_018_sha256: str | None,
    migration_025_exists: bool | None,
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []

    blocker = (
        str(revenue_pulse.get("highest_priority_blocker") or "")
        if revenue_pulse else ""
    )
    revenue_truth = revenue_pulse.get("recognized_revenue_truth") if revenue_pulse else None
    cents = (
        revenue_truth.get("recognized_revenue_cents")
        if isinstance(revenue_truth, Mapping)
        else None
    )
    if blocker == "buyer_conversation":
        items.append(_item(
            "buyer_conversation",
            "EXTERNAL_SEND_GATE",
            "BLOCKED",
            blocker="buyer_conversation",
            next_action="Advance genuine buyer replies with founder-approved person-bound sends",
            founder_approval_required=True,
            evidence={"recognized_revenue_cents": cents},
        ))
    elif revenue_pulse is None:
        items.append(_item(
            "buyer_conversation",
            "INTERNAL_REVERSIBLE",
            "UNKNOWN",
            blocker="revenue_pulse_unavailable",
            next_action="Restore read model evidence",
        ))
    else:
        items.append(_item(
            "buyer_conversation",
            "VERIFIED_COMPLETE",
            "CLEAR",
            blocker=None,
            next_action=None,
            evidence={"recognized_revenue_cents": cents},
        ))

    if sell_now is None:
        items.append(_item(
            "sell_now",
            "INTERNAL_REVERSIBLE",
            "UNKNOWN",
            blocker="sell_now_snapshot_unavailable",
            next_action="Restore Sell Now read model",
        ))
    else:
        ready = int(sell_now.get("ready_product_count") or 0)
        routes = int(sell_now.get("matched_route_count") or 0)
        sell_count = int(sell_now.get("sell_now_count") or 0)
        review = int(sell_now.get("needs_review_count") or 0)
        items.append(_item(
            "sell_now",
            "VERIFIED_COMPLETE" if sell_count > 0 else "INTERNAL_REVERSIBLE",
            "READY" if sell_count > 0 else "BLOCKED",
            blocker=None if sell_count > 0 else "opportunity_factory_readiness",
            next_action=None if sell_count > 0 else (
                "Bind genuine demand, normalized economics, distribution strength, "
                "and fulfilment evidence to factory candidates"
            ),
            evidence={
                "ready_product_count": ready,
                "matched_route_count": routes,
                "sell_now_count": sell_count,
                "needs_review_count": review,
            },
        ))

    if owned_campaigns is None:
        items.append(_item(
            "owned_free_traffic",
            "INTERNAL_REVERSIBLE",
            "UNKNOWN",
            blocker="owned_campaign_snapshot_unavailable",
            next_action="Restore preflight snapshot",
        ))
    else:
        db_gate = bool(owned_campaigns.get("founder_db_approval_required"))
        published = bool(owned_campaigns.get("publication_performed"))
        items.append(_item(
            "owned_free_traffic",
            "VERIFIED_COMPLETE" if published else ("FOUNDER_GATE" if db_gate else "INTERNAL_REVERSIBLE"),
            "LIVE" if published else ("GATED" if db_gate else "BLOCKED"),
            blocker=None if published else (
                "migration_025_owned_campaign_intake" if db_gate else "owned_campaign_preflight"
            ),
            next_action=None if published else (
                "Founder approval for migration 025, then live schema/role verification and release"
                if db_gate else "Close remaining preflight blockers"
            ),
            founder_approval_required=(db_gate and not published),
            evidence={
                "campaigns_requested": owned_campaigns.get("campaigns_requested"),
                "campaigns_preflight_passed": owned_campaigns.get("campaigns_preflight_passed"),
                "campaigns_blocked": owned_campaigns.get("campaigns_blocked"),
                "publication_performed": published,
            },
        ))

    a2a_active = a2a_authentication_status == "activated"
    items.append(_item(
        "a2a_commerce",
        "VERIFIED_COMPLETE" if a2a_active else "INTERNAL_REVERSIBLE",
        "LIVE" if a2a_active else "BLOCKED",
        blocker=None if a2a_active else "commercial_authentication_not_activated",
        next_action=None if a2a_active else "Complete governed authenticated intent-to-review activation",
        evidence={"authentication_status": a2a_authentication_status},
    ))

    if buyer_acquisition is not None:
        sent = bool(buyer_acquisition.get("outbound_sent"))
        targets = int(buyer_acquisition.get("icp_priority_target_count") or 0)
        if targets > 0 and not sent:
            items.append(_item(
                "buyer_acquisition_send",
                "EXTERNAL_SEND_GATE",
                "GATED",
                blocker="governed_send_not_executed",
                next_action="Founder approve person-bound sends for genuine ready targets",
                founder_approval_required=True,
                evidence={"icp_priority_target_count": targets, "outbound_sent": sent},
            ))

    if commercial_exchange is not None:
        inventory = int(commercial_exchange.get("inventory_count") or 0)
        seats = int(commercial_exchange.get("buyer_seat_count") or 0)
        candidates = int(commercial_exchange.get("allocation_candidate_count") or 0)
        allocated = int(commercial_exchange.get("allocated_count") or 0)
        if inventory > 0 and seats > 0 and candidates == 0 and allocated == 0:
            items.append(_item(
                "commercial_exchange",
                "INTERNAL_REVERSIBLE",
                "BLOCKED",
                blocker="allocation_candidate_generation",
                next_action="Generate only evidence-backed allocation candidates",
                evidence={
                    "inventory_count": inventory,
                    "buyer_seat_count": seats,
                    "allocation_candidate_count": candidates,
                    "allocated_count": allocated,
                },
            ))

    if production_failed_units == 0:
        items.append(_item(
            "systemd_failed_units",
            "VERIFIED_COMPLETE",
            "CLEAR",
            blocker=None,
            next_action=None,
            evidence={"failed_units": 0},
        ))
    elif production_failed_units is not None:
        items.append(_item(
            "systemd_failed_units",
            "INTERNAL_REVERSIBLE",
            "BLOCKED",
            blocker="failed_systemd_units",
            next_action="Diagnose failed units using root-cause recovery sequence",
            evidence={"failed_units": production_failed_units},
        ))

    if production_dirty_total:
        items.append(_item(
            "production_worktree",
            "CLEANUP",
            "BLOCKED",
            blocker="dirty_production_worktree",
            next_action="Classify and safely reconcile tracked/untracked work; no reset/clean",
            evidence={"dirty_paths": production_dirty_total},
        ))
    elif production_dirty_total == 0:
        items.append(_item(
            "production_worktree",
            "VERIFIED_COMPLETE",
            "CLEAR",
            blocker=None,
            next_action=None,
            evidence={"dirty_paths": 0},
        ))

    if getlead_candidate_count:
        items.append(_item(
            "getlead_blitz_candidates",
            "CANDIDATE_PROMOTION",
            "GATED",
            blocker="independent_promotion_not_complete",
            next_action="Verify promotion order, merge only independently verified slices",
            evidence={"candidate_branch_count": getlead_candidate_count},
        ))

    migration_018_ok = migration_018_sha256 == EXPECTED_MIGRATION_018_SHA256
    items.append(_item(
        "migration_018_protection",
        "VERIFIED_COMPLETE" if migration_018_ok else "FOUNDER_GATE",
        "CLEAR" if migration_018_ok else "BLOCKED",
        blocker=None if migration_018_ok else "migration_018_checksum_mismatch",
        next_action=None if migration_018_ok else "Stop and reconcile protected migration before any DB work",
        founder_approval_required=not migration_018_ok,
        evidence={
            "expected_sha256": EXPECTED_MIGRATION_018_SHA256,
            "observed_sha256": migration_018_sha256,
        },
    ))

    if migration_025_exists is False:
        items.append(_item(
            "migration_025_owned_campaign_intake",
            "INTERNAL_REVERSIBLE",
            "BLOCKED",
            blocker="migration_025_missing",
            next_action="Restore reviewed migration artifact before founder gate",
        ))
    elif migration_025_exists:
        items.append(_item(
            "migration_025_owned_campaign_intake",
            "FOUNDER_GATE",
            "GATED",
            blocker="founder_db_approval_required",
            next_action="Explicit founder approval required before apply",
            founder_approval_required=True,
        ))

    summary = {
        "item_count": len(items),
        "by_category": {
            category: sum(1 for item in items if item["category"] == category)
            for category in sorted(CATEGORIES)
        },
        "founder_gate_count": sum(
            1 for item in items if item["founder_approval_required"]
        ),
        "open_count": sum(
            1 for item in items if item["category"] != "VERIFIED_COMPLETE"
        ),
    }
    return {
        "schema_version": "empire.master-closure-ledger.v1",
        "items": items,
        "summary": summary,
        "external_send": False,
        "database_mutation": False,
        "payment_action": False,
        "revenue_recognition": False,
        "production_deploy": False,
        "execution_authority": "none",
    }


def collect_runtime_closure(root: str | Path = "/srv/empire_os") -> dict[str, Any]:
    root = Path(root)
    runtime = root / "runtime"

    def run(*argv: str) -> str:
        proc = subprocess.run(
            list(argv),
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        return proc.stdout.strip()

    dirty_total = len(
        [line for line in run("git", "status", "--short").splitlines() if line.strip()]
    )
    failed_raw = run(
        "systemctl", "--failed", "--no-legend", "--plain"
    )
    failed_units = len([line for line in failed_raw.splitlines() if line.strip()])
    candidate_refs = run(
        "git", "for-each-ref", "--format=%(refname:short)", "refs/heads/candidate/getlead-blitz*"
    )
    getlead_count = len([line for line in candidate_refs.splitlines() if line.strip()])

    mig018 = root / "migrations/empiredb/018_tenant_context_foundation.sql"
    mig018_sha = (
        hashlib.sha256(mig018.read_bytes()).hexdigest()
        if mig018.exists() else None
    )
    mig025 = root / "migrations/empiredb/025_owned_campaign_intake.sql"

    return classify_closure(
        revenue_pulse=_read_json(runtime / "revenue_pulse/latest.json"),
        sell_now=_read_json(runtime / "predictive_revenue/sell_now/latest.json"),
        buyer_acquisition=_read_json(runtime / "buyer_acquisition/latest.json"),
        commercial_exchange=_read_json(runtime / "commercial_exchange/latest.json"),
        owned_campaigns=_read_json(runtime / "astra/owned_campaign_activation_v2_prepared/report.json"),
        a2a_authentication_status="not_activated",
        production_dirty_total=dirty_total,
        production_failed_units=failed_units,
        getlead_candidate_count=getlead_count,
        migration_018_sha256=mig018_sha,
        migration_025_exists=mig025.exists(),
    )
