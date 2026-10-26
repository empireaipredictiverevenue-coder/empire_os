#!/usr/bin/env python3
"""One read-only commercial decision review across EXISTING source owners.

Reuses pure owner modules. This does not create another agent, scheduler,
revenue projection, buyer list, model learner or activation workflow.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
from datetime import datetime, timezone
import json
from pathlib import Path

from empire_os.commercial_adaptive_intelligence_control import (
    review_adaptive_commercial_intelligence, POLICY_LOOKUP, REQUIRED_PROOF,
)
from empire_os.commercial_sales_director_adaptive_review import (
    adaptive_original_proof_review,
)
from empire_os.commercial_shadow_offer_reconstruction import (
    review_shadow_offer_reconstruction,
)
from empire_os.commercial_distribution_shadow_refresh import (
    shadow_distribution_refresh_review,
)
from empire_os.revenue_distribution import SOURCES
from empire_os.revenue_distribution_review import REVIEW_SOURCES
from scripts.review_sales_director_original_proof_20261020 import (
    build_original_proof_runtime,
)

MAX_FILE_SIZE = 3_000_000
MAX_PREVIOUS_SIZE = 80_000


def _bounded_json(path: Path, *, max_bytes: int = MAX_FILE_SIZE):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > max_bytes:
        raise ValueError("source is not a bounded original JSON file")
    return json.loads(path.read_text(encoding="utf-8"))


def _previous(filename: str | None):
    if filename is None:
        return None
    return _bounded_json(Path(filename), max_bytes=MAX_PREVIOUS_SIZE)


def build_adaptive_commercial_runtime(
    root: Path, *,
    now: datetime,
    previous_sales: dict | None,
    previous_control: dict | None,
    conversation_proof: dict | None = None,
    owner_source_receipts: dict | None = None,
    include_sales_review: bool = False,
):
    """Pure read-only owner composition, no database, mailbox API or writes."""
    original_sales = build_original_proof_runtime(
        root, now=now, conversation_proof=conversation_proof,
    )
    sales = adaptive_original_proof_review(
        current=original_sales, previous=previous_sales,
        source_receipts=owner_source_receipts, now=now,
    )
    catalog = _bounded_json(root / "runtime/commercial_catalog/latest.json")
    distribution_file = _bounded_json(root / "runtime/revenue_distribution/latest.json")
    previous_book = _bounded_json(
        root / "runtime/predictive_revenue/commercial_offer_book/latest.json"
    )
    owner_reviews = {}
    for name, rel in REVIEW_SOURCES.items():
        try:
            owner_reviews[name] = _bounded_json(root / rel)
        except (OSError, ValueError, json.JSONDecodeError):
            owner_reviews[name] = None
    offers = review_shadow_offer_reconstruction(
        catalog=catalog, distribution=distribution_file,
        review_sources=owner_reviews, previous_offer_book=previous_book,
        now=now,
    )
    original_distribution_sources = {}
    for name, rel in SOURCES.items():
        try:
            original_distribution_sources[name] = _bounded_json(root / rel)
        except (OSError, ValueError, json.JSONDecodeError):
            original_distribution_sources[name] = None
    distribution = shadow_distribution_refresh_review(
        source_snapshots=original_distribution_sources,
        previous_distribution=distribution_file, now=now,
    )
    report = review_adaptive_commercial_intelligence(
        sales=sales, offers=offers, distribution=distribution,
        previous=previous_control, now=now,
    )
    return {"control": report, "sales": sales} if include_sales_review else report


# These are operating-owner handoffs, not an additional research agent.
# Search Intelligence and SEO are outside the authority of this workstream.
EXTERNALLY_HELD_OWNERS = frozenset({
    "agent_web_search_owner", "competitor_search_intelligence_owner",
})
# A payoff forecast cannot be derived from a large unqualified cohort.
BUSINESS_PRIORITY = {
    "BUYER_CAPACITY_AND_TERMS": 0,
    "COMMERCIAL_SOURCE_PROVENANCE": 1,
    "CONTACT_SUPPRESSION": 2,
    "CATALOG_DELIVERABILITY": 3,
    "ORIGINAL_REPLY_AUTHENTICATION": 4,
    "CONTACT_AND_PROSPECT_IDENTITY": 5,
    "SEARCH_SOURCE_FRESHNESS": 6,
    "COMPETITOR_SOURCE_FRESHNESS": 7,
}


def founder_owner_evidence_handoff(control: dict) -> dict:
    """Render one non-executable, idempotent founder decision packet.

    Inputs and owner lanes come only from the existing adaptive commercial
    review. Never join its source cohorts or calculate speculative sales.
    """
    if not isinstance(control, dict):
        raise ValueError("original adaptive owner packet required")
    for key, value in (
        ("schema_version", "empire.commercial.adaptive_intelligence_control.v1"),
        ("mode", "OBSERVE"), ("execution_authority", "none"),
        ("status", "COMMERCIAL_DEPENDENCY_EVIDENCE_HOLD"),
        ("outbound_authorized", False), ("database_writes", False),
        ("payment_execution", False), ("agent_tasks_created", False),
        ("owner_authority_changed", False), ("model_training", False),
    ):
        if control.get(key) != value or type(control.get(key)) != type(value):
            raise ValueError("original adaptive decision authority mismatch: " + key)
    evidence=control.get("decision_signature_data")
    if not isinstance(evidence, dict):
        raise ValueError("missing original decision proof")
    signature=sha256(json.dumps(evidence,sort_keys=True,separators=(",", ":"),
        allow_nan=False,ensure_ascii=True).encode()).hexdigest()
    if control.get("decision_signature") != signature:
        raise ValueError("original adaptive decision signature mismatch")
    gates=control.get("active_dependency_gates")
    if not isinstance(gates,list) or len(gates)>len(POLICY_LOOKUP):
        raise ValueError("original active commercial gates invalid")
    by_name={}
    for row in gates:
        if not isinstance(row,dict):
            raise ValueError("untrusted commercial dependency gate")
        name=row.get("gate")
        if name in by_name or name not in POLICY_LOOKUP:
            raise ValueError("duplicate or unknown original dependency gate")
        owner,instruction,_previous_group,category,source_priority=POLICY_LOOKUP[name]
        if (row.get("existing_owner_lane")!=owner
            or row.get("priority_rank")!=source_priority
            or row.get("category")!=category
            or row.get("review_instruction_not_dispatched")!=instruction
            or row.get("task_created") is not False
            or row.get("source_change_does_not_grant_permission") is not True
            or row.get("parallel_owner_review_possible") not in (True,False)
            or not isinstance(row.get("upstream_gates_blocking_work"),list)
            or any(g not in POLICY_LOOKUP for g in row["upstream_gates_blocking_work"])
            or not isinstance(row.get("original_proof_requirements_not_verified"),list)
            or row["original_proof_requirements_not_verified"]!=list(REQUIRED_PROOF[name])):
            raise ValueError("original owner assignment or evidence requirements drift")
        by_name[name]=row
    if sorted(by_name)!=sorted(evidence.get("gates",[])):
        raise ValueError("original dependency signature and active rows disagree")
    unchanged=control.get("transition")=="UNCHANGED_COMMERCIAL_HOLD"
    if type(control.get("operator_attention_due")) is not bool:
        raise ValueError("missing original attention state")
    if unchanged and control["operator_attention_due"] is not False:
        raise ValueError("unchanged review cannot claim a new attention request")
    actions=[]
    for gate in sorted(by_name,key=lambda name:(BUSINESS_PRIORITY[name],name)):
        row=by_name[gate]
        blocked=row["upstream_gates_blocking_work"]
        externally_owned=row["existing_owner_lane"] in EXTERNALLY_HELD_OWNERS
        if externally_owned:
            decision="EXTERNAL_OWNER_HOLD_NO_ACTION_FROM_THIS_WORKSTREAM"
        elif blocked:
            decision="WAIT_ON_ORIGINAL_UPSTREAM_PROOF_NO_DUPLICATE_TASK"
        elif unchanged:
            decision="NO_NEW_EVIDENCE_NO_REPEAT_OWNER_REQUEST"
        elif row["parallel_owner_review_possible"]:
            decision="ELIGIBLE_FOR_ORIGINAL_OWNER_EVIDENCE_REVIEW_ONLY"
        else:
            decision="REVIEW_IN_ORIGINAL_OWNER_LANE_WITHOUT_DISPATCH"
        actions.append({
            "gate":gate,
            "existing_owner_lane":row["existing_owner_lane"],
            "decision":decision,
            "upstream_gates":list(blocked),
            "proof_requirements_not_verified":list(row["original_proof_requirements_not_verified"]),
            "owner_review_instruction_not_dispatched":row["review_instruction_not_dispatched"],
            "count_is_not_buying_intent":True,
            "new_task_created":False,
        })
    fingerprint=sha256(json.dumps({"original_signature":signature,
        "decisions":[(r["gate"],r["decision"]) for r in actions]},
        sort_keys=True,separators=(",", ":")).encode()).hexdigest()
    return {
        "schema_version":"empire.commercial.adaptive_founder_handoff.v1",
        "status":"ROOT_EVIDENCE_OWNER_HANDOFF_ONLY",
        "original_decision_signature":signature,
        "stable_handoff_signature":fingerprint,
        "original_review_transition":control["transition"],
        "no_repeat_if_unchanged":True,
        "active_gate_count":len(actions),
        "primary_commercial_gate":"BUYER_CAPACITY_AND_TERMS" if "BUYER_CAPACITY_AND_TERMS" in by_name else None,
        "original_owner_handoffs":actions,
        "historical_cases_not_current_buyer_replies":control.get("historical_conversations_not_verified_replies"),
        "buyer_capacity_records_not_verified_purchasers":control.get("buyer_capacity_records_seen_not_purchasers"),
        "verified_buyers":control.get("independently_authenticated_buyers"),
        "verified_revenue_cents":control.get("accepted_verified_revenue_cents"),
        "original_execution_authority_unchanged":True,
        "external_seo_search_owner_not_modified":True,
        "cross_cohort_join_performed":False,
        "site_modified":False,"outbound_sent":False,
        "database_writes":False,"agent_tasks_created":False,
        "payment_execution":False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Manual read-only commercial adaptive dependency graph"
    )
    parser.add_argument("--read-only", action="store_true", required=True)
    parser.add_argument("--founder-handoff", action="store_true",
                        help="Return a concise non-executable evidence/owner decision packet")
    parser.add_argument("--repo-root", default="/srv/empire_os")
    parser.add_argument("--previous-sales-review-file")
    parser.add_argument("--previous-commercial-review-file")
    args = parser.parse_args()
    root = Path(args.repo_root).resolve(strict=True)
    report = build_adaptive_commercial_runtime(
        root, now=datetime.now(timezone.utc),
        previous_sales=_previous(args.previous_sales_review_file),
        previous_control=_previous(args.previous_commercial_review_file),
    )
    print(json.dumps(founder_owner_evidence_handoff(report) if args.founder_handoff else report,
                     sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
