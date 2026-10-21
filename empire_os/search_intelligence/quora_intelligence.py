"""Quora question intelligence adapter for the EXISTING Search Intelligence engine.

Consumes owner-reviewed topics and optionally bounded Search Fabric candidates.
It never scrapes Quora, posts answers, claims Quora demand, treats third-party
visits as owned SEO, or authorises buyer calls, backlinks or revenue.
"""
from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import re
from typing import Any, Mapping, Sequence
from urllib.parse import urlsplit, urlunsplit

from .semantic_opportunity_review import review_semantic_opportunity

ROOT = Path(__file__).resolve().parents[2]
QUEUE = ROOT / "docs/seo/LEAD_SMART_QUORA_ANSWER_REVIEW_QUEUE_20261021.csv"
EXPANSION_QUEUE = ROOT / "docs/seo/EMPIRE_QUORA_MULTINICHE_TOPIC_RESEARCH_20261021.csv"
VERTICAL_PREFIXES = {"QROOF": "roofing", "QHVAC": "hvac", "QSOLA": "solar", "QDENT": "dental", "QLEGL": "legal", "QBUSI": "b2b"}
SPECIALIST_VERTICALS = {"dental", "legal"}
SCHEMA = "empire.search_intelligence.quora_research.v1"
MAX_ROWS = 64
MAX_RESULTS = 96
FRESH_AGE = timedelta(days=7)
CSV_COLUMNS = (
    "item_id", "question_theme", "topic", "seo_page",
    "seo_page_public_verified", "actual_quora_question_url",
    "quora_account_verified", "answer_status", "owner_review",
    "link_approved", "geography_caveat",
)


class QuoraEvidenceError(ValueError):
    pass


def canonical_question_url(url: Any) -> str:
    """Only plain public Quora question URLs, never profiles or redirects."""
    if not isinstance(url, str) or len(url) > 300 or url != url.strip():
        raise QuoraEvidenceError("INVALID_QUORA_QUESTION_URL")
    try:
        p = urlsplit(url)
        host = (p.hostname or "").lower()
        path = p.path.rstrip("/")
        if (p.scheme != "https" or host not in {"www.quora.com", "quora.com"}
                or p.username is not None or p.password is not None
                or p.port is not None or p.query or p.fragment
                or not re.fullmatch(r"/[A-Za-z0-9][A-Za-z0-9_-]{5,180}", path)
                or path.lower().startswith(("/profile", "/topic", "/spaces", "/search"))):
            raise ValueError("not a plain Quora question URL")
    except ValueError:
        raise QuoraEvidenceError("INVALID_QUORA_QUESTION_URL") from None
    return urlunsplit(("https", "www.quora.com", path, "", ""))


def read_topic_queue(path: Path = QUEUE) -> tuple[dict[str, str], ...]:
    # Keep the original eight buyer-reviewed roofing topics byte-for-byte;
    # append the cross-sector expansion only for the canonical queue.
    paths = (path, EXPANSION_QUEUE) if path == QUEUE else (path,)
    rows: list[dict[str, str]] = []
    for selected in paths:
        if (selected.is_symlink() or not selected.is_file()
                or selected.stat().st_size > 32000):
            raise QuoraEvidenceError("QUORA_TOPIC_QUEUE_UNAVAILABLE")
        with selected.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if tuple(reader.fieldnames or ()) != CSV_COLUMNS:
                raise QuoraEvidenceError("QUORA_TOPIC_SCHEMA_DRIFT")
            rows.extend(reader)
    if not 1 <= len(rows) <= MAX_ROWS:
        raise QuoraEvidenceError("QUORA_TOPIC_COUNT_INVALID")
    ids = set()
    unique_themes = set()
    for row in rows:
        topic_id, theme, page = (
            row.get("item_id"), row.get("question_theme"), row.get("seo_page"),
        )
        if (not isinstance(topic_id, str)
                or not re.fullmatch(r"Q[A-Z0-9]{5,18}", topic_id)
                or topic_id in ids
                or not any(topic_id.startswith(prefix) for prefix in VERTICAL_PREFIXES)
                or not isinstance(theme, str) or theme.casefold().strip() in unique_themes
                or not 15 <= len(theme) <= 240 or not theme.strip()
                or not isinstance(page, str)
                or not re.fullmatch(r"/[a-z0-9/-]{3,150}", page)
                or not row.get("topic") or not row.get("geography_caveat")
                or row.get("answer_status") != "RESEARCH_ONLY"
                or row.get("owner_review") != "REQUIRED"
                or row.get("seo_page_public_verified") != "false"
                or row.get("quora_account_verified") != "false"
                or row.get("link_approved") != "false"
                or row.get("actual_quora_question_url") != ""
                or None in row):
            raise QuoraEvidenceError("UNAPPROVED_OR_DUPLICATE_QUORA_TOPIC")
        ids.add(topic_id)
        unique_themes.add(theme.casefold().strip())
    return tuple(rows)


