from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


ROOT = Path("/srv/empire_os")
RUNTIME = ROOT / "runtime"

OUTPUT = (
    RUNTIME
    / "buyer_network_intelligence"
    / "discovery_latest.json"
)


DOMAIN_RE = re.compile(
    r"(?:https?://)?(?:www\.)?"
    r"([a-z0-9][a-z0-9.-]+\.[a-z]{2,})",
    re.I,
)


SIGNALS = {
    "publisher": (
        "publisher program",
        "publishers",
        "become a publisher",
        "affiliate program",
        "media partners",
        "traffic partners",
        "lead partners",
    ),

    "demand": (
        "pay per call",
        "pay-per-call",
        "lead buyer",
        "lead buyers",
        "buy leads",
        "live transfer",
        "live transfers",
        "inbound calls",
        "consumer initiated",
        "consumer-initiated",
    ),

    "integration": (
        "rtb",
        "ping post",
        "ping-post",
        "webhook",
        "api",
        "call tracking",
        "tracking platform",
        "lead routing",
    ),

    "economics": (
        "payout",
        "revshare",
        "revenue share",
        "cost per call",
        "per qualified call",
        "cpl",
        "cpa",
    ),

    "compliance": (
        "tcpa",
        "consent",
        "trustedform",
        "jornaya",
        "compliance",
    ),

    "contact": (
        "contact",
        "apply",
        "sign up",
        "signup",
        "get started",
        "join",
    ),

    "negative": (
        "not accepting publishers",
        "publisher program closed",
        "not accepting affiliates",
        "not accepting traffic",
        "program paused",
    ),
}


VERTICALS = {
    "roofing": (
        "roofing",
        "roofer",
    ),

    "hvac": (
        "hvac",
        "air conditioning",
        "heating",
    ),

    "restoration": (
        "restoration",
        "water damage",
        "fire damage",
    ),

    "solar": (
        "solar",
    ),

    "legal": (
        "mass tort",
        "legal leads",
        "law firm",
    ),

    "home_services": (
        "home services",
        "contractor",
        "plumbing",
        "electrical",
    ),
}


IGNORE = {
    "google.com",
    "bing.com",
    "duckduckgo.com",
    "github.com",
    "python.org",
    "pypi.org",
    "facebook.com",
    "linkedin.com",
    "youtube.com",
    "reddit.com",
    "twitter.com",
    "x.com",
}


def now_iso() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


def domains(text: str) -> set[str]:
    result = set()

    for match in DOMAIN_RE.finditer(
        text or ""
    ):
        domain = (
            match.group(1)
            .lower()
            .rstrip(".")
        )

        if domain.startswith("www."):
            domain = domain[4:]

        if domain in IGNORE:
            continue

        result.add(domain)

    return result


def match_signals(
    text: str,
) -> dict[str, list[str]]:

    low = text.lower()

    return {
        category: [
            term
            for term in terms
            if term in low
        ]

        for category, terms
        in SIGNALS.items()
    }


def detect_verticals(
    text: str,
) -> list[str]:

    low = text.lower()

    found = [
        vertical

        for vertical, terms
        in VERTICALS.items()

        if any(
            term in low
            for term in terms
        )
    ]

    return (
        found
        if found
        else ["home_services"]
    )


def iter_nodes(
    value: Any,
    path: str = "$",
) -> Iterator[tuple[str, Any]]:

    if isinstance(value, dict):

        yield path, value

        for key, child in value.items():

            yield from iter_nodes(
                child,
                f"{path}.{key}",
            )

    elif isinstance(value, list):

        for index, child in enumerate(
            value
        ):

            yield from iter_nodes(
                child,
                f"{path}[{index}]",
            )


def compact_text(
    value: Any,
) -> str:

    try:
        text = json.dumps(
            value,
            ensure_ascii=False,
            default=str,
        )

    except Exception:
        text = str(value)

    return " ".join(
        text.split()
    )


def runtime_files():

    for path in RUNTIME.rglob(
        "*.json"
    ):

        low = str(path).lower()

        if (
            "buyer_network_intelligence"
            in low
        ):
            continue

        if not any(
            token in low
            for token in (
                "buyer",
                "lead",
                "commercial",
                "revenue",
                "opportunity",
            )
        ):
            continue

        yield path


