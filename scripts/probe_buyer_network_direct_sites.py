from __future__ import annotations

import argparse
import concurrent.futures
import html
import json
import re
import socket
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
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
BACKLOG = BASE / "verification_backlog_latest.json"

DIRECT = BASE / "direct_site_verification_latest.json"

MAX_CANDIDATES = 8
MAX_WORKERS = 8
TIMEOUT = 8
MAX_BYTES = 750_000
CACHE_SECONDS = 6 * 60 * 60

USER_AGENT = (
    "EmpireAI-BuyerResearch/1.0 "
    "(public-business-research; read-only)"
)

PATHS = (
    "/",
    "/publishers",
    "/publisher",
    "/partners",
    "/advertisers",
    "/buyers",
    "/contact",
    "/compliance",
)

ALLOWED_TLDS = {
    "com", "co", "uk", "io", "ai", "net", "org",
    "us", "ca", "biz", "info", "pro", "media",
    "marketing", "agency", "digital", "group",
    "company", "services", "solutions",
}

BLOCKED = {
    "ahrefs.com",
    "semrush.com",
    "serpapi.com",
    "localfalcon.com",
    "aol.com",
}

WATCH_DOMAIN_HINTS = (
    "lead",
    "call",
    "market",
    "media",
    "performance",
    "partner",
    "buyer",
    "publisher",
    "traffic",
)


SIGNALS = {
    "publisher_program": (
        "become a publisher",
        "publisher program",
        "publisher network",
        "publisher signup",
        "publisher sign up",
        "our publishers",
        "publishers can",
        "publishers earn",
        "traffic partners",
        "media partners",
        "lead partners",
        "affiliate partners",
    ),

    "active_demand": (
        "pay per call",
        "pay-per-call",
        "inbound calls",
        "qualified calls",
        "qualified call",
        "buy leads",
        "lead buyers",
        "lead buyer",
        "live transfer",
        "live transfers",
        "call buyers",
        "calls from publishers",
        "consumer initiated",
        "consumer-initiated",
    ),

    "integration": (
        "ping post",
        "ping-post",
        "real time bidding",
        "real-time bidding",
        " rtb ",
        "webhook",
        "lead routing",
        "call tracking",
        "api integration",
        "integrate via api",
    ),

    "economics": (
        "payout",
        "revshare",
        "revenue share",
        "cost per call",
        "pay per qualified call",
        "paid per call",
        "earn per call",
        "cpl",
        "cpa",
    ),

    "compliance": (
        "tcpa",
        "trustedform",
        "jornaya",
        "express written consent",
        "prior express consent",
        "consent requirements",
        "compliance requirements",
    ),

    "contactable": (
        "contact us",
        "get in touch",
        "apply now",
        "apply today",
        "publisher application",
        "partner application",
        "become a partner",
        "get started",
    ),

    "negative_program": (
        "not accepting publishers",
        "not accepting affiliates",
        "not accepting traffic",
        "publisher program closed",
        "program is paused",
        "program paused",
    ),
}


VERTICALS = {
    "roofing": (
        "roofing",
        "roof replacement",
        "roof repair",
    ),

    "hvac": (
        "hvac",
        "heating and cooling",
        "air conditioning",
    ),

    "restoration": (
        "restoration",
        "water damage",
        "fire damage",
    ),

    "solar": (
        "solar",
        "solar installation",
    ),

    "legal": (
        "legal leads",
        "mass tort",
        "personal injury",
        "law firms",
    ),

    "home_services": (
        "home services",
        "home improvement",
        "contractors",
        "plumbing",
        "electrical",
    ),
}


def now_iso() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


def valid_domain(domain: str) -> bool:

    domain = (
        domain or ""
    ).strip().lower().rstrip(".")

    if not domain or "." not in domain:
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

    labels = domain.split(".")

    if (
        len(labels) < 2
        or labels[-1]
        not in ALLOWED_TLDS
    ):
        return False

    for label in labels:

        if not label:
            return False

        if (
            label.startswith("-")
            or label.endswith("-")
        ):
            return False

        if not all(
            ch.isalnum()
            or ch == "-"
            for ch in label
        ):
            return False

    return True


def strip_html(raw: str) -> str:

    raw = re.sub(
        r"(?is)<script.*?>.*?</script>",
        " ",
        raw,
    )

    raw = re.sub(
        r"(?is)<style.*?>.*?</style>",
        " ",
        raw,
    )

    raw = re.sub(
        r"(?is)<noscript.*?>.*?</noscript>",
        " ",
        raw,
    )

    raw = re.sub(
        r"(?s)<[^>]+>",
        " ",
        raw,
    )

    raw = html.unescape(raw)

    return " ".join(
        raw.split()
    )


