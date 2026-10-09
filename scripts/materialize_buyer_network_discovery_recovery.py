from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


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


BUYER_SIGNALS = (
    "buyer",
    "buyers",
    "publisher",
    "publishers",
    "pay per call",
    "pay-per-call",
    "lead buyer",
    "lead buyers",
    "lead network",
    "lead exchange",
    "live transfer",
    "live transfers",
    "inbound call",
    "inbound calls",
    "traffic partner",
    "traffic partners",
    "media partner",
    "media partners",
    "affiliate program",
    "publisher program",
    "revshare",
    "revenue share",
    "payout",
    "ping post",
    "ping-post",
    "rtb",
    "lead distribution",
    "lead routing",
)


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
        "law firm",
        "legal leads",
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


def normalise_domain(
    raw: str,
) -> str | None:

    m = DOMAIN_RE.search(
        raw or ""
    )

    if not m:
        return None

    domain = (
        m.group(1)
        .lower()
        .rstrip(".")
    )

    if domain.startswith("www."):
        domain = domain[4:]

    if domain in IGNORE:
        return None

    return domain


def flatten(
    value: Any,
    prefix: str = "",
):
    if isinstance(value, dict):

        for key, item in value.items():

            child = (
                f"{prefix}.{key}"
                if prefix
                else str(key)
            )

            yield from flatten(
                item,
                child,
            )

    elif isinstance(value, list):

        for index, item in enumerate(value):

            yield from flatten(
                item,
                f"{prefix}[{index}]",
            )

    else:
        yield prefix, value


def buyer_signal_count(
    text: str,
) -> int:

    low = text.lower()

    return sum(
        1
        for signal in BUYER_SIGNALS
        if signal in low
    )


def detect_verticals(
    text: str,
) -> list[str]:

    low = text.lower()

    found = []

    for vertical, terms in VERTICALS.items():

        if any(
            term in low
            for term in terms
        ):
            found.append(
                vertical
            )

    return found or [
        "home_services"
    ]


def runtime_json_files():
    for path in RUNTIME.rglob("*.json"):

        text = str(path)

        if (
            "buyer_network_intelligence"
            in text
        ):
            continue

        low = text.lower()

        if not any(
            token in low
            for token in (
                "buyer",
                "lead",
                "revenue",
                "opportunity",
                "commercial",
            )
        ):
            continue

        yield path


def collect() -> dict[str, dict[str, Any]]:

    profiles: dict[
        str,
        dict[str, Any],
    ] = defaultdict(
        lambda: {
            "contexts": [],
            "sources": set(),
            "verticals": set(),
            "signal_count": 0,
        }
    )

    for path in runtime_json_files():

        try:
            payload = json.loads(
                path.read_text(
                    encoding="utf-8",
                    errors="replace",
                )
            )

        except Exception:
            continue

        flattened = list(
            flatten(payload)
        )

        document_text = " ".join(
            str(value)
            for _, value in flattened
            if value is not None
        )

        doc_signals = buyer_signal_count(
            document_text
        )

        if doc_signals <= 0:
            continue

        doc_verticals = detect_verticals(
            document_text
        )

        for key, value in flattened:

            if not isinstance(
                value,
                str,
            ):
                continue

            domain = normalise_domain(
                value
            )

            if not domain:
                continue

            # Build nearby evidence from this field plus
            # the buyer-signalled document context.
            context = (
                f"{domain} "
                f"source={path.relative_to(ROOT)} "
                f"field={key} "
                f"{value[:600]}"
            )

            profile = profiles[
                domain
            ]

            profile[
                "sources"
            ].add(
                str(
                    path.relative_to(ROOT)
                )
            )

            profile[
                "verticals"
            ].update(
                doc_verticals
            )

            profile[
                "signal_count"
            ] = max(
                profile[
                    "signal_count"
                ],
                doc_signals,
            )

            profile[
                "contexts"
            ].append(
                context
            )

    return profiles


def main() -> int:

    profiles = collect()

    runs = []

    for domain, profile in sorted(
        profiles.items()
    ):

        # Require more than accidental mention.
        if (
            profile[
                "signal_count"
            ] < 2
        ):
            continue

        contexts = list(
            dict.fromkeys(
                profile[
                    "contexts"
                ]
            )
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
                    "existing-runtime-buyer-evidence",

                "domains":
                    [domain],

                "stdout_tail":
                    "\n".join(
                        contexts[:15]
                    ),

                "stderr_tail":
                    "",

                "evidence_sources":
                    sorted(
                        profile[
                            "sources"
                        ]
                    ),

                "signal_count":
                    profile[
                        "signal_count"
                    ],
            }
        )

    domains = sorted(
        {
            domain
            for run in runs
            for domain in run[
                "domains"
            ]
        }
    )

    payload = {
        "schema_version":
            "buyer-network-discovery-v2",

        "generated_at":
            now_iso(),

        "authority":
            "OBSERVE",

        "source":
            "existing_empireos_runtime_truth",

        "search_executable":
            False,

        "recovery_mode":
            True,

        "query_count":
            len(runs),

        "candidate_domain_count":
            len(domains),

        "candidate_domains":
            domains,

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
                    len(domains),

                "run_count":
                    len(runs),

                "sample_domains":
                    domains[:40],

                "output":
                    str(OUTPUT),
            },
            indent=2,
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
