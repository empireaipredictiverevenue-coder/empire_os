from __future__ import annotations

import asyncio
import importlib
import inspect
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path("/srv/empire_os")

BASE = (
    ROOT
    / "runtime"
    / "buyer_network_intelligence"
)

QUEUE = BASE / "candidate_queue_latest.json"
DISCOVERY = BASE / "discovery_latest.json"
VERIFICATION = BASE / "verification_latest.json"

MAX_CANDIDATES = 20


SAFE_MODULES = (
    "empire_os.search_intelligence.serp",
    "empire_os.search_intelligence.service",
    "empire_os.buyer_public_research_seed",
)


SAFE_NAME_TERMS = (
    "search",
    "discover",
    "research",
    "probe",
    "preview",
    "query",
    "fetch",
)


BLOCKED_NAME_TERMS = (
    "persist",
    "write",
    "save",
    "send",
    "outbound",
    "activate",
    "delete",
    "remove",
    "update",
    "create",
    "migrate",
    "apply",
    "commit",
    "dispatch",
)


SIGNALS = {
    "publisher_program": (
        "publisher program",
        "become a publisher",
        "publishers",
        "affiliate program",
        "traffic partners",
        "media partners",
        "lead partners",
    ),

    "active_demand": (
        "pay per call",
        "pay-per-call",
        "lead buyer",
        "lead buyers",
        "buy leads",
        "live transfer",
        "inbound calls",
        "consumer initiated",
        "consumer-initiated",
    ),

    "integration": (
        "rtb",
        "ping post",
        "ping-post",
        "api",
        "webhook",
        "call tracking",
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

    "contactable": (
        "contact us",
        "apply",
        "sign up",
        "signup",
        "join",
        "get started",
    ),

    "negative_program": (
        "not accepting publishers",
        "not accepting affiliates",
        "publisher program closed",
        "program paused",
        "not accepting traffic",
    ),
}



ALLOWED_TLDS = {
    "com", "co", "uk", "io", "ai", "net", "org",
    "us", "ca", "biz", "info", "pro", "media",
    "marketing", "agency", "digital", "group",
    "company", "services", "solutions",
}

NON_BUYER_DOMAINS = {
    "ahrefs.com",
    "semrush.com",
    "serpapi.com",
    "localfalcon.com",
    "aol.com",
}

def valid_public_buyer_domain(domain: str) -> bool:
    domain = (domain or "").strip().lower().rstrip(".")

    if not domain or "." not in domain:
        return False

    if domain.startswith("empire."):
        return False

    if domain in NON_BUYER_DOMAINS:
        return False

    if domain.endswith((
        ".json",
        ".md",
        ".txt",
        ".py",
        ".yaml",
        ".yml",
        ".sql",
    )):
        return False

    labels = domain.split(".")

    if len(labels) < 2:
        return False

    if labels[-1] not in ALLOWED_TLDS:
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

PARAM_QUERY = {
    "query",
    "q",
    "search_query",
    "search",
    "term",
    "keywords",
}

PARAM_DOMAIN = {
    "domain",
    "host",
    "hostname",
    "site",
}

PARAM_VERTICAL = {
    "vertical",
    "niche",
    "category",
}

PARAM_LIMIT = {
    "limit",
    "max_results",
    "top_k",
    "count",
}


def now_iso() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


def json_text(value: Any) -> str:
    try:
        return json.dumps(
            value,
            default=str,
            ensure_ascii=False,
        )
    except Exception:
        return str(value)


def signal_map(text: str) -> dict[str, bool]:
    low = text.lower()

    return {
        name: any(
            phrase in low
            for phrase in phrases
        )
        for name, phrases
        in SIGNALS.items()
    }


def missing_fields(
    candidate: dict[str, Any],
) -> list[str]:

    evidence = candidate.get(
        "evidence",
        {},
    )

    return [
        name
        for name in (
            "publisher_program",
            "active_demand",
            "integration",
            "economics",
            "compliance",
            "contactable",
        )
        if not evidence.get(name)
    ]


def candidate_priority(
    candidate: dict[str, Any],
) -> tuple[int, int, str]:

    status_weight = {
        "VERIFY_REQUIREMENTS": 0,
        "WATCH": 1,
    }

    return (
        status_weight.get(
            candidate.get("status"),
            9,
        ),
        -int(
            candidate.get("score")
            or 0
        ),
        str(
            candidate.get("domain")
            or ""
        ),
    )


def queries_for(
    candidate: dict[str, Any],
) -> list[str]:

    domain = str(
        candidate["domain"]
    )

    verticals = candidate.get(
        "verticals"
    ) or ["home services"]

    vertical = str(
        verticals[0]
    )

    gaps = missing_fields(
        candidate
    )

    queries = [
        f"site:{domain} publisher program",
        f"site:{domain} {vertical} pay per call leads",
    ]

    if "integration" in gaps:
        queries.append(
            f"site:{domain} API RTB ping post tracking"
        )

    if "economics" in gaps:
        queries.append(
            f"site:{domain} payout revshare revenue share"
        )

    if "compliance" in gaps:
        queries.append(
            f"site:{domain} TCPA consent compliance"
        )

    if "contactable" in gaps:
        queries.append(
            f"site:{domain} publishers apply contact"
        )

    return queries[:6]


def build_kwargs(
    func: Any,
    *,
    query: str,
    domain: str,
    vertical: str,
) -> dict[str, Any] | None:

    try:
        sig = inspect.signature(
            func
        )
    except Exception:
        return None

    kwargs: dict[str, Any] = {}

    for name, parameter in sig.parameters.items():

        if name in ("self", "cls"):
            return None

        if name in PARAM_QUERY:
            kwargs[name] = query
            continue

        if name in PARAM_DOMAIN:
            kwargs[name] = domain
            continue

        if name in PARAM_VERTICAL:
            kwargs[name] = vertical
            continue

        if name in PARAM_LIMIT:
            kwargs[name] = 10
            continue

        if parameter.default is not inspect._empty:
            continue

        if parameter.kind in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ):
            continue

        # Unknown required dependency means
        # we do not call this function.
        return None

    if not any(
        name in kwargs
        for name in PARAM_QUERY
    ):
        return None

    return kwargs


