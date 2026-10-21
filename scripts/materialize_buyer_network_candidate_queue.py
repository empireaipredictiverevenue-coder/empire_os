from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from empire_os.buyer_network_research_rotation import accepted_domain
from empire_os.buyer_network_contact_history_gate import load_context, review

from empire_os.buyer_network_integration import (
    BuyerNetworkIntegration,
)


ROOT = Path("/srv/empire_os")

DISCOVERY = (
    ROOT
    / "runtime"
    / "buyer_network_intelligence"
    / "discovery_latest.json"
)

OUTPUT = (
    ROOT
    / "runtime"
    / "buyer_network_intelligence"
    / "candidate_queue_latest.json"
)


DOMAIN_RE = re.compile(
    r"(?:https?://)?(?:www\.)?"
    r"([a-z0-9][a-z0-9.-]+\.[a-z]{2,})",
    re.I,
)


PUBLISHER_POSITIVE = (
    "publisher program",
    "publishers",
    "become a publisher",
    "publisher signup",
    "publisher sign up",
    "affiliate program",
    "media partners",
    "traffic partners",
    "lead partners",
)

DEMAND_POSITIVE = (
    "buy leads",
    "lead buyer",
    "lead buyers",
    "pay per call",
    "live transfer",
    "inbound calls",
    "consumer initiated",
    "consumer-initiated",
)

INTEGRATION_POSITIVE = (
    "rtb",
    "ping post",
    "ping-post",
    "api",
    "webhook",
    "tracking platform",
    "call tracking",
)

ECONOMICS_POSITIVE = (
    "payout",
    "revshare",
    "revenue share",
    "cost per call",
    "per qualified call",
    "cpl",
    "cpa",
)

COMPLIANCE_POSITIVE = (
    "tcpa",
    "consent",
    "compliance",
    "trustedform",
    "jornaya",
)

CONTACT_POSITIVE = (
    "contact",
    "apply",
    "sign up",
    "signup",
    "get started",
    "join",
)

NEGATIVE = (
    "not accepting publishers",
    "publisher program closed",
    "not accepting affiliates",
    "not accepting traffic",
    "program paused",
)


def now_iso() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


