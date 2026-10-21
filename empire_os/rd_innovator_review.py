"""Existing Innovator -> canonical R&D intake, with Strategy Supervisor oversight.

Pure, read-only research review. No legacy Innovator loop, supervisor restart
routine, queue dispatch, live model, network, payment or customer action is run.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from empire_os.agents.innovator_agent import PROPOSALS as LEGACY_INNOVATOR_PROPOSALS
from empire_os.departments import default_departments

SEED_FILE = Path("docs/NATIONAL_STORM_HUB_INNOVATION_SEED_20261021.json")
LEGACY_SOURCE = "empire_os/agents/innovator_agent.py"
SCHEMA = "empire.rd_innovator_intake.v1"


def _clean(value: Any, limit: int = 500) -> str:
    return " ".join(value.split())[:limit] if isinstance(value, str) else ""


def _key(name: str) -> str:
    return hashlib.sha256(name.casefold().encode("utf-8")).hexdigest()[:20]


def _candidate(
    name: str,
    *,
    origin: str,
    problem: str = "",
    hypothesis: str = "",
    evidence_refs: tuple[str, ...] = (),
    reuse_components: tuple[str, ...] = (),
    experiment: str = "",
) -> dict[str, Any]:
    return {
        "proposal_id": "rd_idea_" + _key(name),
        "name": name,
        "origin": origin,
        "department": "rd_innovation",
        "lab": "product_innovation",
        "lifecycle_stage": "IDEA",
        "review_status": "HYPOTHESIS_AND_EVIDENCE_REQUIRED",
        "problem": problem,
        "hypothesis": hypothesis,
        "experiment": experiment,
        "evidence_refs": list(evidence_refs),
        "reuse_components": list(reuse_components),
        "financial_forecast": None,
        "technical_readiness_verified": False,
        "buyer_demand_verified": False,
        "customer_actions_authorized": False,
        "ship_action": None,
        "execution_authority": "none",
    }


def review_innovator_rd_intake(repo_root: str | Path) -> dict[str, Any]:
    """Bridge old static proposals and founder-owned research seeds to R&D review.

    This intentionally never calls legacy cycle() because it would log to
    /root/feedback and classify optimistic hardcoded scores as 'ship'.
    Historical projections are deliberately excluded from the returned data.
    """
    root = Path(repo_root)
    departments = {item.key: item for item in default_departments()}
    rd_roles = departments["rd_innovation"].agent_roles
    strategy_roles = departments["strategy"].agent_roles
    linked = "innovator" in rd_roles and "supervisor" in strategy_roles

    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    seed_state = "ABSENT"
    try:
        data = json.loads((root / SEED_FILE).read_text(encoding="utf-8"))
    except FileNotFoundError:
        data = {}
    except (OSError, json.JSONDecodeError):
        data = {}
        seed_state = "INVALID_SEED"
    if isinstance(data, dict) and isinstance(data.get("proposals"), list):
        seed_state = "READ"
        for item in data["proposals"][:25]:
            if not isinstance(item, Mapping):
                continue
            name = _clean(item.get("name"), 100)
            if not name or name.casefold() in seen:
                continue
            seen.add(name.casefold())
            paths = tuple(_clean(p, 180) for p in item.get("reuse_components", [])
                          if isinstance(p, str)) if isinstance(item.get("reuse_components"), list) else ()
            candidates.append(_candidate(
                name, origin="founder_research_seed",
                problem=_clean(item.get("problem")),
                hypothesis=_clean(item.get("hypothesis")),
                experiment=_clean(item.get("experiment")),
                evidence_refs=(str(SEED_FILE),),
                reuse_components=paths[:16],
            ))

    for proposal in LEGACY_INNOVATOR_PROPOSALS:
        name = _clean(proposal.get("name"), 100)
        if not name or name.casefold() in seen:
            continue
        seen.add(name.casefold())
        candidates.append(_candidate(
            name, origin="legacy_static_idea",
            evidence_refs=(LEGACY_SOURCE,),
        ))

    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "status": "REVIEW_READY" if linked and seed_state == "READ"
                  else "REVIEW_WITH_GAPS",
        "seed_state": seed_state,
        "rd_owner": "rd_innovation",
        "supervisor_owner": "strategy",
        "innovator_role_registered_in_rd": "innovator" in rd_roles,
        "supervisor_role_registered_in_strategy": "supervisor" in strategy_roles,
        "supervisor_action": "read_only_review",
        "legacy_seed_count": sum(x["origin"] == "legacy_static_idea" for x in candidates),
        "founder_seed_count": sum(x["origin"] == "founder_research_seed" for x in candidates),
        "candidate_count": len(candidates),
        "candidates": candidates,
        "automatic_proposal_ship_allowed": False,
        "queue_mutated": False,
        "model_invoked": False,
        "customer_actions_authorized": False,
        "payment_authority": "none",
        "execution_authority": "none",
    }