def discover_safe_callables():

    adapters = []

    for module_name in SAFE_MODULES:

        try:
            module = importlib.import_module(
                module_name
            )

        except Exception:
            continue

        for name, value in inspect.getmembers(
            module,
            inspect.isfunction,
        ):

            low = name.lower()

            if not any(
                token in low
                for token in SAFE_NAME_TERMS
            ):
                continue

            if any(
                token in low
                for token in BLOCKED_NAME_TERMS
            ):
                continue

            adapters.append(
                (
                    module_name,
                    name,
                    value,
                )
            )

    return adapters


async def invoke(
    func: Any,
    kwargs: dict[str, Any],
) -> Any:

    value = func(
        **kwargs
    )

    if inspect.isawaitable(
        value
    ):
        value = await value

    return value


async def verify_candidate(
    candidate: dict[str, Any],
    adapters,
):

    domain = str(
        candidate["domain"]
    )

    verticals = candidate.get(
        "verticals"
    ) or ["home_services"]

    vertical = str(
        verticals[0]
    )

    results = []

    combined = []

    for query in queries_for(
        candidate
    ):

        query_result = {
            "query": query,
            "attempts": [],
        }

        for (
            module_name,
            function_name,
            func,
        ) in adapters:

            kwargs = build_kwargs(
                func,
                query=query,
                domain=domain,
                vertical=vertical,
            )

            if kwargs is None:
                continue

            try:
                value = await asyncio.wait_for(
                    invoke(
                        func,
                        kwargs,
                    ),
                    timeout=30,
                )

            except Exception as exc:
                query_result[
                    "attempts"
                ].append(
                    {
                        "adapter":
                            (
                                module_name
                                + "."
                                + function_name
                            ),

                        "status":
                            "ERROR",

                        "error":
                            type(exc).__name__,
                    }
                )
                continue

            text = json_text(
                value
            )

            query_result[
                "attempts"
            ].append(
                {
                    "adapter":
                        (
                            module_name
                            + "."
                            + function_name
                        ),

                    "status":
                        "PASS",

                    "result_preview":
                        text[:2500],
                }
            )

            # Only bind evidence if the returned
            # material actually references target.
            # Never count our own verification query as evidence.
            clean_text = re.sub(
                re.escape(query),
                " ",
                text,
                flags=re.I,
            )

            clean_text = re.sub(
                re.escape(f"site:{domain}"),
                " ",
                clean_text,
                flags=re.I,
            )

            if (
                domain.lower()
                in clean_text.lower()
            ):
                combined.append(
                    clean_text
                )

        results.append(
            query_result
        )

    evidence_text = "\n".join(
        combined
    )

    evidence = signal_map(
        evidence_text
    )

    return {
        "domain":
            domain,

        "vertical":
            vertical,

        "evidence":
            evidence,

        "evidence_text":
            evidence_text[-12000:],

        "queries":
            results,
    }