def evidence(text: str) -> dict[str, bool]:

    normalized = (
        " "
        + text.lower()
        + " "
    )

    return {
        category: any(
            phrase in normalized
            for phrase in phrases
        )

        for category, phrases
        in SIGNALS.items()
    }


def matched_terms(text: str) -> dict[str, list[str]]:

    normalized = (
        " "
        + text.lower()
        + " "
    )

    return {
        category: [
            phrase
            for phrase in phrases
            if phrase in normalized
        ]

        for category, phrases
        in SIGNALS.items()
    }


def verticals(text: str) -> list[str]:

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

    return found


def same_domain(
    expected: str,
    final_url: str,
) -> bool:

    try:
        hostname = (
            urllib.parse.urlparse(
                final_url
            )
            .hostname
            or ""
        ).lower()

    except Exception:
        return False

    return (
        hostname == expected
        or hostname.endswith(
            "." + expected
        )
    )


def fetch_one(
    domain: str,
    path: str,
) -> dict[str, Any]:

    urls = [
        f"https://{domain}{path}",
    ]

    if path == "/":
        urls.append(
            f"http://{domain}/"
        )

    last_error = None

    for url in urls:

        request = urllib.request.Request(
            url,
            headers={
                "User-Agent":
                    USER_AGENT,

                "Accept":
                    (
                        "text/html,"
                        "application/xhtml+xml"
                    ),
            },
            method="GET",
        )

        try:
            context = ssl.create_default_context()

            with urllib.request.urlopen(
                request,
                timeout=TIMEOUT,
                context=context,
            ) as response:

                final_url = response.geturl()

                if not same_domain(
                    domain,
                    final_url,
                ):
                    return {
                        "url":
                            url,

                        "status":
                            "REDIRECT_OUTSIDE_DOMAIN",

                        "final_url":
                            final_url,

                        "text":
                            "",
                    }

                content_type = (
                    response.headers.get(
                        "Content-Type",
                        ""
                    )
                    .lower()
                )

                if (
                    "text/html"
                    not in content_type
                    and "text/plain"
                    not in content_type
                ):
                    return {
                        "url":
                            url,

                        "status":
                            "UNSUPPORTED_CONTENT",

                        "final_url":
                            final_url,

                        "text":
                            "",
                    }

                raw = response.read(
                    MAX_BYTES
                )

                charset = (
                    response.headers
                    .get_content_charset()
                    or "utf-8"
                )

                decoded = raw.decode(
                    charset,
                    errors="replace",
                )

                text = strip_html(
                    decoded
                )

                return {
                    "url":
                        url,

                    "status":
                        "PASS",

                    "http_status":
                        getattr(
                            response,
                            "status",
                            200,
                        ),

                    "final_url":
                        final_url,

                    "text":
                        text[:100_000],
                }

        except (
            urllib.error.HTTPError,
            urllib.error.URLError,
            TimeoutError,
            socket.timeout,
            ssl.SSLError,
        ) as exc:

            last_error = (
                f"{type(exc).__name__}:"
                f"{str(exc)[:300]}"
            )

        except Exception as exc:

            last_error = (
                f"{type(exc).__name__}:"
                f"{str(exc)[:300]}"
            )

    return {
        "url":
            urls[0],

        "status":
            "ERROR",

        "error":
            last_error
            or "unknown",

        "text":
            "",
    }


def select_candidates(
    backlog: dict[str, Any],
) -> list[dict[str, Any]]:

    candidates = [
        item

        for item in backlog.get(
            "candidates",
            [],
        )

        if valid_domain(
            str(
                item.get("domain")
                or ""
            )
        )
    ]

    verify = [
        item
        for item in candidates
        if item.get("status")
        == "VERIFY_REQUIREMENTS"
    ]

    watch = [
        item
        for item in candidates
        if (
            item.get("status")
            == "WATCH"
            and any(
                hint in str(
                    item.get("domain")
                    or ""
                ).lower()

                for hint
                in WATCH_DOMAIN_HINTS
            )
        )
    ]

    def key(item):
        return (
            -int(
                item.get("score")
                or 0
            ),
            str(
                item.get("domain")
                or ""
            ),
        )

    verify.sort(key=key)
    watch.sort(key=key)

    selected = []

    seen = set()

    for item in verify + watch:

        domain = str(
            item.get("domain")
            or ""
        ).lower()

        if domain in seen:
            continue

        seen.add(domain)
        selected.append(item)

        if len(selected) >= MAX_CANDIDATES:
            break

    return selected


