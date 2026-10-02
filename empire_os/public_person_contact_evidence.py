"""Bounded exact-person public contact evidence collection.

This module observes public evidence only. It never guesses an email and never
grants outreach authority.
"""
from __future__ import annotations

from typing import Any, Callable, Mapping
from urllib.parse import urlparse

from empire_os.buyer_discovery import classify_decision_role, looks_like_person_name
from empire_os.search_fabric.search import search
from empire_os.search_fabric.site_probe import probe_site


_DIRECTORY_HOSTS = {
    "bbb.org",
    "buildzoom.com",
    "chamberofcommerce.com",
    "angi.com",
    "homeadvisor.com",
    "houzz.com",
    "avvo.com",
    "justia.com",
    "lawyers.com",
}


def _text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _host(value: Any) -> str:
    text = _text(value).lower()
    if not text:
        return ""
    if "://" not in text:
        text = "https://" + text
    try:
        return (urlparse(text).hostname or "").removeprefix("www.")
    except ValueError:
        return ""


def _email_domain(value: Any) -> str:
    email = _text(value).lower()
    if "@" not in email:
        return ""
    return email.rsplit("@", 1)[-1].removeprefix("www.")


def _same_person(left: Any, right: Any) -> bool:
    return _text(left).casefold() == _text(right).casefold()


def _source_kind(url: str, company_domain: str) -> str | None:
    host = _host(url)
    if not host:
        return None
    if host == company_domain:
        return "official_site"
    if host.endswith(".gov"):
        return "public_government_record"
    if any(
        host == domain or host.endswith("." + domain)
        for domain in _DIRECTORY_HOSTS
    ):
        return "public_business_directory"
    return None


def _search_once(
    search_fn: Callable[..., Mapping[str, Any]],
    query: str,
    *,
    num: int,
) -> list[dict[str, Any]]:
    for engine in ("bing_rss", "bing_html"):
        try:
            payload = search_fn(
                query,
                num=num,
                engine=engine,
                use_cache=True,
            )
        except TypeError:
            payload = search_fn(query, num)
        except Exception:
            payload = {}
        organic = payload.get("organic") if isinstance(payload, Mapping) else None
        rows = [
            dict(row)
            for row in (organic or [])
            if isinstance(row, Mapping)
        ]
        if rows:
            return rows
    return []


def collect_public_person_contact_evidence(
    *,
    business_name: str,
    website: str,
    person_name: str,
    person_title: str,
    search_fn: Callable[..., Mapping[str, Any]] = search,
    probe_fn: Callable[..., Mapping[str, Any]] = probe_site,
    max_queries: int = 4,
    max_results_per_query: int = 6,
    max_pages_total: int = 6,
) -> dict[str, Any]:
    """Collect explicit exact-person email evidence from bounded public sources."""
    business = _text(business_name)
    website = _text(website)
    name = _text(person_name)
    title = _text(person_title)
    company_domain = _host(website)
    role, role_score = classify_decision_role(title)

    base = {
        "schema_version": "empire.public-person-contact-evidence.v1",
        "attempted": False,
        "business_name": business,
        "company_domain": company_domain,
        "person_name": name,
        "person_title": title,
        "decision_role": role,
        "decision_score": role_score,
        "queries": [],
        "pages_inspected": 0,
        "evidence": [],
        "execution_authority": "none",
        "outbound_authorized": False,
        "database_write_performed": False,
    }
    if (
        not business
        or not company_domain
        or not looks_like_person_name(name)
        or role_score < 0.5
    ):
        return base

    queries = [
        f'site:{company_domain} "{name}" email',
        f'site:{company_domain} "{name}" contact',
        f'"{name}" "{business}" email',
        f'"{name}" "{business}" contact',
    ][: max(1, min(int(max_queries), 4))]
    base["attempted"] = True
    base["queries"] = list(queries)

    candidates: list[tuple[str, str]] = []
    seen_urls: set[str] = set()
    page_cap = max(1, min(int(max_pages_total), 8))
    for query in queries:
        rows = _search_once(
            search_fn,
            query,
            num=max(1, min(int(max_results_per_query), 8)),
        )
        for row in rows:
            url = _text(row.get("link") or row.get("url"))
            kind = _source_kind(url, company_domain)
            if not url or kind is None or url in seen_urls:
                continue
            seen_urls.add(url)
            candidates.append((url, kind))
            if len(candidates) >= page_cap:
                break
        if len(candidates) >= page_cap:
            break

    accepted: list[dict[str, Any]] = []
    for url, kind in candidates:
        try:
            probe = probe_fn(
                url,
                max_pages=2,
                request_timeout=3.0,
                time_budget_seconds=8.0,
                page_priority="people",
                public_only=True,
            )
        except Exception:
            continue
        base["pages_inspected"] += 1
        if not isinstance(probe, Mapping) or probe.get("ok") is not True:
            continue

        for raw in probe.get("people") or []:
            if not isinstance(raw, Mapping):
                continue
            if not _same_person(raw.get("name"), name):
                continue
            email = _text(raw.get("email")).lower()
            if not email or _email_domain(email) != company_domain:
                continue
            observed_title = _text(raw.get("title"))
            observed_role, observed_score = classify_decision_role(
                observed_title or title
            )
            if observed_score < 0.5:
                continue

            accepted.append({
                "name": name,
                "title": observed_title or title,
                "email": email,
                "source_url": (
                    _text(raw.get("url") or raw.get("evidence_url"))
                    or url
                ),
                "source_kind": kind,
                "role_corroborated": True,
                "direct_publication": True,
                "business_identity_correlated": True,
                "decision_role": observed_role,
                "decision_score": observed_score,
            })

    deduped: dict[tuple[str, str], dict[str, Any]] = {}
    for row in accepted:
        deduped[(row["name"].casefold(), row["email"].casefold())] = row
    base["evidence"] = list(deduped.values())
    return base
