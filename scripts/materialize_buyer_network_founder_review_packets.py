from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path("/srv/empire_os")

BASE = (
    ROOT
    / "runtime"
    / "buyer_network_intelligence"
)

DISCOVERY = BASE / "discovery_latest.json"
VERIFICATION = BASE / "verification_latest.json"
QUEUE = BASE / "candidate_queue_latest.json"

PACKETS = (
    BASE
    / "founder_review_packets_latest.json"
)

PACKETS_MD = (
    BASE
    / "founder_review_packets_latest.md"
)

BACKLOG = (
    BASE
    / "verification_backlog_latest.json"
)


BLOCKED = {
    "ahrefs.com",
    "semrush.com",
    "serpapi.com",
    "localfalcon.com",
    "aol.com",
}


def now_iso():
    return datetime.now(
        timezone.utc
    ).isoformat()


def valid_domain(domain: str) -> bool:

    domain = (
        domain or ""
    ).strip().lower()

    if not domain:
        return False

    if domain.startswith("empire."):
        return False

    if domain in BLOCKED:
        return False

    if domain.endswith(
        (
            ".json",
            ".md",
            ".txt",
            ".py",
            ".sql",
            ".yaml",
            ".yml",
        )
    ):
        return False

    if "." not in domain:
        return False

    labels = domain.split(".")

    allowed_tlds = {
        "com", "co", "uk", "io", "ai", "net", "org",
        "us", "ca", "biz", "info", "pro", "media",
        "marketing", "agency", "digital", "group",
        "company", "services", "solutions",
    }

    if labels[-1] not in allowed_tlds:
        return False

    for label in labels:
        if not label:
            return False

        if label.startswith("-") or label.endswith("-"):
            return False

        if not all(
            ch.isalnum() or ch == "-"
            for ch in label
        ):
            return False

    return True


def write_json(path, value):

    tmp = path.with_suffix(".tmp")

    tmp.write_text(
        json.dumps(
            value,
            indent=2,
            sort_keys=True,
            default=str,
        )
        + "\n",
        encoding="utf-8",
    )

    tmp.replace(path)


def active_verified_domains(discovery):

    return {
        str(domain).lower()

        for run in discovery.get(
            "runs",
            [],
        )

        if run.get("query")
        == "buyer-network-active-verification"

        for domain in (
            run.get("domains")
            or []
        )

        if valid_domain(
            str(domain)
        )
    }


def verification_map(data):

    result = {}

    for item in data.get(
        "verifications",
        [],
    ):

        domain = str(
            item.get("domain")
            or ""
        ).lower()

        if valid_domain(domain):
            result[domain] = item

    return result


def genuine(item):

    if not item:
        return False

    evidence = item.get(
        "evidence",
        {},
    )

    buyer_role = bool(
        evidence.get(
            "publisher_program"
        )
        or evidence.get(
            "active_demand"
        )
    )

    positive = sum(
        bool(
            evidence.get(key)
        )

        for key in (
            "publisher_program",
            "active_demand",
            "integration",
            "economics",
            "compliance",
            "contactable",
        )
    )

    return (
        buyer_role
        and positive >= 2
        and not evidence.get(
            "negative_program"
        )
    )


def gaps(candidate):

    evidence = candidate.get(
        "evidence",
        {},
    )

    return [
        key

        for key in (
            "publisher_program",
            "active_demand",
            "integration",
            "economics",
            "compliance",
            "contactable",
        )

        if not evidence.get(key)
    ]


