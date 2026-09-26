"""OBSERVE-only executor for competitor account research actions.

Consumes the canonical competitor-audience runtime snapshot and executes bounded
public web research through Empire Search Fabric. Search results are observations
only: they are not buyer intent, commercial intent, verified outcomes, prospects,
or outreach authority.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.parse import urlparse

from empire_os.competitor_audience_sweep import fetch_public_html
from empire_os.search_fabric.search import search as search_web


SNAPSHOT_RELATIVE_PATH = Path(
    "runtime/competitive_intelligence/competitor_account_research_latest.json"
)


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _domain(value: Any) -> str:
    text = _clean(value).lower()
    if not text:
        return ""
    if "://" not in text:
        text = "https://" + text
    host = (urlparse(text).hostname or "").lower().rstrip(".")
    return host.removeprefix("www.")


def _slug_words(value: Any) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", _clean(value).lower()))


SearchFn = Callable[..., Mapping[str, Any]]
FetchFn = Callable[[str], str | None]


_GENERIC_COMPANY_TOKENS = {
    "inc", "llc", "ltd", "limited", "corp", "corporation",
    "company", "co", "plc",
}


def _company_name_tokens(value: Any) -> tuple[str, ...]:
    return tuple(
        token
        for token in re.findall(r"[a-z0-9]+", _clean(value).lower())
        if len(token) > 1 and token not in _GENERIC_COMPANY_TOKENS
    )


def _result_matches_company(
    raw: Mapping[str, Any],
    *,
    company_name: str,
    company_domain: str,
) -> bool:
    url = _clean(raw.get("link") or raw.get("url"))
    if company_domain and _domain(url) == company_domain:
        return True

    haystack = _slug_words(
        " ".join(
            (
                _clean(raw.get("title")),
                _clean(raw.get("snippet")),
                url,
            )
        )
    )
    if not haystack:
        return False

    exact_name = _slug_words(company_name)
    if exact_name and exact_name in haystack:
        return True

    tokens = _company_name_tokens(company_name)
    if len(tokens) >= 2 and all(token in haystack.split() for token in tokens):
        return True

    return False


def _html_mentions_company(html: str, company_name: str) -> bool:
    text = _slug_words(re.sub(r"<[^>]+>", " ", html))
    exact_name = _slug_words(company_name)
    if exact_name and exact_name in text:
        return True

    tokens = _company_name_tokens(company_name)
    words = set(text.split())
    return len(tokens) >= 2 and all(token in words for token in tokens)


def build_account_research_queries(
    company: Mapping[str, Any],
    context: Mapping[str, Any],
) -> list[str]:
    name = _clean(company.get("company_name") or context.get("company_name"))
    domain = _domain(company.get("company_website"))
    action = _clean(context.get("next_best_research_action"))
    competitors = [
        _clean(value)
        for value in company.get("competitors", [])
        if _clean(value)
    ]

    if not name:
        return []

    queries = [f'"{name}"']

    if action == "deep_account_research":
        queries.extend([
            f'"{name}" services',
            f'"{name}" reviews',
            f'"{name}" jobs hiring',
            f'"{name}" partners customers',
            f'"{name}" comparison alternatives',
        ])
    elif action == "collect_additional_public_evidence":
        queries.extend([
            f'"{name}" comparison',
            f'"{name}" best roofing companies',
            f'"{name}" reviews',
        ])

    if domain:
        queries.append(f'"{domain}"')

    for competitor in competitors[:3]:
        queries.append(f'"{name}" "{competitor}"')

    return list(dict.fromkeys(query for query in queries if query.strip()))[:10]


def execute_account_research(
    company: Mapping[str, Any],
    context: Mapping[str, Any],
    *,
    search_fn: SearchFn = search_web,
    fetch_fn: FetchFn = fetch_public_html,
    max_results_per_query: int = 5,
) -> dict[str, Any]:
    entity_id = _clean(company.get("entity_id") or context.get("entity_id"))
    company_name = _clean(
        company.get("company_name") or context.get("company_name")
    )
    company_domain = _domain(company.get("company_website"))
    action = _clean(context.get("next_best_research_action"))

    evidence_refs = {
        _clean(item.get("source_ref"))
        for item in company.get("evidence", [])
        if isinstance(item, Mapping) and _clean(item.get("source_ref"))
    }

    queries = build_account_research_queries(company, context)
    observations: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    rejected_irrelevant_count = 0

    # First-party retrieval is direct and bounded. Search engines are not
    # trusted to establish company identity for the official domain.
    if company_domain:
        first_party_url = f"https://{company_domain}/"
        html = fetch_fn(first_party_url)
        if html:
            seen_urls.add(first_party_url)
            observations.append({
                "query": None,
                "engine": None,
                "position": None,
                "title": company_name,
                "snippet": "",
                "url": first_party_url,
                "domain": company_domain,
                "relevance_score": None,
                "first_party_domain_match": True,
                "existing_evidence_source": False,
                "observation_type": "public_first_party_page",
                "verified_fact": False,
            })

    # Re-observe known evidence pages directly. They remain observations here;
    # the canonical evidence layer owns fact verification.
    for item in company.get("evidence", []) or []:
        if not isinstance(item, Mapping):
            continue
        evidence_url = _clean(item.get("source_ref"))
        if not evidence_url or evidence_url in seen_urls:
            continue
        html = fetch_fn(evidence_url)
        if not html or not _html_mentions_company(html, company_name):
            continue

        seen_urls.add(evidence_url)
        observations.append({
            "query": None,
            "engine": None,
            "position": None,
            "title": _clean(item.get("summary")) or company_name,
            "snippet": "",
            "url": evidence_url,
            "domain": _domain(evidence_url) or None,
            "relevance_score": None,
            "first_party_domain_match": False,
            "existing_evidence_source": True,
            "observation_type": "reobserved_public_evidence",
            "verified_fact": False,
        })

    for query in queries:
        result = search_fn(
            query,
            num=max(1, min(int(max_results_per_query), 10)),
        )
        if not isinstance(result, Mapping):
            continue

        params = result.get("searchParameters")
        engine = (
            _clean(params.get("engine"))
            if isinstance(params, Mapping)
            else ""
        )

        for raw in result.get("organic", []) or []:
            if not isinstance(raw, Mapping):
                continue

            url = _clean(raw.get("link") or raw.get("url"))
            if not url or url in seen_urls:
                continue

            if not _result_matches_company(
                raw,
                company_name=company_name,
                company_domain=company_domain,
            ):
                rejected_irrelevant_count += 1
                continue

            seen_urls.add(url)

            result_domain = _domain(url)
            first_party = bool(
                company_domain and result_domain == company_domain
            )
            observations.append({
                "query": query,
                "engine": engine or None,
                "position": raw.get("position"),
                "title": _clean(raw.get("title")),
                "snippet": _clean(raw.get("snippet")),
                "url": url,
                "domain": result_domain or None,
                "relevance_score": raw.get("relevance_score"),
                "first_party_domain_match": first_party,
                "existing_evidence_source": url in evidence_refs,
                "observation_type": "public_search_result",
                "verified_fact": False,
            })

    first_party_count = sum(
        1 for row in observations if row["first_party_domain_match"]
    )
    evidence_reobserved_count = sum(
        1 for row in observations if row["existing_evidence_source"]
    )
    third_party_count = len(observations) - first_party_count

    if not observations:
        next_step = "search_retrieval_retry"
    elif action == "deep_account_research" and (
        first_party_count > 0 and third_party_count >= 2
    ):
        next_step = "account_research_brief_ready_for_review"
    elif action == "collect_additional_public_evidence" and third_party_count > 0:
        next_step = "review_additional_public_evidence_candidates"
    else:
        next_step = "continue_public_research"

    return {
        "schema_version": "empire.competitor_account_research.v1",
        "mode": "OBSERVE",
        "entity_id": entity_id,
        "company_name": company_name,
        "company_domain": company_domain or None,
        "research_rank": context.get("research_rank"),
        "research_priority": (
            context.get("features", {}).get("research_priority")
            if isinstance(context.get("features"), Mapping)
            else None
        ),
        "requested_action": action or None,
        "planned_query_count": len(queries),
        "executed_query_count": len(queries),
        "observation_count": len(observations),
        "first_party_observation_count": first_party_count,
        "third_party_observation_count": third_party_count,
        "existing_evidence_source_reobserved_count": (
            evidence_reobserved_count
        ),
        "irrelevant_search_result_rejected_count": (
            rejected_irrelevant_count
        ),
        "next_step": next_step,
        "observations": observations,
        "observations_are_verified_facts": False,
        "buyer_intent": False,
        "commercial_intent": False,
        "prospect_created": False,
        "outreach_enabled": False,
        "score_persistence_authorized": False,
        "outcome_update_authorized": False,
        "execution_authority": "none",
    }


def execute_snapshot_research(
    snapshot: Mapping[str, Any],
    *,
    search_fn: SearchFn = search_web,
    fetch_fn: FetchFn = fetch_public_html,
) -> dict[str, Any]:
    companies = {
        _clean(row.get("entity_id")): row
        for row in snapshot.get("companies", [])
        if isinstance(row, Mapping) and _clean(row.get("entity_id"))
    }

    actions = []
    for context in snapshot.get("omega_cortex_context", []) or []:
        if not isinstance(context, Mapping):
            continue
        entity_id = _clean(context.get("entity_id"))
        company = companies.get(entity_id)
        if company is None:
            continue
        actions.append(
            execute_account_research(
                company,
                context,
                search_fn=search_fn,
                fetch_fn=fetch_fn,
            )
        )

    actions.sort(
        key=lambda row: (
            int(row.get("research_rank") or 999999),
            row.get("company_name") or "",
        )
    )

    return {
        "schema_version": "empire.competitor_account_research_batch.v1",
        "mode": "OBSERVE",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "company_count": len(actions),
        "observation_count": sum(
            int(row.get("observation_count") or 0) for row in actions
        ),
        "brief_ready_count": sum(
            1 for row in actions
            if row.get("next_step") == (
                "account_research_brief_ready_for_review"
            )
        ),
        "additional_evidence_review_count": sum(
            1 for row in actions
            if row.get("next_step") == (
                "review_additional_public_evidence_candidates"
            )
        ),
        "buyer_intent_inferred": False,
        "commercial_intent_inferred": False,
        "outreach_enabled": False,
        "execution_authority": "none",
        "actions": actions,
    }


def write_account_research_snapshot(
    repo_root: Path,
    payload: Mapping[str, Any],
) -> Path:
    path = repo_root / SNAPSHOT_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)
    return path


def build_account_research_runtime(repo_root: Path) -> dict[str, Any]:
    path = repo_root / SNAPSHOT_RELATIVE_PATH
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "available": False,
            "schema_version": "empire.competitor_account_research_batch.v1",
            "mode": "OBSERVE",
            "company_count": 0,
            "observation_count": 0,
            "buyer_intent_inferred": False,
            "commercial_intent_inferred": False,
            "outreach_enabled": False,
            "execution_authority": "none",
        }
    return {"available": True, **payload}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Execute bounded competitor account research actions"
    )
    parser.add_argument(
        "--repo-root",
        default=os.getenv("EMPIRE_REPO_ROOT", "/srv/empire_os"),
    )
    parser.add_argument(
        "--run",
        action="store_true",
        help="Execute public research from the current competitor snapshot.",
    )
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()

    if not args.run:
        print(json.dumps(
            build_account_research_runtime(repo_root),
            indent=2,
            sort_keys=True,
            default=str,
        ))
        return 0

    source_path = (
        repo_root
        / "runtime/competitive_intelligence/"
        / "competitor_audience_latest.json"
    )
    source = json.loads(source_path.read_text(encoding="utf-8"))
    payload = execute_snapshot_research(source)
    write_account_research_snapshot(repo_root, payload)
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
