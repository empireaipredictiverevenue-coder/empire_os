from __future__ import annotations

import importlib
import inspect
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from empire_os.buyer_network_integration import (
    BuyerNetworkIntegration,
)
from empire_os.buyer_network_contact_history_gate import load_context, review


ROOT = Path("/srv/empire_os")

QUEUE = (
    ROOT
    / "runtime"
    / "buyer_network_intelligence"
    / "candidate_queue_latest.json"
)

OUTPUT = (
    ROOT
    / "runtime"
    / "buyer_network_intelligence"
    / "founder_shortlist_latest.json"
)

MARKDOWN = (
    ROOT
    / "runtime"
    / "buyer_network_intelligence"
    / "founder_shortlist_latest.md"
)


EXISTING_LOGIC_MODULES = (
    "empire_os.buyer_capacity_readiness",
    "empire_os.buyer_commercial_terms_intake",
    "empire_os.buyer_supply_review",
    "empire_os.buyer_call_economics",
    "empire_os.conversation_qualification",
    "empire_os.omega_buyer_readiness",
    "empire_os.lead_smart_predictive_revenue_adapter",
    "empire_os.predictive_revenue_jev",
)


def now_iso() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


def atomic_json(
    path: Path,
    payload: dict[str, Any],
) -> None:

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    tmp = path.with_suffix(".tmp")

    tmp.write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            default=str,
        )
        + "\n",
        encoding="utf-8",
    )

    tmp.replace(path)


def load_existing_logic() -> dict[str, Any]:
    result: dict[str, Any] = {}

    for name in EXISTING_LOGIC_MODULES:
        try:
            module = importlib.import_module(
                name
            )

        except Exception as exc:
            result[name] = {
                "loaded": False,
                "error":
                    type(exc).__name__,
                "contracts": [],
            }
            continue

        contracts = []

        for member_name, member in inspect.getmembers(
            module
        ):
            if member_name.startswith("_"):
                continue

            if not inspect.isfunction(member):
                continue

            try:
                signature = str(
                    inspect.signature(
                        member
                    )
                )

            except Exception:
                signature = "(unknown)"

            contracts.append(
                {
                    "name":
                        member_name,
                    "signature":
                        signature,
                }
            )

        result[name] = {
            "loaded": True,
            "contracts":
                contracts[:100],
        }

    return result


def evidence_gaps(
    candidate: dict[str, Any],
) -> list[str]:

    evidence = candidate.get(
        "evidence",
        {},
    )

    required = {
        "publisher_program":
            "verify_publisher_acceptance",

        "active_demand":
            "verify_active_buyer_demand",

        "integration":
            "verify_tracking_or_integration",

        "economics":
            "verify_payout_economics",

        "compliance":
            "verify_compliance_requirements",

        "contactable":
            "verify_contact_or_application_path",
    }

    return [
        gap
        for key, gap in required.items()
        if not evidence.get(key)
    ]


def founder_priority(
    candidate: dict[str, Any],
) -> int:

    score = int(
        candidate.get("score") or 0
    )

    status = candidate.get(
        "status"
    )

    evidence = candidate.get(
        "evidence",
        {},
    )

    if status == "READY_TO_APPROACH":
        score += 20

    elif status == "VERIFY_REQUIREMENTS":
        score += 10

    if evidence.get(
        "publisher_program"
    ):
        score += 5

    if evidence.get(
        "active_demand"
    ):
        score += 5

    if evidence.get(
        "economics"
    ):
        score += 5

    if evidence.get(
        "integration"
    ):
        score += 5

    if evidence.get(
        "compliance"
    ):
        score += 3

    if evidence.get(
        "contactable"
    ):
        score += 2

    if evidence.get(
        "negative_program"
    ):
        score = 0

    return max(
        0,
        min(100, score),
    )


def classify(
    candidate: dict[str, Any],
) -> str:

    status = candidate.get(
        "status"
    )

    evidence = candidate.get(
        "evidence",
        {},
    )

    if (
        status == "READY_TO_APPROACH"
        and evidence.get(
            "publisher_program"
        )
        and evidence.get(
            "active_demand"
        )
    ):
        return "A_FOUNDER_REVIEW"

    if status in (
        "READY_TO_APPROACH",
        "VERIFY_REQUIREMENTS",
    ):
        return "B_VERIFY_REQUIREMENTS"

    return "HOLD"