def _timestamp(value: Any, now: datetime) -> datetime:
    if not isinstance(value, str):
        raise QuoraEvidenceError("INVALID_SEARCH_OBSERVATION_TIME")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise QuoraEvidenceError("INVALID_SEARCH_OBSERVATION_TIME") from None
    if parsed.tzinfo is None:
        raise QuoraEvidenceError("INVALID_SEARCH_OBSERVATION_TIME")
    parsed = parsed.astimezone(timezone.utc)
    if parsed > now or now - parsed > timedelta(days=365):
        raise QuoraEvidenceError("INVALID_SEARCH_OBSERVATION_TIME")
    return parsed


def review_quora_research(
    observations: Sequence[Mapping[str, Any]] = (),
    *,
    path: Path = QUEUE,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Review Search Fabric candidate links without elevating search snippets.

    An observation is a separately supplied, provenance-labelled search result;
    it is NOT evidence that its Quora page exists, or that anyone wants a quote.
    """
    clock = now or datetime.now(timezone.utc)
    if clock.tzinfo is None:
        raise QuoraEvidenceError("AWARE_REVIEW_CLOCK_REQUIRED")
    clock = clock.astimezone(timezone.utc)
    seeds = read_topic_queue(path)
    ids = {r["item_id"]: r for r in seeds}
    if not isinstance(observations, (list, tuple)) or len(observations) > MAX_RESULTS:
        raise QuoraEvidenceError("UNBOUNDED_QUORA_SEARCH_CANDIDATES")
    candidates = []
    seen = set()
    for row in observations:
        if not isinstance(row, Mapping):
            raise QuoraEvidenceError("UNTRUSTED_QUORA_SEARCH_ROW")
        if set(row) != {
            "seed_id", "question_url", "question_title", "source_ref",
            "source_query", "observed_at", "provider",
        }:
            raise QuoraEvidenceError("UNTRUSTED_QUORA_SEARCH_ROW")
        seed_id = row["seed_id"]
        if seed_id not in ids or row["provider"] != "search_fabric":
            raise QuoraEvidenceError("INVALID_QUORA_SEARCH_PROVENANCE")
        title = row["question_title"]
        ref = row["source_ref"]
        if (not isinstance(title, str) or not 12 <= len(title) <= 240
                or not isinstance(ref, str)
                or not re.fullmatch(r"search-fabric:[a-zA-Z0-9:_-]{12,150}", ref)):
            raise QuoraEvidenceError("INVALID_QUORA_SEARCH_PROVENANCE")
        query = 'site:quora.com "' + ids[seed_id]["question_theme"] + '"'
        if row["source_query"] != query:
            raise QuoraEvidenceError("SOURCE_QUERY_MISMATCH")
        url = canonical_question_url(row["question_url"])
        if url in seen:
            raise QuoraEvidenceError("DUPLICATE_QUORA_CANDIDATE")
        seen.add(url)
        observed = _timestamp(row["observed_at"], clock)
        # Semantic sector/intent judgement is a text-only research hypothesis.
        signal = review_semantic_opportunity(
            title, source_kind="EXTERNAL_PUBLIC_TITLE", evidence_refs=[ref]
        )
        candidates.append({
            "seed_id": seed_id,
            "vertical": next(v for prefix, v in VERTICAL_PREFIXES.items()
                             if seed_id.startswith(prefix)),
            "question_url_candidate": url,
            "question_title_candidate": title,
            "source_ref": ref,
            "observed_at": observed.isoformat(),
            "source_status": (
                "FRESH_SEARCH_FABRIC_CANDIDATE" if clock - observed <= FRESH_AGE
                else "STALE_SEARCH_FABRIC_CANDIDATE"
            ),
            "intent_hypothesis": signal["intent_label"],
            "sector_hypothesis": signal["sector_review"]["status"],
            "quora_origin_page_verified": False,
            "author_or_customer_verified": False,
            "buyer_qualification_verified": False,
            "posting_authorized": False,
        })
    topics = []
    for row in seeds:
        theme = row["question_theme"]
        signal = review_semantic_opportunity(
            theme, source_kind="PAGE_TITLE_UNMEASURED"
        )
        vertical = next(v for prefix, v in VERTICAL_PREFIXES.items()
                        if row["item_id"].startswith(prefix))
        topics.append({
            "item_id": row["item_id"],
            "vertical": vertical,
            "specialist_editorial_review_required": vertical in SPECIALIST_VERTICALS,
            "question_theme": theme,
            "topic": row["topic"],
            "proposed_owned_page": row["seo_page"],
            "source_query_plan": 'site:quora.com "' + theme + '"',
            "proposed_page_public_verified": False,
            "editorial_review_required": True,
            "intent_hypothesis": signal["intent_label"],
            "sector_hypothesis": signal["sector_review"]["status"],
            "answer_publication_state": "RESEARCH_ONLY",
        })
    fresh_count = sum(x["source_status"] == "FRESH_SEARCH_FABRIC_CANDIDATE"
                      for x in candidates)
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "existing_search_fabric": "SOURCE_CANDIDATES_ONLY",
        "original_topic_digest": "sha256:" + sha256(
            path.read_bytes()
        ).hexdigest(),
        "expansion_topic_digest": (
            "sha256:" + sha256(EXPANSION_QUEUE.read_bytes()).hexdigest()
            if path == QUEUE else None
        ),
        "vertical_topic_counts": {
            vertical: sum(t["vertical"] == vertical for t in topics)
            for vertical in VERTICAL_PREFIXES.values()
        },
        "topic_count": len(topics),
        "topics": topics,
        "source_candidates_count": len(candidates),
        "fresh_source_candidate_count": fresh_count,
        "candidate_questions": candidates,
        "verified_quora_questions": 0,
        "published_answers_verified": 0,
        "owned_seo_sessions_verified": 0,
        "third_party_visits_first_party": False,
        "affiliate_links_authorized": False,
        "automated_posting_authorized": False,
        "owner_editorial_signoff_verified": False,
        "organic_buyer_enquiries_verified": False,
        "buyer_accepted_calls_verified": False,
        "realized_revenue_verified": False,
        "external_requests_performed": False,
        "production_writes": False,
        "execution_authority": "NONE",
    }


def review_quora_serp_snapshot(
    seed_id: str, snapshot: Any, *,
    path: Path = QUEUE, now: datetime | None = None,
) -> dict[str, Any]:
    """Adapt the canonical SearchFabricSerpAdapter snapshot, never fetch Quora.

    A cached or provider-failed snapshot is held, not re-dated as fresh.
    Source digests identify observation bytes; hashes are NOT site authority.
    """
    from .serp import SerpSnapshot
    import json

    clock = now or datetime.now(timezone.utc)
    if clock.tzinfo is None:
        raise QuoraEvidenceError("AWARE_REVIEW_CLOCK_REQUIRED")
    topics = {r["item_id"]: r for r in read_topic_queue(path)}
    if seed_id not in topics or not isinstance(snapshot, SerpSnapshot):
        raise QuoraEvidenceError("INVALID_SEARCH_FABRIC_SNAPSHOT")
    expected = 'site:quora.com "' + topics[seed_id]["question_theme"] + '"'
    if snapshot.query != expected:
        raise QuoraEvidenceError("SOURCE_QUERY_MISMATCH")
    empty = review_quora_research(path=path, now=clock)
    if (snapshot.available is not True or snapshot.cache is not False
            or snapshot.error or snapshot.engine in ("none", "")
            or not 1 <= len(snapshot.results) <= 20):
        return {
            **empty,
            "search_fabric_snapshot_state": "HELD_OR_UNVERIFIED_SOURCE",
            "search_fabric_snapshot_candidate_verified": False,
        }
    observed = _timestamp(snapshot.observed_at, clock.astimezone(timezone.utc))
    converted = []
    for result in snapshot.results:
        if (result.engine != snapshot.engine
                or "search_fabric" not in result.provenance
                or "cache:false" not in result.provenance
                or f"engine:{snapshot.engine}" not in result.provenance
                or type(result.position) is not int or result.position < 1):
            raise QuoraEvidenceError("INVALID_SEARCH_FABRIC_SNAPSHOT_PROVENANCE")
        try:
            url = canonical_question_url(result.url)
        except QuoraEvidenceError:
            continue  # Other search domains and Quora profile URLs are not questions.
        # Hash the actual returned row, not a made-up independent Quora receipt.
        evidence_bytes = json.dumps({
            "seed": seed_id, "engine": snapshot.engine,
            "query": snapshot.query, "url": url,
            "title": result.title, "position": result.position,
            "observed_at": observed.isoformat(),
        }, sort_keys=True).encode("utf-8")
        converted.append({
            "seed_id": seed_id, "question_url": url,
            "question_title": result.title,
            "source_ref": "search-fabric:" + sha256(evidence_bytes).hexdigest(),
            "source_query": expected, "observed_at": observed.isoformat(),
            "provider": "search_fabric",
        })
    result = review_quora_research(converted, path=path, now=clock)
    return {
        **result,
        "search_fabric_snapshot_state": (
            "CANDIDATE_RESULTS_OBSERVED" if converted
            else "NO_QUORA_QUESTION_RESULTS_IN_RETURNED_SAMPLE"
        ),
        "search_fabric_snapshot_candidate_verified": False,
        "snapshot_provider_reported": snapshot.engine,
        "snapshot_google_ranking_verified": False,
    }
