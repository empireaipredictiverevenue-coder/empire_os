"""Empire-native Search Product crawl audit.

Consumes the stable Search Fabric site_probe output and turns it into
SEO/product findings. It performs no publishing, indexing, database writes,
forms, authentication bypass or commercial mutation.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Callable, Mapping, Sequence

from empire_os.search_fabric.site_probe import probe_site


@dataclass(frozen=True)
class CrawlFinding:
    code: str
    severity: str
    scope: str
    message: str
    url: str | None = None
    evidence: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _clean(value: Any) -> str:
    return str(value or "").strip()


def audit_probe_result(probe: Mapping[str, Any]) -> dict[str, Any]:
    if probe.get("ok") is not True:
        return {
            "available": False,
            "reason": _clean(probe.get("error")) or "crawl_unavailable",
            "pages_observed": 0,
            "findings": [
                CrawlFinding(
                    code="crawl_unavailable",
                    severity="critical",
                    scope="site",
                    message="The site could not be observed by the Empire crawler.",
                    url=_clean(probe.get("requested_url")) or None,
                ).as_dict()
            ],
            "limitations": [
                "bounded_observe_only_crawl",
                "not_a_full_search_engine_index",
            ],
        }

    findings: list[CrawlFinding] = []
    pages = [
        row
        for row in (probe.get("pages_checked") or [])
        if isinstance(row, Mapping)
    ]
    site_url = _clean(probe.get("final_url")) or _clean(
        probe.get("requested_url")
    )

    if not _clean(probe.get("title")):
        findings.append(CrawlFinding(
            code="site_title_missing",
            severity="high",
            scope="site",
            message="No usable site title was observed.",
            url=site_url or None,
        ))

    if not _clean(probe.get("description")):
        findings.append(CrawlFinding(
            code="meta_description_missing",
            severity="medium",
            scope="site",
            message="No usable meta description was observed.",
            url=site_url or None,
        ))

    if not _clean(probe.get("canonical_url")):
        findings.append(CrawlFinding(
            code="site_canonical_missing",
            severity="medium",
            scope="site",
            message="No canonical URL was observed on the primary page.",
            url=site_url or None,
        ))

    schema_types = [
        _clean(value)
        for value in (probe.get("schema_types") or [])
        if _clean(value)
    ]
    if not schema_types:
        findings.append(CrawlFinding(
            code="structured_data_not_observed",
            severity="low",
            scope="site",
            message="No structured-data types were observed in the bounded crawl.",
            url=site_url or None,
        ))

    titles: dict[str, list[str]] = {}
    for row in pages:
        url = _clean(row.get("url"))
        title = _clean(row.get("title"))
        canonical = _clean(row.get("canonical_url"))

        if not title:
            findings.append(CrawlFinding(
                code="page_title_missing",
                severity="high",
                scope="page",
                message="Observed page has no usable title.",
                url=url or None,
            ))
        else:
            titles.setdefault(title.casefold(), []).append(url)

        if not canonical:
            findings.append(CrawlFinding(
                code="page_canonical_missing",
                severity="medium",
                scope="page",
                message="Observed page has no canonical URL.",
                url=url or None,
            ))

    for urls in titles.values():
        clean_urls = tuple(url for url in urls if url)
        if len(clean_urls) > 1:
            findings.append(CrawlFinding(
                code="duplicate_page_title",
                severity="medium",
                scope="site",
                message="Multiple observed pages share the same title.",
                evidence=clean_urls,
            ))

    if probe.get("budget_exhausted") is True:
        findings.append(CrawlFinding(
            code="crawl_budget_exhausted",
            severity="info",
            scope="crawl",
            message=(
                "The bounded crawl hit its time budget; additional pages may exist."
            ),
            url=site_url or None,
        ))

    local_entity_signals = {
        "business_name_observed": bool(probe.get("business_names")),
        "phone_observed": bool(probe.get("phones")),
        "address_observed": bool(probe.get("addresses")),
        "structured_data_observed": bool(schema_types),
    }

    severity_order = {
        "critical": 0,
        "high": 1,
        "medium": 2,
        "low": 3,
        "info": 4,
    }
    findings.sort(
        key=lambda item: (
            severity_order.get(item.severity, 9),
            item.code,
            item.url or "",
        )
    )

    return {
        "available": True,
        "mode": "OBSERVE",
        "execution_allowed": False,
        "pages_observed": len(pages),
        "domain": _clean(probe.get("domain")) or None,
        "final_url": site_url or None,
        "site_title": _clean(probe.get("title")) or None,
        "site_description_observed": bool(_clean(probe.get("description"))),
        "canonical_observed": bool(_clean(probe.get("canonical_url"))),
        "schema_types": schema_types,
        "local_entity_signals": local_entity_signals,
        "evidence_score": probe.get("evidence_score"),
        "finding_count": len(findings),
        "findings": [item.as_dict() for item in findings],
        "limitations": [
            "bounded_observe_only_crawl",
            "not_a_full_search_engine_index",
            "no_rank_or_traffic_metrics_invented",
        ],
    }


ProbeFn = Callable[..., Mapping[str, Any]]


def crawl_search_site(
    url: str,
    *,
    max_pages: int = 6,
    request_timeout: float = 8.0,
    time_budget_seconds: float = 30.0,
    probe: ProbeFn = probe_site,
) -> dict[str, Any]:
    target = _clean(url)
    if not target:
        raise ValueError("url required")

    bounded_pages = max(1, min(int(max_pages), 12))
    bounded_timeout = max(1.0, min(float(request_timeout), 30.0))
    bounded_budget = max(
        bounded_timeout,
        min(float(time_budget_seconds), 120.0),
    )

    observed = probe(
        target,
        max_pages=bounded_pages,
        request_timeout=bounded_timeout,
        time_budget_seconds=bounded_budget,
        page_priority="default",
    )
    audit = audit_probe_result(observed)
    return {
        "schema_version": "empire.search.crawl.v1",
        "source": "empire_web_intelligence_crawler",
        "mode": "OBSERVE",
        "execution_allowed": False,
        "publishing_execution": False,
        "indexation_execution": False,
        "requested_url": target,
        "limits": {
            "max_pages": bounded_pages,
            "request_timeout_seconds": bounded_timeout,
            "time_budget_seconds": bounded_budget,
        },
        "audit": audit,
    }