def qualification(
    candidate: dict[str, Any],
) -> dict[str, Any]:

    evidence = candidate.get(
        "evidence",
        {},
    )

    result = (
        BuyerNetworkIntegration
        .candidate(
            vertical_match=bool(
                candidate.get(
                    "verticals"
                )
            ),

            publisher_program_confidence=(
                0.85
                if evidence.get(
                    "publisher_program"
                )
                else 0.0
            ),

            active_demand_confidence=(
                0.85
                if evidence.get(
                    "active_demand"
                )
                else 0.0
            ),

            inventory_fit_confidence=(
                0.50
                if evidence.get(
                    "active_demand"
                )
                else 0.0
            ),

            integration_confidence=(
                0.80
                if evidence.get(
                    "integration"
                )
                else 0.0
            ),

            economics_confidence=(
                0.80
                if evidence.get(
                    "economics"
                )
                else 0.0
            ),

            compliance_confidence=(
                0.75
                if evidence.get(
                    "compliance"
                )
                else 0.0
            ),

            contactable=bool(
                evidence.get(
                    "contactable"
                )
            ),

            negative_program_confidence=(
                0.95
                if evidence.get(
                    "negative_program"
                )
                else 0.0
            ),

            evidence_count=int(
                evidence.get(
                    "evidence_count"
                )
                or 0
            ),
        )
    )

    return {
        "score":
            result.score,

        "readiness":
            result.readiness,

        "blockers":
            list(
                result.blockers
            ),

        "reasons":
            list(
                result.reasons
            ),
    }


def enrich(
    candidate: dict[str, Any],
) -> dict[str, Any]:

    gaps = evidence_gaps(
        candidate
    )

    priority = founder_priority(
        candidate
    )

    founder_class = classify(
        candidate
    )

    q = qualification(
        candidate
    )

    evidence = candidate.get(
        "evidence",
        {},
    )

    return {
        "domain":
            candidate.get(
                "domain"
            ),

        "founder_class":
            founder_class,

        "founder_priority":
            priority,

        "queue_status":
            candidate.get(
                "status"
            ),

        "qualification":
            q,

        "verticals":
            candidate.get(
                "verticals",
                [],
            ),

        "already_known":
            bool(
                candidate.get(
                    "already_known"
                )
            ),

        "evidence_count":
            evidence.get(
                "evidence_count",
                0,
            ),

        "evidence": {
            key:
                evidence.get(key)
            for key in (
                "publisher_program",
                "active_demand",
                "integration",
                "economics",
                "compliance",
                "contactable",
                "negative_program",
            )
        },

        "evidence_gaps":
            gaps,

        "predictive_revenue": {
            "state":
                (
                    "ECONOMICS_EVIDENCE_PRESENT"
                    if evidence.get(
                        "economics"
                    )
                    else
                    "AWAITING_OBSERVED_ECONOMICS"
                ),

            "forecast_revenue":
                None,

            "reason":
                (
                    "No verified per-unit realised "
                    "revenue is present in discovery "
                    "evidence; no revenue invented."
                ),
        },

        "commercial_authority":
            "FOUNDER_REVIEW_ONLY",

        "outbound_authority":
            False,
    }


def build_markdown(
    payload: dict[str, Any],
) -> str:

    lines = [
        "# Empire AI — Buyer Network Founder Shortlist",
        "",
        f"Generated: {payload['generated_at']}",
        "",
        "Authority: OBSERVE / FOUNDER REVIEW ONLY",
        "",
        (
            f"Shortlisted buyers: "
            f"{payload['shortlist_count']}"
        ),
        "",
    ]

    for index, item in enumerate(
        payload["shortlist"],
        1,
    ):
        lines.extend(
            [
                (
                    f"## {index}. "
                    f"{item['domain']}"
                ),
                "",
                (
                    f"- Class: "
                    f"{item['founder_class']}"
                ),
                (
                    f"- Priority: "
                    f"{item['founder_priority']}"
                ),
                (
                    f"- Queue status: "
                    f"{item['queue_status']}"
                ),
                (
                    f"- Qualification: "
                    f"{item['qualification']['readiness']}"
                ),
                (
                    f"- Verticals: "
                    f"{', '.join(item['verticals']) or 'unknown'}"
                ),
                (
                    f"- Already known: "
                    f"{item['already_known']}"
                ),
                (
                    f"- Contact history: "
                    f"{item.get('outreach_status', 'UNVERIFIED')}"
                ),
                (
                    f"- Contact next action: "
                    f"{item.get('contact_history', {}).get('next_action', 'RECONCILE')}"
                ),
                (
                    f"- Evidence count: "
                    f"{item['evidence_count']}"
                ),
                (
                    "- Missing evidence: "
                    + (
                        ", ".join(
                            item[
                                "evidence_gaps"
                            ]
                        )
                        or "none"
                    )
                ),
                (
                    "- Predictive Revenue: "
                    + item[
                        "predictive_revenue"
                    ]["state"]
                ),
                "",
            ]
        )

    return "\n".join(lines) + "\n"


