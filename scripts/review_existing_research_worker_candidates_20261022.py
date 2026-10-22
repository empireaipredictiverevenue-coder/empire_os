#!/usr/bin/env python3
"""Read-only Research-role systemd inventory; NEVER register a new agent.

Research may exist as source, departmental actions or legacy containers.
Only a PINNED service + process + department/role + owner-authorised key
can become an independently authenticated managed Research principal.
"""
from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from empire_os.agent_runtime_identity_evidence import MANAGED_WORKERS
from empire_os.departments import default_departments


@dataclass(frozen=True)
class ExistingCandidate:
    unit: str
    evidence_lane: str
    blocker: str


CANDIDATES = (
    ExistingCandidate(
        "empire-department-cycle.service", "strategy_executive",
        "role_is_executive_not_research",
    ),
    ExistingCandidate(
        "empire-buyer-acquisition-scout.service", "buyer_research_pipeline",
        "multi_execstart_discovery_persistence_not_pinned_research",
    ),
    ExistingCandidate(
        "empire-linkedin-revenue-department.service",
        "linked_market_research", "specialised_evidence_utility_not_pinned_research",
    ),
    ExistingCandidate(
        "empire-market-gps.service", "market_signal_pipeline",
        "market_reader_not_pinned_research",
    ),
    ExistingCandidate(
        "empire-predictive-intelligence.service", "predictive_snapshot_builder",
        "intelligence_materializer_not_pinned_research",
    ),
)


def fixed_systemd_read(unit: str) -> dict[str, str]:
    if unit not in {candidate.unit for candidate in CANDIDATES}:
        raise ValueError("only_existing_research_candidate_units")
    try:
        completed = subprocess.run(
            ["systemctl", "show", unit, "-p", "Id", "-p", "LoadState",
             "-p", "Type", "-p", "User", "-p", "Group",
             "-p", "ActiveState", "-p", "SubState", "--no-pager"],
            capture_output=True, text=True, timeout=3, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {}
    if completed.returncode:
        return {}
    result = {}
    for line in completed.stdout[:4096].splitlines():
        k, eq, v = line.partition("=")
        if eq and k in {"Id", "LoadState", "Type", "User", "Group",
                        "ActiveState", "SubState"} and k not in result:
            result[k] = v.strip()
    return result


def review(
    *, reader: Callable[[str], Mapping[str, str]] = fixed_systemd_read,
) -> dict[str, Any]:
    market_roles = {
        d.key: tuple(d.agent_roles)
        for d in default_departments()
    }
    if "research" not in market_roles.get("market_intelligence", ()):
        raise ValueError("canonical_market_research_role_not_defined")
    enrolled = [
        worker for worker in MANAGED_WORKERS
        if worker.department == "market_intelligence"
        and worker.role in {"research", "deep_research"}
    ]
    candidates = []
    for candidate in CANDIDATES:
        state = dict(reader(candidate.unit))
        loaded = state.get("LoadState") == "loaded" and state.get("Id") == candidate.unit
        candidates.append({
            "unit": candidate.unit,
            "evidence_lane": candidate.evidence_lane,
            "service_loaded": loaded,
            "service_active": state.get("ActiveState") == "active" if loaded else False,
            "managed_research_role_approved": False,
            "blocker": candidate.blocker,
            "agent_enrolled": False,
            "execution_authority": "none",
        })
    # Registry presence is NOT kernel process proof or a public-key grant.
    return {
        "schema_version": "empire.agents.research_managed_worker_readiness.v1",
        "status": (
            "HOLD_RESEARCH_MANAGED_ROLE_REQUIRES_RUNTIME_ATTESTATION"
            if enrolled else "HOLD_NO_VERIFIED_RESEARCH_MANAGED_IDENTITY"
        ),
        "canonical_research_role_defined": True,
        "existing_research_role_process_identity_proven": False,
        "research_managed_worker_candidates_enrolled_in_source": len(enrolled),
        "production_trusted_research_registration": False,
        "production_trusted_signing_enabled": False,
        "live_research_a2a_reply_verified": False,
        "existing_service_candidates": candidates,
        "source_only_legacy_research_agent_is_runtime_attestation": False,
        "production_agent_permissions_changed": False,
        "live_queue_modified": False,
        "execution_authority": "none",
    }


def main() -> int:
    if sys.argv[1:] != ["--review-read-only"]:
        print("EXACT_READ_ONLY_REVIEW_FLAG_REQUIRED")
        return 2
    print(json.dumps(review(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