def atomic_write(
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


def normalize_domain(value: str) -> str | None:

    match = DOMAIN_RE.search(
        value or ""
    )

    if not match:
        return None

    domain = (
        match.group(1)
        .lower()
        .rstrip(".")
    )

    if domain.startswith("www."):
        domain = domain[4:]

    return domain


def collect_domain_context(
    discovery: dict[str, Any],
) -> dict[str, dict[str, Any]]:

    profiles: dict[
        str,
        dict[str, Any],
    ] = defaultdict(
        lambda: {
            "verticals": set(),
            "queries": set(),
            "evidence_lines": [],
            "runs": 0,
        }
    )

    for run in discovery.get(
        "runs",
        [],
    ):

        vertical = str(
            run.get("vertical") or ""
        ).strip()

        query = str(
            run.get("query") or ""
        ).strip()

        text = (
            str(run.get("stdout_tail") or "")
            + "\n"
            + str(run.get("stderr_tail") or "")
        )

        lines = [
            line.strip()
            for line in text.splitlines()
            if line.strip()
        ]

        run_domains = set(
            run.get("domains") or []
        )

        for raw_domain in run_domains:

            domain = normalize_domain(
                str(raw_domain)
            )

            if not domain:
                continue

            profile = profiles[domain]

            profile["runs"] += 1

            if vertical:
                profile[
                    "verticals"
                ].add(vertical)

            if query:
                profile[
                    "queries"
                ].add(query)

            domain_lines = [
                line[:1000]
                for line in lines
                if domain in line.lower()
            ]

            profile[
                "evidence_lines"
            ].extend(
                domain_lines[:20]
            )

    return profiles


# Known identities must originate in buyer-specific evidence. Previously this
# walked ALL runtime JSON (~3.5 GB, 30k files), conflating logs/placeholder
# URLs with buyer identities and making every cycle expensive.
KNOWN_EVIDENCE_PATHS = (
    "buyer_acquisition/scout_latest.json",
    "buyer_acquisition/latest.json",
    "buyer_acquisition/linkedin_revenue_department_latest.json",
    "revenue_sprint/lead_buyer_evidence_2026-10-02.json",
    "truth_quality_control/buyer_input_latest.json",
)


def existing_runtime_domains() -> set[str]:
    domains: set[str] = set()
    runtime = ROOT / "runtime"
    for relative in KNOWN_EVIDENCE_PATHS:
        path = runtime / relative
        try:
            if not path.is_file() or path.stat().st_size > 5_000_000:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for match in DOMAIN_RE.finditer(text):
            domain = match.group(1).lower().rstrip(".")
            if accepted_domain(domain):
                domains.add(domain)
    return domains


def contains_any(
    text: str,
    terms: tuple[str, ...],
) -> bool:

    low = text.lower()

    return any(
        term in low
        for term in terms
    )


def score_profile(
    domain: str,
    profile: dict[str, Any],
    known_domains: set[str],
) -> dict[str, Any]:

    evidence_lines = list(
        dict.fromkeys(
            profile["evidence_lines"]
        )
    )

    evidence_text = "\n".join(
        evidence_lines
    )

    publisher = contains_any(
        evidence_text,
        PUBLISHER_POSITIVE,
    )

    demand = contains_any(
        evidence_text,
        DEMAND_POSITIVE,
    )

    integration = contains_any(
        evidence_text,
        INTEGRATION_POSITIVE,
    )

    economics = contains_any(
        evidence_text,
        ECONOMICS_POSITIVE,
    )

    compliance = contains_any(
        evidence_text,
        COMPLIANCE_POSITIVE,
    )

    contactable = contains_any(
        evidence_text,
        CONTACT_POSITIVE,
    )

    negative = contains_any(
        evidence_text,
        NEGATIVE,
    )

    evidence_count = sum(
        (
            publisher,
            demand,
            integration,
            economics,
            compliance,
            contactable,
        )
    )

    assessment = (
        BuyerNetworkIntegration
        .candidate(
            vertical_match=bool(
                profile["verticals"]
            ),

            publisher_program_confidence=(
                0.85
                if publisher
                else 0.0
            ),

            active_demand_confidence=(
                0.80
                if demand
                else 0.35
            ),

            inventory_fit_confidence=(
                0.45
                if demand
                else 0.0
            ),

            integration_confidence=(
                0.80
                if integration
                else 0.0
            ),

            economics_confidence=(
                0.80
                if economics
                else 0.0
            ),

            compliance_confidence=(
                0.75
                if compliance
                else 0.0
            ),

            contactable=contactable,

            negative_program_confidence=(
                0.95
                if negative
                else 0.0
            ),

            evidence_count=evidence_count,
        )
    )

    # Search-result presence is discovery evidence,
    # not sufficient proof for outreach readiness.
    readiness = assessment.readiness

    if (
        readiness
        == "READY_TO_APPROACH"
        and not (
            publisher
            and demand
        )
    ):
        readiness = "VERIFY_REQUIREMENTS"

    if negative:
        readiness = "REJECT"

    actively_verified = (
        "buyer-network-active-verification"
        in profile["queries"]
    )

    # Contextual/runtime evidence is sufficient for VERIFY,
    # but READY requires the dedicated active verifier.
    if (
        readiness == "READY_TO_APPROACH"
        and not actively_verified
    ):
        readiness = "VERIFY_REQUIREMENTS"

    return {
        "domain":
            domain,

        "status":
            readiness,

        "score":
            assessment.score,

        "already_known":
            domain in known_domains,

        "verticals":
            sorted(
                profile["verticals"]
            ),

        "discovery_queries":
            sorted(
                profile["queries"]
            ),

        "run_count":
            profile["runs"],

        "evidence": {
            "publisher_program":
                publisher,

            "active_demand":
                demand,

            "integration":
                integration,

            "economics":
                economics,

            "compliance":
                compliance,

            "contactable":
                contactable,

            "negative_program":
                negative,

            "evidence_count":
                evidence_count,

            "lines":
                evidence_lines[:12],
        },
    }


def main() -> int:

    discovery = json.loads(
        DISCOVERY.read_text()
    )

    profiles = collect_domain_context(
        discovery
    )
    # A failed or interrupted Search Fabric cycle must not erase the last
    # candidate queue. Leave the existing artifact untouched for review.
    if not profiles:
        raise RuntimeError("DISCOVERY_UNAVAILABLE_PRESERVE_EXISTING_BUYER_QUEUE")

    known_domains = (
        existing_runtime_domains()
    )

    candidates = [
        score_profile(
            domain,
            profile,
            known_domains,
        )
        for domain, profile
        in profiles.items()
        if accepted_domain(domain)
        and domain not in {"company.com", "insider.com"}
        and not domain.endswith(".sentry.io")
        and any(
            "runtime/truth_quality_control/" not in str(line)
            for line in profile.get("evidence_lines", [])
        )
    ]

    priority_order = {
        "READY_TO_APPROACH": 0,
        "VERIFY_REQUIREMENTS": 1,
        "WATCH": 2,
        "REJECT": 3,
    }

    # Discovery rank must never be mistaken for a fresh, uncontacted lead.
    contact_context = load_context()
    for item in candidates:
        contact = review(item["domain"], contact_context)
        item["contact_history"] = contact
        item["outreach_status"] = contact["state"]
        item["outbound_authorized"] = False

    candidates.sort(
        key=lambda item: (
            priority_order.get(
                item["status"],
                99,
            ),

            item["already_known"],

            -int(item["score"]),

            item["domain"],
        )
    )

    counts = {
        status: sum(
            1
            for item in candidates
            if item["status"] == status
        )
        for status in (
            "READY_TO_APPROACH",
            "VERIFY_REQUIREMENTS",
            "WATCH",
            "REJECT",
        )
    }

    payload = {
        "schema_version":
            "buyer-network-candidate-queue-v1",

        "generated_at":
            now_iso(),

        "authority":
            "OBSERVE",

        "source":
            "existing_buyer_discovery_preview",

        "candidate_count":
            len(candidates),

        "new_candidate_count":
            sum(
                1
                for item in candidates
                if not item["already_known"]
            ),

        "known_candidate_count":
            sum(
                1
                for item in candidates
                if item["already_known"]
            ),

        "status_counts":
            counts,

        "contact_history_gate_enabled": True,
        "contact_history_source": contact_context["source"],
        "gmail_snapshot_fresh": contact_context["gmail_snapshot_fresh"],

        "candidates":
            candidates,

        "governance": {
            "outbound_authority":
                False,

            "traffic_activation_authority":
                False,

            "commercial_terms_authority":
                False,

            "funds_authority":
                False,

            "ready_is_recommendation_only":
                True,
        },
    }

    atomic_write(
        OUTPUT,
        payload,
    )

    print(
        json.dumps(
            {
                "status": "PASS",

                "authority":
                    payload["authority"],

                "candidate_count":
                    payload[
                        "candidate_count"
                    ],

                "new_candidate_count":
                    payload[
                        "new_candidate_count"
                    ],

                "status_counts":
                    counts,

                "top_candidates": [
                    {
                        "domain":
                            item["domain"],

                        "status":
                            item["status"],

                        "score":
                            item["score"],

                        "already_known":
                            item[
                                "already_known"
                            ],
                    }

                    for item
                    in candidates[:25]
                ],

                "output":
                    str(OUTPUT),
            },
            indent=2,
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