def collect():

    evidence: dict[
        str,
        dict[str, Any],
    ] = defaultdict(
        lambda: {
            "sources": set(),
            "verticals": set(),
            "contexts": [],
            "categories": set(),
            "matched_terms": set(),
        }
    )

    for source in runtime_files():

        try:
            payload = json.loads(
                source.read_text(
                    encoding="utf-8",
                    errors="replace",
                )
            )

        except Exception:
            continue

        for json_path, node in iter_nodes(
            payload
        ):

            text = compact_text(
                node
            )

            # Prevent broad top-level documents
            # from falsely pairing unrelated domains.
            if (
                len(text) < 20
                or len(text) > 12000
            ):
                continue

            node_domains = domains(
                text
            )

            if (
                not node_domains
                or len(node_domains) > 5
            ):
                continue

            matched = match_signals(
                text
            )

            positive_categories = {
                category

                for category in (
                    "publisher",
                    "demand",
                    "integration",
                    "economics",
                    "compliance",
                    "contact",
                )

                if matched[
                    category
                ]
            }

            # Require localized buyer evidence.
            if len(
                positive_categories
            ) < 2:
                continue

            verticals = detect_verticals(
                text
            )

            actual_terms = sorted(
                {
                    term

                    for terms
                    in matched.values()

                    for term in terms
                }
            )

            excerpt = text[:2500]

            for domain in node_domains:

                profile = evidence[
                    domain
                ]

                profile[
                    "sources"
                ].add(
                    str(
                        source.relative_to(
                            ROOT
                        )
                    )
                )

                profile[
                    "verticals"
                ].update(
                    verticals
                )

                profile[
                    "categories"
                ].update(
                    positive_categories
                )

                profile[
                    "matched_terms"
                ].update(
                    actual_terms
                )

                profile[
                    "contexts"
                ].append(
                    {
                        "source":
                            str(
                                source.relative_to(
                                    ROOT
                                )
                            ),

                        "json_path":
                            json_path,

                        "excerpt":
                            excerpt,

                        "terms":
                            actual_terms,
                    }
                )

    return evidence


def main() -> int:

    evidence = collect()

    runs = []

    for domain, profile in sorted(
        evidence.items()
    ):

        contexts = profile[
            "contexts"
        ]

        lines = []

        for context in contexts[:12]:

            terms = " ".join(
                context["terms"]
            )

            lines.append(
                f"{domain} "
                f"{terms} "
                f"source={context['source']} "
                f"path={context['json_path']} "
                f"context={context['excerpt']}"
            )

        verticals = sorted(
            profile[
                "verticals"
            ]
        )

        runs.append(
            {
                "status":
                    "PASS",

                "vertical":
                    (
                        verticals[0]
                        if verticals
                        else "home_services"
                    ),

                "query":
                    "contextual-runtime-buyer-evidence",

                "domains":
                    [domain],

                "stdout_tail":
                    "\n".join(
                        lines
                    ),

                "stderr_tail":
                    "",

                "evidence_sources":
                    sorted(
                        profile[
                            "sources"
                        ]
                    ),

                "evidence_categories":
                    sorted(
                        profile[
                            "categories"
                        ]
                    ),

                "matched_terms":
                    sorted(
                        profile[
                            "matched_terms"
                        ]
                    ),
            }
        )

    candidate_domains = sorted(
        {
            domain

            for run in runs

            for domain
            in run["domains"]
        }
    )

    payload = {
        "schema_version":
            "buyer-network-discovery-v3-contextual",

        "generated_at":
            now_iso(),

        "authority":
            "OBSERVE",

        "source":
            "existing_empireos_contextual_runtime_evidence",

        "candidate_domain_count":
            len(candidate_domains),

        "candidate_domains":
            candidate_domains,

        "query_count":
            len(runs),

        "runs":
            runs,

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

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    tmp = OUTPUT.with_suffix(
        ".tmp"
    )

    tmp.write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    tmp.replace(
        OUTPUT
    )

    print(
        json.dumps(
            {
                "status":
                    "PASS",

                "candidate_domain_count":
                    len(
                        candidate_domains
                    ),

                "sample": [
                    {
                        "domain":
                            run["domains"][0],

                        "categories":
                            run[
                                "evidence_categories"
                            ],

                        "terms":
                            run[
                                "matched_terms"
                            ][:12],
                    }

                    for run
                    in runs[:30]
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
