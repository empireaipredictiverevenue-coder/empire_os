"""Bounded multi-pass public deep-research intake for EmpireOS.

Original EmpireOS implementation informed by architectural review of:
* odysseus-dev/odysseus (AGPL-3.0-or-later; NO code copied)
* Alibaba-NLP/DeepResearch (Apache-2.0; NO code copied)
All injected search, document inspection, planning and model adapters remain
outside this module. Nothing executes automatically on import.
"""
from __future__ import annotations

from dataclasses import dataclass
import ipaddress
import re
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urlsplit, urlunsplit


@dataclass(frozen=True)
class ResearchLimits:
    max_queries: int = 6
    max_rounds: int = 2
    results_per_query: int = 4
    max_pages: int = 10

    def bounded(self) -> "ResearchLimits":
        return ResearchLimits(
            max_queries=max(1, min(int(self.max_queries), 8)),
            max_rounds=max(1, min(int(self.max_rounds), 3)),
            results_per_query=max(1, min(int(self.results_per_query), 5)),
            max_pages=max(1, min(int(self.max_pages), 12)),
        )


def _text(value: Any, size: int = 240) -> str:
    return " ".join(str(value or "").split())[:size]


def _public_url(raw: Any) -> str | None:
    """Syntax-only public URL guard; the injected fetcher MUST enforce DNS/IP SSRF."""
    url = _text(raw, 2048)
    try:
        parsed = urlsplit(url)
        host = (parsed.hostname or "").lower().rstrip(".")
        if parsed.scheme.lower() not in {"http", "https"} or not host:
            return None
        if parsed.username or parsed.password or not parsed.netloc:
            return None
        if parsed.port is not None and parsed.port not in {80, 443}:
            return None
        if host in {"localhost", "localhost.localdomain"} or host.endswith(
            (".localhost", ".local", ".internal", ".invalid", ".test", ".example")
        ):
            return None
        if "." not in host:
            return None
        try:
            addr = ipaddress.ip_address(host.strip("[]"))
        except ValueError:
            pass
        else:
            if not addr.is_global:
                return None
        return urlunsplit((
            parsed.scheme.lower(), parsed.netloc.lower(), parsed.path or "/",
            parsed.query, "",
        ))
    except (ValueError, TypeError):
        return None


def _seed_queries(question: str) -> list[str]:
    return [
        question,
        f"{question} official documents primary sources",
        f"{question} independent evidence limitations counterexamples",
    ]


def _query(value: Any) -> str:
    return _text(value, 260)


def _safe_result_rows(payload: Any) -> list[Mapping[str, Any]]:
    if not isinstance(payload, Mapping):
        return []
    rows = payload.get("organic")
    if not isinstance(rows, list):
        return []
    return [r for r in rows if isinstance(r, Mapping)]