def main():

    discovery = json.loads(
        DISCOVERY.read_text()
    )

    verification = json.loads(
        VERIFICATION.read_text()
    )

    queue = json.loads(
        QUEUE.read_text()
    )

    active = active_verified_domains(
        discovery
    )

    verified = verification_map(
        verification
    )

    packets = []
    backlog = []

    for candidate in queue.get(
        "candidates",
        [],
    ):

        domain = str(
            candidate.get("domain")
            or ""
        ).lower()

        if not valid_domain(domain):
            continue

        status = candidate.get(
            "status"
        )

        verified_item = verified.get(
            domain
        )

        provenance = (
            domain in active
        )

        corroborated = genuine(
            verified_item
        )

        if (
            status
            == "READY_TO_APPROACH"
            and provenance
            and corroborated
        ):

            packets.append(
                {
                    "domain":
                        domain,

                    "score":
                        candidate.get(
                            "score"
                        ),

                    "verticals":
                        candidate.get(
                            "verticals",
                            [],
                        ),

                    "evidence":
                        verified_item.get(
                            "evidence",
                            {},
                        ),

                    "active_verification":
                        True,

                    "buyer_role_corroborated":
                        True,

                    "authority":
                        "FOUNDER_REVIEW_ONLY",

                    "outbound_authority":
                        False,

                    "traffic_authority":
                        False,

                    "predictive_revenue":
                        {
                            "forecast":
                                None,

                            "reason":
                                (
                                    "Await observed "
                                    "commercial economics."
                                ),
                        },
                }
            )

            continue

        if status in (
            "READY_TO_APPROACH",
            "VERIFY_REQUIREMENTS",
            "WATCH",
        ):

            reasons = []

            if not provenance:
                reasons.append(
                    "missing_active_verification"
                )

            if not corroborated:
                reasons.append(
                    "buyer_role_not_corroborated"
                )

            reasons.extend(
                f"missing:{gap}"
                for gap in gaps(
                    candidate
                )
            )

            backlog.append(
                {
                    "domain":
                        domain,

                    "status":
                        status,

                    "score":
                        candidate.get(
                            "score"
                        ),

                    "verticals":
                        candidate.get(
                            "verticals",
                            [],
                        ),

                    "reasons":
                        list(
                            dict.fromkeys(
                                reasons
                            )
                        ),

                    "authority":
                        "OBSERVE",
                }
            )

    packets.sort(
        key=lambda x: (
            -int(x["score"] or 0),
            x["domain"],
        )
    )

    backlog.sort(
        key=lambda x: (
            0
            if x["status"]
            == "VERIFY_REQUIREMENTS"
            else 1,

            -int(x["score"] or 0),

            x["domain"],
        )
    )

    write_json(
        PACKETS,
        {
            "schema_version":
                "buyer-founder-review-v1",

            "generated_at":
                now_iso(),

            "authority":
                "FOUNDER_REVIEW_ONLY",

            "trusted_ready_count":
                len(packets),

            "packets":
                packets,

            "governance":
                {
                    "outbound":
                        False,

                    "db_write":
                        False,

                    "traffic":
                        False,

                    "funds":
                        False,
                },
        },
    )

    write_json(
        BACKLOG,
        {
            "schema_version":
                "buyer-verification-backlog-v1",

            "generated_at":
                now_iso(),

            "authority":
                "OBSERVE",

            "backlog_count":
                len(backlog),

            "candidates":
                backlog,
        },
    )

    lines = [
        "# Empire AI — Trusted Buyer Founder Review",
        "",
        (
            "Trusted READY buyers: "
            + str(len(packets))
        ),
        (
            "Verification backlog: "
            + str(len(backlog))
        ),
        "",
    ]

    if not packets:

        lines.extend(
            [
                (
                    "No candidate currently satisfies "
                    "all trusted READY gates."
                ),
                "",
                "Outbound remains blocked.",
                "",
            ]
        )

    for i, packet in enumerate(
        packets,
        1,
    ):

        evidence = [
            key
            for key, value
            in packet[
                "evidence"
            ].items()
            if value
        ]

        lines.extend(
            [
                (
                    f"## {i}. "
                    f"{packet['domain']}"
                ),
                "",
                (
                    f"- Score: "
                    f"{packet['score']}"
                ),
                (
                    "- Verticals: "
                    + ", ".join(
                        packet[
                            "verticals"
                        ]
                    )
                ),
                (
                    "- Evidence: "
                    + ", ".join(
                        evidence
                    )
                ),
                (
                    "- Active verification: YES"
                ),
                (
                    "- Buyer role corroborated: YES"
                ),
                (
                    "- Authority: FOUNDER REVIEW ONLY"
                ),
                (
                    "- Outbound: BLOCKED"
                ),
                "",
            ]
        )

    PACKETS_MD.write_text(
        "\n".join(lines)
        + "\n",
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "status":
                    "PASS",

                "trusted_ready_count":
                    len(packets),

                "trusted_ready_domains":
                    [
                        x["domain"]
                        for x in packets
                    ],

                "verification_backlog":
                    len(backlog),

                "backlog_top_20":
                    [
                        {
                            "domain":
                                x[
                                    "domain"
                                ],

                            "status":
                                x[
                                    "status"
                                ],

                            "score":
                                x[
                                    "score"
                                ],

                            "reasons":
                                x[
                                    "reasons"
                                ],
                        }

                        for x
                        in backlog[:20]
                    ],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
