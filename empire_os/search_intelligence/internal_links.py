"""Pure internal-link analysis for Search Intelligence."""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from typing import Any, Iterable, Mapping
from urllib.parse import urlsplit


@dataclass(frozen=True)
class InternalLinkFinding:
    kind: str
    page_url: str
    severity: str
    evidence: Mapping[str, Any]
    recommendation: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _page_url(page: Mapping[str, Any]) -> str:
    return str(page.get("canonical_url") or page.get("url") or "").strip()


def _same_site(source: str, target: str) -> bool:
    a, b = urlsplit(source), urlsplit(target)
    return bool(a.netloc and b.netloc and a.netloc.lower() == b.netloc.lower())


def analyze_internal_links(
    pages: Iterable[Mapping[str, Any]],
    links: Iterable[Mapping[str, Any]],
    *,
    excessive_outgoing_threshold: int = 100,
    weak_cluster_min_related_links: int = 1,
    anchor_concentration_min_links: int = 5,
    anchor_concentration_ratio: float = 0.8,
) -> list[InternalLinkFinding]:
    page_rows = [dict(p) for p in pages]
    link_rows = [dict(l) for l in links]
    urls = {_page_url(p) for p in page_rows if _page_url(p)}
    inbound: Counter[str] = Counter()
    outgoing: Counter[str] = Counter()
    related: Counter[str] = Counter()
    anchors_by_target: dict[str, list[str]] = defaultdict(list)
    findings: list[InternalLinkFinding] = []

    page_by_url = {_page_url(p): p for p in page_rows if _page_url(p)}

    for link in link_rows:
        source = str(link.get("source_url") or "").strip()
        target = str(link.get("target_url") or "").strip()
        if not source or not target:
            continue
        outgoing[source] += 1
        if target in urls:
            inbound[target] += 1
            anchor = str(link.get("anchor_text") or "").strip().lower()
            if anchor:
                anchors_by_target[target].append(anchor)
            a, b = page_by_url.get(source, {}), page_by_url.get(target, {})
            same_topic = (
                a.get("topic") is not None
                and b.get("topic") is not None
                and str(a.get("topic")).strip().lower()
                == str(b.get("topic")).strip().lower()
            )
            shared_entities = set(a.get("entity_references") or ()) & set(
                b.get("entity_references") or ()
            )
            if same_topic or shared_entities:
                related[source] += 1
        elif _same_site(source, target):
            findings.append(InternalLinkFinding(
                "broken_internal_target",
                source,
                "high",
                {"target_url": target},
                "repair_or_remove_broken_internal_link",
            ))

    for url, page in page_by_url.items():
        if inbound[url] == 0:
            findings.append(InternalLinkFinding(
                "orphan_page",
                url,
                "medium",
                {"inbound_links": 0},
                "add_contextual_internal_link_from_relevant_page",
            ))
        if outgoing[url] > excessive_outgoing_threshold:
            findings.append(InternalLinkFinding(
                "excessive_internal_links",
                url,
                "medium",
                {"outgoing_links": outgoing[url]},
                "review_and_reduce_low_value_internal_links",
            ))
        if page.get("topic") and related[url] < weak_cluster_min_related_links:
            findings.append(InternalLinkFinding(
                "weak_topic_cluster",
                url,
                "low",
                {
                    "topic": page.get("topic"),
                    "observed_related_links": related[url],
                },
                "add_contextual_links_within_observed_topic_cluster",
            ))

    for target, anchors in anchors_by_target.items():
        if len(anchors) < anchor_concentration_min_links:
            continue
        counts = Counter(anchors)
        anchor, count = counts.most_common(1)[0]
        ratio = count / len(anchors)
        if ratio >= anchor_concentration_ratio:
            findings.append(InternalLinkFinding(
                "anchor_over_concentration",
                target,
                "low",
                {
                    "anchor_text": anchor,
                    "ratio": round(ratio, 4),
                    "observed_links": len(anchors),
                },
                "diversify_contextual_anchor_text_where_natural",
            ))

    return findings