def probe_candidate(
    candidate: dict[str, Any],
) -> dict[str, Any]:

    domain = str(
        candidate["domain"]
    ).lower()

    pages = []

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=4
    ) as pool:

        future_map = {
            pool.submit(
                fetch_one,
                domain,
                path,
            ):
            path

            for path in PATHS
        }

        for future in concurrent.futures.as_completed(
            future_map
        ):

            result = future.result()

            pages.append(
                result
            )

    pages.sort(
        key=lambda item:
        item.get("url", "")
    )

    successful = [
        page
        for page in pages
        if page.get("status")
        == "PASS"
    ]

    body_text = "\n".join(
        page.get("text", "")
        for page in successful
    )

    ev = evidence(
        body_text
    )

    terms = matched_terms(
        body_text
    )

    buyer_role = bool(
        ev.get(
            "publisher_program"
        )
        or ev.get(
            "active_demand"
        )
    )

    positive_count = sum(
        bool(
            ev.get(key)
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

    corroborated = (
        buyer_role
        and positive_count >= 2
        and not ev.get(
            "negative_program"
        )
    )

    snippets = []

    for page in successful:

        text = page.get(
            "text",
            ""
        )

        page_terms = matched_terms(
            text
        )

        actual = sorted(
            {
                term
                for values
                in page_terms.values()
                for term in values
            }
        )

        if not actual:
            continue

        low = text.lower()

        starts = []

        for term in actual:

            pos = low.find(
                term
            )

            if pos >= 0:
                starts.append(
                    max(
                        0,
                        pos - 180,
                    )
                )

        for start in sorted(
            set(starts)
        )[:3]:

            snippets.append(
                {
                    "url":
                        page.get(
                            "final_url"
                        )
                        or page.get(
                            "url"
                        ),

                    "text":
                        text[
                            start:
                            start + 800
                        ],

                    "matched_terms":
                        actual,
                }
            )

    return {
        "domain":
            domain,

        "queue_status":
            candidate.get(
                "status"
            ),

        "queue_score":
            candidate.get(
                "score"
            ),

        "verticals_detected":
            verticals(
                body_text
            ),

        "pages_attempted":
            len(pages),

        "pages_successful":
            len(successful),

        "pages":
            [
                {
                    key: value
                    for key, value
                    in page.items()
                    if key != "text"
                }

                for page in pages
            ],

        "evidence":
            ev,

        "matched_terms":
            terms,

        "buyer_role":
            buyer_role,

        "positive_category_count":
            positive_count,

        "corroborated":
            corroborated,

        "snippets":
            snippets[:12],
    }


def write_json(
    path: Path,
    value: Any,
) -> None:

    tmp = path.with_suffix(
        ".tmp"
    )

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


def merge_results(
    results: list[dict[str, Any]],
) -> None:

    discovery = json.loads(
        DISCOVERY.read_text()
    )

    verification = json.loads(
        VERIFICATION.read_text()
    )

    # Remove older direct-site active runs.
    runs = [
        run

        for run in discovery.get(
            "runs",
            [],
        )

        if run.get(
            "verification_source"
        )
        != "direct-site"
    ]

    for item in results:

        if not item.get(
            "corroborated"
        ):
            continue

        snippets = item.get(
            "snippets",
            [],
        )

        actual_text = "\n".join(
            snippet.get(
                "text",
                ""
            )

            for snippet
            in snippets
        )

        if not actual_text:
            continue

        runs.append(
            {
                "status":
                    "PASS",

                "vertical":
                    (
                        item.get(
                            "verticals_detected"
                        )
                        or ["home_services"]
                    )[0],

                "query":
                    "buyer-network-active-verification",

                "verification_source":
                    "direct-site",

                "domains":
                    [
                        item["domain"]
                    ],

                # IMPORTANT:
                # Only actual retrieved site text is
                # provided to the queue scorer.
                "stdout_tail":
                    actual_text[
                        -20_000:
                    ],

                "stderr_tail":
                    "",
            }
        )

    discovery[
        "runs"
    ] = runs

    discovery[
        "candidate_domains"
    ] = sorted(
        {
            str(domain).lower()

            for run in runs

            for domain in (
                run.get("domains")
                or []
            )

            if valid_domain(
                str(domain)
            )
        }
    )

    discovery[
        "candidate_domain_count"
    ] = len(
        discovery[
            "candidate_domains"
        ]
    )

    existing = {
        str(
            item.get("domain")
            or ""
        ).lower():
            item

        for item
        in verification.get(
            "verifications",
            [],
        )

        if valid_domain(
            str(
                item.get("domain")
                or ""
            )
        )
    }

    for item in results:

        if not item.get(
            "corroborated"
        ):
            continue

        existing[
            item["domain"]
        ] = {
            "domain":
                item["domain"],

            "vertical":
                (
                    item.get(
                        "verticals_detected"
                    )
                    or ["home_services"]
                )[0],

            "evidence":
                item["evidence"],

            "evidence_text":
                "\n".join(
                    snippet.get(
                        "text",
                        ""
                    )

                    for snippet
                    in item.get(
                        "snippets",
                        []
                    )
                )[
                    -20_000:
                ],

            "queries":
                [
                    {
                        "query":
                            "direct-site-public-pages",

                        "attempts":
                            item.get(
                                "pages",
                                []
                            ),
                    }
                ],

            "verification_source":
                "direct-site",

            "verified_at":
                now_iso(),
        }

    verification[
        "verifications"
    ] = list(
        existing.values()
    )

    verification[
        "candidate_count"
    ] = len(
        verification[
            "verifications"
        ]
    )

    verification[
        "verified_run_count"
    ] = sum(
        1
        for item
        in verification[
            "verifications"
        ]
        if (
            item.get(
                "evidence",
                {}
            ).get(
                "publisher_program"
            )
            or item.get(
                "evidence",
                {}
            ).get(
                "active_demand"
            )
        )
    )

    write_json(
        DISCOVERY,
        discovery,
    )

    write_json(
        VERIFICATION,
        verification,
    )


def cached_results() -> (
    list[dict[str, Any]]
    | None
):

    if not DIRECT.exists():
        return None

    try:
        data = json.loads(
            DIRECT.read_text()
        )

    except Exception:
        return None

    generated = data.get(
        "generated_epoch"
    )

    if not isinstance(
        generated,
        (int, float),
    ):
        return None

    if (
        time.time()
        - generated
        > CACHE_SECONDS
    ):
        return None

    return data.get(
        "results",
        [],
    )


def main() -> int:

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--force",
        action="store_true",
    )

    args = parser.parse_args()

    cached = (
        None
        if args.force
        else cached_results()
    )

    if cached is not None:

        merge_results(
            cached
        )

        print(
            json.dumps(
                {
                    "status":
                        "PASS_CACHED",

                    "result_count":
                        len(cached),

                    "corroborated":
                        [
                            item[
                                "domain"
                            ]
                            for item
                            in cached
                            if item.get(
                                "corroborated"
                            )
                        ],

                    "authority":
                        "OBSERVE",
                },
                indent=2,
            )
        )

        return 0

    backlog = json.loads(
        BACKLOG.read_text()
    )

    candidates = select_candidates(
        backlog
    )

    results = []

    # Domains run concurrently, while each
    # candidate internally bounds page concurrency.
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=MAX_WORKERS
    ) as pool:

        futures = {
            pool.submit(
                probe_candidate,
                candidate,
            ):
            candidate

            for candidate
            in candidates
        }

        for future in concurrent.futures.as_completed(
            futures
        ):

            candidate = futures[
                future
            ]

            try:
                result = future.result()

            except Exception as exc:
                result = {
                    "domain":
                        candidate[
                            "domain"
                        ],

                    "queue_status":
                        candidate.get(
                            "status"
                        ),

                    "queue_score":
                        candidate.get(
                            "score"
                        ),

                    "corroborated":
                        False,

                    "error":
                        (
                            f"{type(exc).__name__}:"
                            f"{str(exc)[:500]}"
                        ),
                }

            results.append(
                result
            )

    results.sort(
        key=lambda item:
        str(
            item.get(
                "domain"
            )
        )
    )

    direct_payload = {
        "schema_version":
            "buyer-direct-site-verification-v1",

        "generated_at":
            now_iso(),

        "generated_epoch":
            time.time(),

        "authority":
            "OBSERVE",

        "candidate_count":
            len(candidates),

        "results":
            results,

        "governance": {
            "outbound":
                False,

            "forms":
                False,

            "logins":
                False,

            "db_write":
                False,

            "traffic_activation":
                False,

            "commercial_terms":
                False,

            "funds":
                False,
        },
    }

    write_json(
        DIRECT,
        direct_payload,
    )

    merge_results(
        results
    )

    print(
        json.dumps(
            {
                "status":
                    "PASS",

                "candidate_count":
                    len(candidates),

                "candidates":
                    [
                        item.get(
                            "domain"
                        )
                        for item
                        in candidates
                    ],

                "corroborated_count":
                    sum(
                        bool(
                            item.get(
                                "corroborated"
                            )
                        )
                        for item
                        in results
                    ),

                "corroborated_domains":
                    [
                        item[
                            "domain"
                        ]
                        for item
                        in results
                        if item.get(
                            "corroborated"
                        )
                    ],

                "results":
                    [
                        {
                            "domain":
                                item.get(
                                    "domain"
                                ),

                            "pages_successful":
                                item.get(
                                    "pages_successful"
                                ),

                            "evidence":
                                item.get(
                                    "evidence"
                                ),

                            "corroborated":
                                item.get(
                                    "corroborated"
                                ),
                        }

                        for item
                        in results
                    ],

                "authority":
                    "OBSERVE",
            },
            indent=2,
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