async def main_async():

    queue = json.loads(
        QUEUE.read_text()
    )

    discovery = json.loads(
        DISCOVERY.read_text()
    )

    adapters = discover_safe_callables()

    candidates = [
        candidate

        for candidate
        in queue.get(
            "candidates",
            [],
        )

        if candidate.get("status")
        in (
            "READY_TO_APPROACH",
            "VERIFY_REQUIREMENTS",
            "WATCH",
        )
        and valid_public_buyer_domain(
            str(candidate.get("domain") or "")
        )
    ]

    candidates.sort(
        key=candidate_priority
    )

    candidates = candidates[
        :MAX_CANDIDATES
    ]

    verifications = []

    new_runs = []

    for candidate in candidates:

        result = await verify_candidate(
            candidate,
            adapters,
        )

        verifications.append(
            result
        )

        evidence = result[
            "evidence"
        ]

        positive_count = sum(
            1
            for name in (
                "publisher_program",
                "active_demand",
                "integration",
                "economics",
                "compliance",
                "contactable",
            )
            if evidence.get(name)
        )

        # Require at least two corroborated
        # buyer-specific evidence categories.
        # API/contact/tooling evidence alone cannot promote.
        if (
            positive_count < 2
            or not (
                evidence.get("publisher_program")
                or evidence.get("active_demand")
            )
        ):
            continue

        domain = result[
            "domain"
        ]

        terms = [
            name
            for name, present
            in evidence.items()
            if present
        ]

        new_runs.append(
            {
                "status":
                    "PASS",

                "vertical":
                    result["vertical"],

                "query":
                    "buyer-network-active-verification",

                "domains":
                    [domain],

                "stdout_tail":
                    (
                        f"{domain} "
                        + " ".join(terms)
                        + " "
                        + result[
                            "evidence_text"
                        ]
                    )[-15000:],

                "stderr_tail":
                    "",

                "verification":
                    evidence,
            }
        )

    existing_runs = discovery.get(
        "runs",
        []
    )

    # Remove older active-verification runs
    # so repeated cycles do not grow forever.
    existing_runs = [
        run
        for run in existing_runs
        if run.get("query")
        != "buyer-network-active-verification"
    ]

    merged_runs = (
        existing_runs
        + new_runs
    )

    clean_runs = []

    for run in merged_runs:

        clean_domains = [
            str(domain).lower()

            for domain in (
                run.get("domains")
                or []
            )

            if valid_public_buyer_domain(
                str(domain)
            )
        ]

        if not clean_domains:
            continue

        clean_run = dict(run)
        clean_run["domains"] = clean_domains

        clean_runs.append(
            clean_run
        )

    discovery["runs"] = clean_runs

    domains = sorted(
        {
            domain

            for run
            in discovery["runs"]

            for domain
            in (
                run.get("domains")
                or []
            )
        }
    )

    discovery[
        "candidate_domains"
    ] = domains

    discovery[
        "candidate_domain_count"
    ] = len(domains)

    discovery[
        "active_verification"
    ] = {
        "generated_at":
            now_iso(),

        "candidate_count":
            len(candidates),

        "verified_run_count":
            len(new_runs),

        "safe_adapter_count":
            len(adapters),

        "authority":
            "OBSERVE",
    }

    tmp = DISCOVERY.with_suffix(
        ".tmp"
    )

    tmp.write_text(
        json.dumps(
            discovery,
            indent=2,
            sort_keys=True,
            default=str,
        )
        + "\n",
        encoding="utf-8",
    )

    tmp.replace(
        DISCOVERY
    )

    VERIFICATION.write_text(
        json.dumps(
            {
                "schema_version":
                    "buyer-network-verification-v1",

                "generated_at":
                    now_iso(),

                "authority":
                    "OBSERVE",

                "safe_adapters": [
                    f"{module}.{name}"
                    for module, name, _
                    in adapters
                ],

                "candidate_count":
                    len(candidates),

                "verified_run_count":
                    len(new_runs),

                "verifications":
                    verifications,

                "governance": {
                    "db_write_authority":
                        False,

                    "outbound_authority":
                        False,

                    "traffic_activation_authority":
                        False,

                    "commercial_terms_authority":
                        False,

                    "funds_authority":
                        False,
                },
            },
            indent=2,
            sort_keys=True,
            default=str,
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "status":
                    "PASS",

                "safe_adapter_count":
                    len(adapters),

                "candidate_count":
                    len(candidates),

                "verified_run_count":
                    len(new_runs),

                "verified_domains": [
                    run["domains"][0]
                    for run
                    in new_runs[:30]
                ],

                "authority":
                    "OBSERVE",
            },
            indent=2,
        )
    )


def main():

    # Explicitly remove execution authority.
    os.environ[
        "EMPIRE_MODE"
    ] = "OBSERVE"

    os.environ[
        "EMPIRE_EXECUTION_AUTHORITY"
    ] = "OBSERVE"

    os.environ[
        "OUTBOUND_ENABLED"
    ] = "0"

    os.environ[
        "EMPIRE_OUTBOUND_ENABLED"
    ] = "0"

    os.environ[
        "LIVE_OUTBOUND"
    ] = "0"

    asyncio.run(
        main_async()
    )


if __name__ == "__main__":
    main()
