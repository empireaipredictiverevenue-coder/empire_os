from __future__ import annotations

import argparse
import concurrent.futures
import html
import ipaddress
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

from empire_os.buyer_public_research_seed import publisher_review_page_paths
from empire_os.buyer_network_research_rotation import (
    accepted_domain, choose_research_batch, make_research_summary,
    retain_recent_results, RESULT_TTL_SECONDS,
)


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

LEDGER = BASE / "research_ledger_latest.json"
PROGRESS = BASE / "research_progress_latest.json"
BRAIN = BASE / "team_brain_latest.json"
EFFECTIVENESS = BASE / "scout_effectiveness_latest.json"

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
    "us", "ca", "au", "biz", "info", "pro", "media",
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
        "pay per lead",
        "pay-per-lead",
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
        "pay per accepted lead",
        "paid per accepted lead",
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

    if domain in BLOCKED or not accepted_domain(domain):
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


def public_dns_only(domain: str) -> bool:
    """Never research hosts resolving to Empire internal/private networks."""
    if not valid_domain(domain):
        return False
    try:
        addresses = socket.getaddrinfo(
            domain, 443, type=socket.SOCK_STREAM,
        )
    except (socket.gaierror, OSError):
        return False
    return bool(addresses) and all(
        ipaddress.ip_address(address[4][0]).is_global
        for address in addresses
    )


class SiteOnlyRedirect(urllib.request.HTTPRedirectHandler):
    def __init__(self, requested_domain: str):
        super().__init__()
        self.requested_domain = requested_domain

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urllib.parse.urlsplit(newurl)
        host = (parsed.hostname or "").lower()
        if (
            parsed.scheme not in ("http", "https")
            or not same_domain(self.requested_domain, newurl)
            or not public_dns_only(host)
        ):
            return None
        return super().redirect_request(
            req, fp, code, msg, headers, newurl,
        )


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

            opener = urllib.request.build_opener(
                urllib.request.HTTPSHandler(context=context),
                SiteOnlyRedirect(domain),
            )
            with opener.open(request, timeout=TIMEOUT) as response:

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
    ledger: dict[str, Any] | None = None,
    *,
    now_epoch: float | None = None,
    priority_hints: dict[str, int] | None = None,
    evidence_yield_penalties: dict[str, int] | None = None,
) -> list[dict[str, Any]]:
    clean = {
        **backlog,
        "candidates": [
            item for item in backlog.get("candidates", [])
            if isinstance(item, dict)
            and valid_domain(str(item.get("domain") or ""))
        ],
    }
    selected, _ = choose_research_batch(
        clean, ledger, now_epoch=now_epoch or time.time(),
        limit=MAX_CANDIDATES,
        priority_hints=priority_hints,
        evidence_yield_penalties=evidence_yield_penalties,
    )
    return selected


def read_existing_team_brain_hints(*, now_epoch: float) -> dict[str, int]:
    """Optional hints from the ORIGINAL team. Never grant probe eligibility."""
    try:
        if (BRAIN.is_symlink() or not BRAIN.is_file()
                or not 100 <= BRAIN.stat().st_size <= 500_000):
            return {}
        data = json.loads(BRAIN.read_text())
        at = datetime.fromisoformat(str(data.get("generated_at", "")))
        hints = data.get("research_priority_hints")
        if (at.utcoffset() is None
                or not 0 <= now_epoch - at.timestamp() <= 3 * 3600
                or data.get("schema_version") != "empire.buyer_acquisition.decision_brain.v1"
                or data.get("mode") != "OBSERVE"
                or data.get("outbound_authorized") is not False
                or data.get("external_execution_performed") is not False
                or data.get("database_writes") is not False
                or data.get("research_priority_hints_are_not_research_authority") is not True
                or not isinstance(hints, dict) or len(hints) > 500):
            return {}
        if any(not valid_domain(domain) or type(score) is not int
               or not 0 <= score <= 150 for domain, score in hints.items()):
            return {}
        return hints
    except (OSError, TypeError, ValueError, OverflowError):
        return {}


def read_original_scout_yield_penalties(*, now_epoch: float) -> dict[str, int]:
    """Read bounded advisory reductions; never admit a candidate or bypass a cooldown."""
    try:
        if (EFFECTIVENESS.is_symlink() or not EFFECTIVENESS.is_file()
                or not 100 <= EFFECTIVENESS.stat().st_size <= 500_000):
            return {}
        data = json.loads(EFFECTIVENESS.read_text())
        at = datetime.fromisoformat(str(data.get("generated_at", "")))
        penalties = data.get("research_deprioritization_hints")
        if (at.utcoffset() is None
                or not 0 <= now_epoch - at.timestamp() <= 3 * 3600
                or data.get("schema_version") != "empire.buyer_scout.effectiveness.v1"
                or data.get("status") != "MEASURED"
                or data.get("mode") != "OBSERVE"
                or data.get("outbound_sent") is not False
                or data.get("database_writes") is not False
                or data.get("payment_authorized") is not False
                or data.get("penalties_are_advisory_not_eligibility") is not True
                or not isinstance(penalties, dict) or len(penalties) > 500):
            return {}
        if any(not valid_domain(domain) or type(value) is not int
               or not 0 <= value <= 60 for domain, value in penalties.items()):
            return {}
        return penalties
    except (OSError, ValueError, TypeError, OverflowError):
        return {}


