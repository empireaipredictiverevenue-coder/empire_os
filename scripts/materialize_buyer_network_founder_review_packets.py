from __future__ import annotations

import json
from datetime import datetime, timezone
import time
from pathlib import Path
from typing import Any

from empire_os.buyer_review_holds import load_review_holds
from empire_os.buyer_first_party_due_diligence import load_due_diligence
from empire_os.buyer_network_research_rotation import accepted_domain, RESULT_TTL_SECONDS
from empire_os.buyer_network_contact_history_gate import load_context, review


ROOT = Path("/srv/empire_os")
HOLDS = ROOT / "config/buyer_network_manual_review_holds.json"
DUE_DILIGENCE = ROOT / "runtime/buyer_network_intelligence/due_diligence_latest.json"

BASE = (
    ROOT
    / "runtime"
    / "buyer_network_intelligence"
)

DISCOVERY = BASE / "discovery_latest.json"
VERIFICATION = BASE / "verification_latest.json"
DIRECT_SITE = BASE / "direct_site_verification_latest.json"
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

    if not accepted_domain(domain):
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


def active_verified_domains(discovery, site_snapshot=None, *, now_epoch=None):
    """Use durable, independently fetched site results, not transient search rows.

    This is only evidence to REVIEW. It does not establish live campaigns,
    contacts, commercial terms, or permission to approach anyone.
    """
    if site_snapshot is None:
        return {
            str(domain).lower()
            for run in discovery.get("runs", [])
            if run.get("verification_source") == "direct-site"
            and run.get("status") == "PASS"
            and run.get("query") == "buyer-network-active-verification"
            and len(run.get("domains") or []) == 1
            for domain in (run.get("domains") or [])
            if valid_domain(str(domain))
        }
    if (not isinstance(site_snapshot, dict)
            or site_snapshot.get("schema_version") != "buyer-direct-site-verification-v1"
            or site_snapshot.get("authority") != "OBSERVE"
            or not isinstance(site_snapshot.get("governance"), dict)
            or site_snapshot["governance"].get("outbound") is not False
            or site_snapshot["governance"].get("traffic_activation") is not False
            or site_snapshot["governance"].get("commercial_terms") is not False
            or not isinstance(site_snapshot.get("results"), list)
            or len(site_snapshot["results"]) > 3000):
        return set()
    now = time.time() if now_epoch is None else now_epoch
    try:
        snapshot_epoch = float(site_snapshot["generated_epoch"])
    except (KeyError, TypeError, ValueError):
        return set()
    if not 0 <= now - snapshot_epoch <= RESULT_TTL_SECONDS:
        return set()
    corroborated = set()
    conflicts = set()
    for row in site_snapshot["results"]:
        if not isinstance(row, dict):
            continue
        domain = str(row.get("domain") or "").lower()
        if not valid_domain(domain):
            continue
        try:
            observed = float(row.get("observed_epoch") or 0)
        except (ValueError, TypeError):
            continue
        if (not 0 <= now - observed <= RESULT_TTL_SECONDS
                or row.get("corroborated") is not True
                or row.get("buyer_role") is not True
                or type(row.get("pages_successful")) is not int
                or row["pages_successful"] < 1
                or type(row.get("positive_category_count")) is not int
                or row["positive_category_count"] < 2
                or not isinstance(row.get("evidence"), dict)
                or row["evidence"].get("negative_program") is True):
            continue
        if domain in corroborated:
            conflicts.add(domain)
        corroborated.add(domain)
    return corroborated - conflicts


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

    # Founder due-diligence HOLD policy is authoritative for review promotion.
    # Evaluate it before any existing runtime snapshot is overwritten.
    manual_holds = load_review_holds(HOLDS)
    site_reviews, automated_holds = load_due_diligence(
        DUE_DILIGENCE, now_epoch=time.time(),
    )

    discovery = json.loads(
        DISCOVERY.read_text()
    )

    verification = json.loads(
        VERIFICATION.read_text()
    )

    queue = json.loads(
        QUEUE.read_text()
    )
    contact_context = load_context()

    # Direct-site observer owns durable, timestamped independent evidence.
    # Search Fabric can replace discovery.runs between cycles, so transient
    # run entries are not the source of truth for the founder packets.
    try:
        if (DIRECT_SITE.is_symlink() or not DIRECT_SITE.is_file()
                or DIRECT_SITE.stat().st_size > 4_000_000):
            raise ValueError("BUYER_DIRECT_SITE_SNAPSHOT_UNSAFE")
        site_snapshot = json.loads(DIRECT_SITE.read_text())
    except (OSError, ValueError, TypeError):
        site_snapshot = {"invalid": True}
    active = active_verified_domains(discovery, site_snapshot)

    verified = verification_map(
        verification
    )

    packets = []
    backlog = []
    held_domains = []
    automated_held_domains = []
    pending_due_diligence_domains = []

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
        contact = review(domain, contact_context)

        manual_hold = manual_holds.get(domain)
        if manual_hold is not None:
            held_domains.append(domain)
            backlog.append({
                "domain": domain,
                "status": "MANUAL_EVIDENCE_HOLD",
                "source_status": candidate.get("status"),
                "score": candidate.get("score"),
                "verticals": candidate.get("verticals", []),
                "reasons": ["manual_hold:" + manual_hold["reason_code"]],
                "review_required": True,
                "authority": "OBSERVE",
                "outbound_authority": False,
            })
            continue

        status = candidate.get(
            "status"
        )

        automated_hold = automated_holds.get(domain)
        if automated_hold is not None:
            automated_held_domains.append(domain)
            backlog.append({
                "domain": domain,
                "status": "AUTOMATED_EVIDENCE_HOLD",
                "source_status": status,
                "score": candidate.get("score"),
                "verticals": candidate.get("verticals", []),
                "reasons": ["automated_hold:" + automated_hold["reason_code"]],
                "review_required": True,
                "evidence_observed_at": automated_hold["observed_at"],
                "authority": "OBSERVE",
                "outbound_authority": False,
            })
            continue

        site_review = site_reviews.get(domain) or {}
        due_current = (
            site_review.get("freshness") == "CURRENT"
            and site_review.get("homepage_reachable") is True
            and site_review.get("state") == "NEEDS_FOUNDER_REVIEW"
        )
        if status == "READY_TO_APPROACH" and not due_current:
            pending_due_diligence_domains.append(domain)
            backlog.append({
                "domain": domain,
                "status": "DUE_DILIGENCE_PENDING",
                "source_status": status,
                "score": candidate.get("score"),
                "verticals": candidate.get("verticals", []),
                "reasons": ["first_party_due_diligence_missing_stale_or_unavailable"],
                "review_required": True,
                "authority": "OBSERVE",
                "outbound_authority": False,
            })
            continue

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
                    "first_party_due_diligence_current": True,
                    "due_diligence_link_count": site_review.get("link_count", 0),
                    "commercial_terms_verified": False,
                    "payout_economics_verified": False,
                    "contact_history": contact,

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

            "manual_hold_count": len(held_domains),
            "manual_hold_domains": sorted(set(held_domains)),
            "automated_evidence_hold_count": len(automated_held_domains),
            "automated_evidence_hold_domains": sorted(set(automated_held_domains)),
            "due_diligence_pending_count": len(pending_due_diligence_domains),

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

            "manual_hold_count": len(held_domains),
            "automated_evidence_hold_count": len(automated_held_domains),
            "due_diligence_pending_count": len(pending_due_diligence_domains),
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
        ("Manual due-diligence holds: " + str(len(held_domains))),
        ("Automated critical-link holds: " + str(len(automated_held_domains))),
        ("Pending independent first-party link checks: " + str(len(pending_due_diligence_domains))),
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

                "manual_hold_count": len(held_domains),
                "automated_evidence_hold_count": len(automated_held_domains),
                "due_diligence_pending_count": len(pending_due_diligence_domains),

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