def main() -> int:

    queue = json.loads(
        QUEUE.read_text()
    )

    existing_logic = (
        load_existing_logic()
    )
    contact_context = load_context()

    # Fail closed on contextual/quarantine evidence and non-business domains.
    # 'already_known' is discovery history, NOT evidence of no prior outreach.
    blocked = {"company.com", "insider.com", "sentry.io"}
    candidates = []
    for candidate in queue.get("candidates", []):
        domain = str(candidate.get("domain") or "").lower()
        if candidate.get("status") not in ("READY_TO_APPROACH", "VERIFY_REQUIREMENTS"):
            continue
        if domain in blocked or domain.endswith(".sentry.io"):
            continue
        lines = candidate.get("evidence", {}).get("lines", [])
        if not isinstance(lines, list) or not lines:
            continue
        # Quarantine and synthetic truth-control observations are not
        # independent confirmation of a live publisher programme.
        if all("runtime/truth_quality_control/" in str(line) for line in lines):
            continue
        item = enrich(candidate)
        contact = review(domain, contact_context)
        item["contact_history"] = contact
        item["outreach_status"] = contact["state"]
        item["outbound_authority"] = False
        candidates.append(item)

    candidates.sort(
        key=lambda item: (
            0
            if item[
                "founder_class"
            ] == "A_FOUNDER_REVIEW"
            else 1,

            -item[
                "founder_priority"
            ],

            item["domain"] or "",
        )
    )

    shortlist = candidates[:25]

    payload = {
        "schema_version":
            "buyer-network-founder-shortlist-v1",

        "generated_at":
            now_iso(),

        "authority":
            "OBSERVE",

        "commercial_authority":
            "FOUNDER_REVIEW_ONLY",

        "source_candidate_count":
            queue.get(
                "candidate_count",
                0,
            ),

        "eligible_candidate_count":
            len(candidates),

        "shortlist_count":
            len(shortlist),

        "contact_history_gate_enabled": True,
        "contact_history_source": contact_context["source"],
        "gmail_snapshot_fresh": contact_context["gmail_snapshot_fresh"],

        "existing_logic_modules":
            existing_logic,

        "shortlist":
            shortlist,

        "governance": {
            "outbound_authority":
                False,

            "db_write_authority":
                False,

            "traffic_activation_authority":
                False,

            "commercial_terms_authority":
                False,

            "funds_authority":
                False,
        },
    }

    atomic_json(
        OUTPUT,
        payload,
    )

    MARKDOWN.write_text(
        build_markdown(
            payload
        ),
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "status": "PASS",

                "source_candidate_count":
                    payload[
                        "source_candidate_count"
                    ],

                "eligible_candidate_count":
                    payload[
                        "eligible_candidate_count"
                    ],

                "shortlist_count":
                    payload[
                        "shortlist_count"
                    ],

                "top_buyers": [
                    {
                        "domain":
                            item["domain"],

                        "class":
                            item[
                                "founder_class"
                            ],

                        "priority":
                            item[
                                "founder_priority"
                            ],

                        "qualification":
                            item[
                                "qualification"
                            ]["readiness"],

                        "gaps":
                            item[
                                "evidence_gaps"
                            ],
                    }

                    for item
                    in shortlist[:15]
                ],

                "json_output":
                    str(OUTPUT),

                "founder_report":
                    str(MARKDOWN),
            },
            indent=2,
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