def read_ledger_and_results() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    try:
        previous = json.loads(DIRECT.read_text())
    except (FileNotFoundError, ValueError, OSError):
        previous = {}
    prior = previous.get("results") or []
    epoch = previous.get("generated_epoch")
    try:
        ledger = json.loads(LEDGER.read_text())
    except (FileNotFoundError, ValueError, OSError):
        ledger = {"schema_version": "empire.buyer_network_research_ledger.v1",
                  "mode": "OBSERVE", "domains": {}}
    ledger.setdefault("domains", {})
    # Seed the durable rotation history from the legacy, already-fetched
    # direct-site batch without reclassifying those results as new evidence.
    if isinstance(epoch, (int, float)) and 0 < time.time() - epoch < RESULT_TTL_SECONDS:
        for item in prior:
            domain = str(item.get("domain") or "").lower()
            if not valid_domain(domain):
                continue
            item.setdefault("observed_epoch", epoch)
            ledger["domains"].setdefault(domain, {
                "last_attempt_epoch": epoch,
                "status": "LEGACY_OBSERVED",
            })
    return ledger, prior


def probe_candidate(
    candidate: dict[str, Any],
) -> dict[str, Any]:

    domain = str(
        candidate["domain"]
    ).lower()

    if not public_dns_only(domain):
        return {
            "domain": domain,
            "queue_status": candidate.get("status"),
            "pages_attempted": 0, "pages_successful": 0,
            "corroborated": False, "evidence": {},
            "status": "NON_PUBLIC_OR_UNRESOLVABLE_DOMAIN",
            "snippets": [],
        }
    pages = []
    # At most two reviewed SAME-HOST publisher pages (Polyares PPL + PPC).
    # No global path expansion or additional research timer.
    extra = publisher_review_page_paths(domain)
    probe_paths = PATHS + tuple(path for path in extra if path not in PATHS)

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

            for path in probe_paths
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

        "publisher_formats_advertised_not_approved": [
            product for product, terms in (
                ("PAY_PER_LEAD", ("pay per lead", "pay-per-lead")),
                ("PAY_PER_CALL", ("pay per call", "pay-per-call")),
            ) if any(term in body_text.lower() for term in terms)
        ],

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
                item.get("observed_at") or now_iso(),
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
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--plan-only", action="store_true")
    args = parser.parse_args()

    backlog = json.loads(BACKLOG.read_text())
    ledger, prior = read_ledger_and_results()
    timestamp = time.time()
    if args.force:
        # Explicit manual retry, not an automated infinite retry loop.
        ledger = {**ledger, "domains": {}}
    hints = read_existing_team_brain_hints(now_epoch=timestamp)
    penalties = read_original_scout_yield_penalties(now_epoch=timestamp)
    candidates = select_candidates(backlog, ledger, now_epoch=timestamp,
                                   priority_hints=hints,
                                   evidence_yield_penalties=penalties)
    selected_domains = [item["domain"] for item in candidates]
    if args.plan_only:
        print(json.dumps({
            "status": "PLAN_ONLY",
            "mode": "OBSERVE",
            "selected_domains": selected_domains,
            "batch_size": len(candidates),
            "queue_count": backlog.get("backlog_count"),
            "execution_authority": "NONE",
            "network_probes_performed": 0,
            "files_written": 0,
        }, indent=2))
        return 0

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(probe_candidate, item): item for item in candidates}
        for future in concurrent.futures.as_completed(futures):
            candidate = futures[future]
            try:
                result = future.result()
            except Exception as exc:
                result = {
                    "domain": candidate["domain"],
                    "queue_status": candidate.get("status"),
                    "corroborated": False,
                    "error": type(exc).__name__,
                }
            result["observed_epoch"] = timestamp
            result["observed_at"] = datetime.fromtimestamp(
                timestamp, tz=timezone.utc
            ).isoformat()
            results.append(result)
    for item in results:
        ledger["domains"][item["domain"]] = {
            "last_attempt_epoch": timestamp,
            "status": "CORROBORATED_FIRST_PARTY" if item.get("corroborated")
            else "EVIDENCE_INSUFFICIENT",
        }
    recent = retain_recent_results(prior, results, now_epoch=timestamp)
    ledger["mode"] = "OBSERVE"
    ledger["updated_at"] = now_iso()
    direct = {
        "schema_version": "buyer-direct-site-verification-v1",
        "generated_at": now_iso(),
        "generated_epoch": timestamp,
        "authority": "OBSERVE",
        "candidate_count": len(candidates),
        "observed_domain_count": len(recent),
        "results": recent,
        "governance": {
            "outbound": False, "forms": False, "logins": False,
            "db_write": False, "traffic_activation": False,
            "commercial_terms": False, "funds": False,
        },
    }
    progress = make_research_summary(backlog, ledger, recent)
    progress["latest_batch_domains"] = selected_domains
    progress["latest_batch_count"] = len(results)
    progress["invalid_or_placeholder_skipped"] = sum(
        1 for item in backlog.get("candidates", [])
        if isinstance(item, dict) and not valid_domain(
            str(item.get("domain") or "")
        )
    )
    # State is persisted only after a bounded fetch; no outbound, terms or DB.
    write_json(DIRECT, direct)
    write_json(LEDGER, ledger)
    write_json(PROGRESS, progress)
    if recent:
        merge_results(recent)
    print(json.dumps({
        "status": "PASS" if candidates else "NO_NEW_DUE_CANDIDATES",
        "mode": "OBSERVE", "selected_domains": selected_domains,
        "latest_batch_count": len(results),
        "recent_evidence_count": len(recent),
        "verify_attempted_count": progress["verify_attempted_count"],
        "watch_attempted_count": progress["watch_attempted_count"],
        "outstanding_verify_count": progress["outstanding_verify_count"],
        "outstanding_watch_count": progress["outstanding_watch_count"],
        "execution_authority": "NONE",
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