def run_research(
    question: str,
    *,
    search_fn: Callable[..., Mapping[str, Any]],
    inspect_fn: Callable[[str], Mapping[str, Any]],
    limits: ResearchLimits = ResearchLimits(),
    initial_queries: Sequence[str] | None = None,
    follow_up_fn: Callable[[str, list[dict[str, Any]], list[str]], Sequence[str]] | None = None,
    synthesize_fn: Callable[[str, list[dict[str, Any]]], Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return traceable research observations; never authorize commercial actions.

    Search uses Empire's existing "organic" result contract. An inspected page
    proves only that a response was examined; it does NOT verify claims or intent.
    Search adapters are responsible for network and throttling policy. Document
    readers MUST enforce DNS resolution, redirect and content-size safeguards.
    Synthesis must return {"claims":[{"claim":str,"source_ids":["S1"]}]}.
    Unsupported or uninspected-source claims are rejected.
    """
    q = _text(question, 700)
    if not q:
        raise ValueError("research question is required")
    bounded = limits.bounded()
    proposed = initial_queries if initial_queries is not None else _seed_queries(q)
    queue: list[tuple[str, int]] = []
    enqueued: set[str] = set()

    def enqueue(raw: Any, round_index: int) -> None:
        item = _query(raw)
        if not item or item.lower() in enqueued or round_index >= bounded.max_rounds:
            return
        if len(queue) + len(enqueued) >= 3 * bounded.max_queries:
            return
        enqueued.add(item.lower())
        queue.append((item, round_index))

    for item in list(proposed)[:bounded.max_queries]:
        enqueue(item, 0)

    searches: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    visited: set[str] = set()
    followup_rounds: set[int] = set()
    page_count = 0
    while queue and len(searches) < bounded.max_queries:
        term, depth = queue.pop(0)
        record: dict[str, Any] = {"query": term, "round": depth + 1, "result_count": 0}
        try:
            payload = search_fn(term, num=bounded.results_per_query)
            rows = _safe_result_rows(payload)
            record["result_count"] = len(rows)
            if isinstance(payload, Mapping) and payload.get("error"):
                record["provider_state"] = "DEGRADED"
            else:
                record["provider_state"] = "OBSERVED"
        except Exception as exc:
            rows = []
            record["provider_state"] = "ERROR"
            record["error_type"] = type(exc).__name__
        searches.append(record)

        for row in rows[:bounded.results_per_query]:
            if page_count >= bounded.max_pages:
                break
            url = _public_url(row.get("link") or row.get("url"))
            if not url or url in visited:
                continue
            visited.add(url)
            page_count += 1
            entry: dict[str, Any] = {
                "source_id": f"S{len(sources) + 1}",
                "url": url,
                "title": _text(row.get("title"), 300),
                "snippet": _text(row.get("snippet"), 700),
                "discovery_query": term,
                "source_lane": _text(row.get("source_lane"), 25),
                "discovery_engine": _text(row.get("discovery_engine"), 50),
                "observation_type": "public_search_result",
                "claim_accuracy_verified": False,
                "original_page_inspected": False,
                "inspection_status": "UNINSPECTED",
            }
            try:
                inspected = inspect_fn(url)
                if isinstance(inspected, Mapping):
                    status = _text(inspected.get("status"), 90)
                    entry["inspection_status"] = status or "UNINSPECTED"
                    if status == "ORIGINAL_HTML_HEADINGS_INSPECTED":
                        entry["original_page_inspected"] = True
                        entry["content_sha256"] = _text(inspected.get("content_sha256"), 64)
                        entry["document_headings"] = [
                            _text(h, 180)
                            for h in (inspected.get("document_headings") or [])[:4]
                        ]
                        entry["visible_excerpt"] = _text(inspected.get("visible_excerpt"), 1200)
                        literal_terms = inspected.get("literal_source_terms_observed")
                        entry["literal_source_terms_observed"] = [
                            _text(term, 50) for term in
                            (literal_terms if isinstance(literal_terms, list) else [])[:12]
                            if isinstance(term, str)
                        ]
                        passage_anchors = inspected.get("source_passage_anchors")
                        unanchored_terms = inspected.get(
                            "unanchored_page_terms_require_manual_review"
                        )
                        entry["unanchored_page_terms_require_manual_review"] = [
                            _text(term, 50) for term in (
                                unanchored_terms if isinstance(unanchored_terms, list)
                                else []
                            )[:12] if isinstance(term, str)
                        ]
                        entry["source_passage_anchors"] = [
                            {
                                "term": _text(anchor.get("term"), 50),
                                "original_page_excerpt": _text(
                                    anchor.get("original_page_excerpt"), 165
                                ),
                                "excerpt_sha256": _text(anchor.get("excerpt_sha256"), 64),
                                "support_level": "VERBATIM_PUBLISHER_WORDS_ONLY",
                                "publisher_claim_truth_verified": False,
                                "client_republication_rights_verified": False,
                            }
                            for anchor in (
                                passage_anchors if isinstance(passage_anchors, list)
                                else []
                            )[:8]
                            if isinstance(anchor, Mapping)
                        ]
                else:
                    entry["inspection_status"] = "INVALID_INSPECTOR_RESULT"
            except Exception as exc:
                entry["inspection_status"] = "INSPECTOR_ERROR"
                entry["error_type"] = type(exc).__name__
            sources.append(entry)

        # A model/planner may propose new questions after observing the
        # evidence; proposals remain capped, de-duplicated, and OBSERVE-only.
        if (
            follow_up_fn is not None
            and depth + 1 < bounded.max_rounds
            and depth not in followup_rounds
            and len(searches) < bounded.max_queries
        ):
            followup_rounds.add(depth)
            try:
                followups = follow_up_fn(q, list(sources), [x["query"] for x in searches])
                if isinstance(followups, (list, tuple)):
                    for item in followups[:bounded.max_queries - len(searches)]:
                        enqueue(item, depth + 1)
            except Exception as exc:
                record["followup_error_type"] = type(exc).__name__

    eligible = {s["source_id"] for s in sources if s["original_page_inspected"]}
    claims: list[dict[str, Any]] = []
    rejected_claims = 0
    if synthesize_fn is not None and eligible:
        try:
            response = synthesize_fn(q, [s for s in sources if s["original_page_inspected"]])
            candidate_claims = response.get("claims", []) if isinstance(response, Mapping) else []
            if isinstance(candidate_claims, list):
                for raw in candidate_claims[:20]:
                    if not isinstance(raw, Mapping):
                        rejected_claims += 1
                        continue
                    citation_ids = raw.get("source_ids")
                    ids = list(dict.fromkeys(citation_ids)) if isinstance(citation_ids, list) else []
                    statement = _text(raw.get("claim"), 1000)
                    if statement and ids and all(isinstance(i, str) and i in eligible for i in ids):
                        claims.append({
                            "claim": statement,
                            "source_ids": ids,
                            "factual_accuracy_verified": False,
                        })
                    else:
                        rejected_claims += 1
        except Exception:
            rejected_claims += 1

    status = (
        "DRAFT_WITH_INSPECTED_CITATIONS" if claims
        else "EVIDENCE_READY_FOR_SYNTHESIS" if eligible
        else "INSUFFICIENT_PRIMARY_EVIDENCE"
    )
    return {
        "schema_version": "empire.deep_research.intake.v1",
        "mode": "OBSERVE",
        "question": q,
        "status": status,
        "searches": searches,
        "source_count": len(sources),
        "original_pages_inspected": len(eligible),
        "source_observations": sources,
        "draft_claims": claims,
        "rejected_unsupported_claims": rejected_claims,
        "source_truth": "inspection_is_not_claim_or_commercial_verification",
        "budget": {
            "searches_executed": len(searches),
            "pages_considered": page_count,
            "max_queries": bounded.max_queries,
            "max_pages": bounded.max_pages,
            "max_rounds": bounded.max_rounds,
        },
        "execution_authority": "none",
        "database_write": False,
        "outbound_authorized": False,
        "outbound_sent": False,
        "production_activation": False,
    }
