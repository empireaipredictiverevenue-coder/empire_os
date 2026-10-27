"""Evidence-first competitor change extraction for the original EmpireOS feed.

Pure offline analysis of HTML already obtained by an authorised, robots-respecting
source reader. NEVER fetches or sends messages, creates CRM leads or infers demand.
"""
from __future__ import annotations

import hashlib
import ipaddress
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any, Mapping
from urllib.parse import urlsplit

SCHEMA = "empire.competitor_change_radar.v1"
MAX_HTML_BYTES = 500_000
MAX_SOURCE_COUNT = 20
MAX_FACTS_PER_CLASS = 8
CATEGORIES = ("pricing", "offers", "features", "announcements")
BLOCKS = {"p", "li", "h1", "h2", "h3", "h4", "td", "section", "article", "div"}
SKIP = {"script", "style", "noscript", "svg", "form", "nav", "footer"}
PATTERNS = {
    "pricing": re.compile(r"(?:[$£€]\s?\d[\d,.]*(?:\s?[/](?:mo|month|yr|year))?|\b(?:USD|GBP|EUR)\s?\d[\d,.]*|\b(?:per month|per year|monthly plan|annual plan|pricing starts|starting at)\b)", re.I),
    "offers": re.compile(r"\b(?:free trial|discount|special offer|money.back guarantee|no credit card|limited.time offer|\d{1,2}% off|free consultation)\b", re.I),
    "features": re.compile(r"\b(?:new feature|integrations?|webhooks?|automated|automation|dashboard|API access|real.time monitoring|launching|now supports)\b", re.I),
    "announcements": re.compile(r"\b(?:changelog|release notes|product update|now available|new launch|announcing|version \d|we launched)\b", re.I),
}
EMAIL = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
PHONE = re.compile(r"(?<!\w)(?:\+?\d[\d\s().-]{8,}\d)(?!\w)")
SPACE = re.compile(r"\s+")


class _PublicText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.parts: list[str] = []
        self.lines: list[str] = []

    def _flush(self) -> None:
        value = SPACE.sub(" ", " ".join(self.parts)).strip()
        if value:
            self.lines.append(value)
        self.parts.clear()

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in SKIP:
            if not self.depth:
                self._flush()
            self.depth += 1
        elif not self.depth and tag in BLOCKS:
            self._flush()

    def handle_endtag(self, tag: str) -> None:
        if tag in SKIP:
            self.depth = max(0, self.depth - 1)
        elif not self.depth and tag in BLOCKS:
            self._flush()

    def handle_data(self, data: str) -> None:
        if not self.depth and data.strip():
            self.parts.append(data)


def _safe_source(source_ref: str) -> bool:
    try:
        u = urlsplit(source_ref)
        host = u.hostname or ""
        if u.scheme != "https" or u.username or u.password or u.port is not None:
            return False
        if not host or len(source_ref) > 400 or u.fragment:
            return False
        if host in {"localhost"} or host.endswith((".local", ".internal", ".test", ".invalid", ".localhost", ".onion")):
            return False
        try:
            addr = ipaddress.ip_address(host)
            return addr.is_global
        except ValueError:
            return "." in host and all(part for part in host.split("."))
    except (TypeError, ValueError, AttributeError):
        return False


def extract_public_facts(html: str) -> dict[str, list[dict[str, str]]]:
    """Return bounded, source-attributable excerpts, not raw pages or contact data."""
    if not isinstance(html, str) or len(html.encode("utf-8")) > MAX_HTML_BYTES:
        raise ValueError("invalid or oversize public HTML")
    parser = _PublicText()
    parser.feed(html)
    parser._flush()
    facts: dict[str, list[dict[str, str]]] = {name: [] for name in CATEGORIES}
    seen: dict[str, set[str]] = {name: set() for name in CATEGORIES}
    for line in parser.lines:
        if EMAIL.search(line) or PHONE.search(line):
            continue
        line = SPACE.sub(" ", line).strip()
        if not 12 <= len(line) <= 200:
            continue
        for category in CATEGORIES:
            if not PATTERNS[category].search(line):
                continue
            normalized = line.casefold()
            fingerprint = hashlib.sha256(normalized.encode()).hexdigest()
            if fingerprint in seen[category] or len(facts[category]) >= MAX_FACTS_PER_CLASS:
                continue
            seen[category].add(fingerprint)
            facts[category].append({"text": line, "digest": fingerprint})
    return facts


def _iso(value: str) -> datetime:
    try:
        when = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, TypeError) as exc:
        raise ValueError("valid timestamp required") from exc
    if when.tzinfo is None:
        raise ValueError("timezone-aware timestamp required")
    return when.astimezone(timezone.utc)


def observe_public_source(row: Mapping[str, Any]) -> dict[str, Any]:
    """Accept only an explicit prior public-source acquisition receipt and HTML."""
    if row.get("fetch_authority") != "PUBLIC_ROBOTS_PERMITTED":
        raise ValueError("robots-permitted prior fetch evidence required")
    source = str(row.get("source_ref") or "")
    if not _safe_source(source):
        raise ValueError("unsafe source reference")
    entity = str(row.get("entity_id") or "").strip()
    if not 1 <= len(entity) <= 120:
        raise ValueError("canonical entity ID required")
    seen_at = _iso(str(row.get("observed_at") or ""))
    facts = extract_public_facts(row.get("html"))
    return {
        "entity_id": entity,
        "company_name": str(row.get("company_name") or "")[:140],
        "source_ref": source,
        "observed_at": seen_at.isoformat(),
        "industry": str(row.get("industry") or "")[:75],
        "territory": str(row.get("territory") or "")[:75],
        "facts": facts,
        "fetch_authority": "PUBLIC_ROBOTS_PERMITTED",
        "baseline_is_not_change": True,
    }


def compare_observations(previous: Mapping[str, Any] | None,
                         current: Mapping[str, Any]) -> dict[str, Any]:
    source = str(current["source_ref"])
    result = {
        "entity_id": current["entity_id"], "source_ref": source,
        "observed_at": current["observed_at"], "status": "BASELINE_ONLY",
        "changes": [], "buyer_intent_inferred": False,
        "revenue_inferred": False, "requires_human_review": False,
    }
    if previous is None:
        return result
    if previous.get("source_ref") != source or previous.get("entity_id") != current["entity_id"]:
        raise ValueError("cross-company/source observation cannot be compared")
    if _iso(str(previous.get("observed_at"))) >= _iso(str(current["observed_at"])):
        raise ValueError("observation clocks must advance")
    if previous.get("fetch_authority") != "PUBLIC_ROBOTS_PERMITTED":
        raise ValueError("untrusted prior observation")
    old = previous.get("facts", {})
    if not isinstance(old, Mapping):
        raise ValueError("invalid prior facts")
    for category in CATEGORIES:
        prior_rows, next_rows = old.get(category, []), current["facts"][category]
        if not isinstance(prior_rows, list):
            raise ValueError("invalid prior fact rows")
        prev = {x["digest"]: x for x in prior_rows if isinstance(x, dict) and "digest" in x}
        nxt = {x["digest"]: x for x in next_rows}
        for key in sorted(nxt.keys() - prev.keys()):
            result["changes"].append({
                "category": category, "change": "ADDED_OR_REWORDED",
                "text": nxt[key]["text"], "digest": key,
            })
        for key in sorted(prev.keys() - nxt.keys()):
            result["changes"].append({
                "category": category, "change": "MISSING_OR_REWORDED",
                "text": str(prev[key].get("text", ""))[:200], "digest": key,
            })
    result["status"] = "REVIEW_REQUIRED" if result["changes"] else "UNCHANGED"
    result["requires_human_review"] = bool(result["changes"])
    return result




def _review_id(entity_id: str, source_ref: str, first_detected_at: str) -> str:
    return hashlib.sha256(
        f"{entity_id}|{source_ref}|{first_detected_at}".encode()
    ).hexdigest()[:24]


def _research_priority(changes: list[Mapping[str, Any]]) -> str:
    return ("PRICING_OR_OFFER_REVIEW" if any(
        item.get("category") in {"pricing", "offers"} for item in changes
    ) else "FEATURE_OR_ANNOUNCEMENT_REVIEW")


def acknowledge_review(
    snapshot: Mapping[str, Any], *, review_id: str,
    reviewer: str, reason: str, now: datetime,
) -> dict[str, Any]:
    """Explicit human resolution; does not create buyer actions or outbound."""
    if (snapshot.get("schema_version") != SCHEMA
            or snapshot.get("mode") != "OBSERVE"
            or snapshot.get("execution_authority") != "none"
            or snapshot.get("outreach_enabled") is not False
            or snapshot.get("payment_authorized") is not False
            or snapshot.get("buyer_intent_inferred") is not False):
        raise ValueError("untrusted radar")
    if (not isinstance(now, datetime) or now.tzinfo is None
            or not re.fullmatch(r"[a-f0-9]{24}", review_id or "")):
        raise ValueError("valid review ID and timezone required")
    if not re.fullmatch(r"[a-zA-Z0-9_.-]{2,60}", reviewer or ""):
        raise ValueError("bounded reviewer ID required")
    reason = str(reason or "").strip()
    if not 8 <= len(reason) <= 500:
        raise ValueError("review resolution explanation required")
    pending = snapshot.get("review_queue", [])
    if not isinstance(pending, list):
        raise ValueError("invalid review queue")
    matching = [item for item in pending if item.get("review_id") == review_id]
    if len(matching) != 1:
        raise ValueError("review item does not exist or is already resolved")
    now_iso = now.astimezone(timezone.utc).isoformat()
    item = matching[0]
    resolved = snapshot.get("resolved_reviews", [])
    if not isinstance(resolved, list) or len(resolved) > 100:
        raise ValueError("invalid resolution history")
    result = dict(snapshot)
    result["review_queue"] = [
        row for row in pending if row.get("review_id") != review_id
    ]
    result["review_candidate_count"] = len(result["review_queue"])
    result["pending_review_count"] = len(result["review_queue"])
    result["resolved_reviews"] = [
        *resolved, {
            "review_id": review_id,
            "entity_id": item["entity_id"],
            "source_ref": item["source_ref"],
            "resolved_at": now_iso,
            "reviewer": reviewer,
            "reason": reason,
            "decision": "REVIEW_CLOSED_NOT_BUYER_CONFIRMED",
        },
    ][-100:]
    result["last_resolution_at"] = now_iso
    return result


def build_radar(rows: list[Mapping[str, Any]], *,
                previous: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Compare bounded snapshots; output review candidates, never leads or revenue."""
    if not isinstance(rows, list) or len(rows) > MAX_SOURCE_COUNT:
        raise ValueError("max 20 public-source observations per bounded batch")
    prior = previous or {}
    if prior and (prior.get("schema_version") != SCHEMA
                  or prior.get("mode") != "OBSERVE"
                  or prior.get("execution_authority") != "none"):
        raise ValueError("untrusted previous radar")
    seen: set[tuple[str, str]] = set()
    prev_index = {
        (row.get("entity_id"), row.get("source_ref")): row
        for row in prior.get("observations", [])
        if isinstance(row, Mapping)
    }
    observations, comparisons = [], []
    for raw in rows:
        fresh = observe_public_source(raw)
        identity = (fresh["entity_id"], fresh["source_ref"])
        if identity in seen:
            raise ValueError("duplicate source observation")
        seen.add(identity)
        observations.append(fresh)
        comparisons.append(compare_observations(prev_index.get(identity), fresh))
    # Retain known earlier baselines for unobserved sources; do not call silence a removal.
    for identity, record in prev_index.items():
        if identity not in seen:
            observations.append(record)
    # A fleeting observation is not a useful operator queue. Preserve earlier
    # unresolved changes through subsequent unchanged / unavailable scans.
    old_queue = prior.get("review_queue", [])
    if not isinstance(old_queue, list) or len(old_queue) > MAX_SOURCE_COUNT:
        raise ValueError("invalid existing review queue")
    pending: dict[tuple[str, str], dict[str, Any]] = {}
    for item in old_queue:
        if not isinstance(item, Mapping):
            raise ValueError("invalid review item")
        key = (str(item.get("entity_id") or ""), str(item.get("source_ref") or ""))
        if (not key[0] or not _safe_source(key[1])
                or item.get("status") not in {"HUMAN_REVIEW_ONLY", "PENDING_REVIEW"}
                or key in pending):
            raise ValueError("untrusted or repeated review item")
        prior_changes = item.get("changes", [])
        if not isinstance(prior_changes, list) or len(prior_changes) > 20:
            raise ValueError("invalid prior change evidence")
        pending[key] = {
            **item, "status": "PENDING_REVIEW",
            "changes": list(prior_changes),
            "review_id": str(item.get("review_id") or _review_id(*key, str(item.get("observed_at")))),
            "first_detected_at": item.get("first_detected_at") or item.get("observed_at"),
            "research_priority": item.get("research_priority") or _research_priority(prior_changes),
        }
    new_review_count = 0
    for cmp in comparisons:
        if not cmp["requires_human_review"]:
            continue
        key = (cmp["entity_id"], cmp["source_ref"])
        existing = pending.get(key)
        if existing is None:
            new_review_count += 1
            existing = {
                "entity_id": key[0], "source_ref": key[1],
                "first_detected_at": cmp["observed_at"],
                "review_id": _review_id(*key, cmp["observed_at"]),
                "changes": [],
            }
        evidence = {}
        for item in [*existing["changes"], *cmp["changes"]]:
            if not isinstance(item, Mapping) or item.get("category") not in CATEGORIES:
                continue
            identity = (item.get("category"), item.get("change"), item.get("digest"))
            evidence[identity] = dict(item)
        combined = list(evidence.values())[-20:]
        existing.update({
            "observed_at": cmp["observed_at"],
            "latest_change_at": cmp["observed_at"],
            "changes": combined,
            "change_count": len(combined),
            "status": "PENDING_REVIEW",
            "research_priority": _research_priority(combined),
        })
        pending[key] = existing
    queue = sorted(pending.values(), key=lambda x: (
        x["research_priority"] != "PRICING_OR_OFFER_REVIEW",
        str(x["first_detected_at"]),
        x["entity_id"],
    ))
    resolved_reviews = prior.get("resolved_reviews", [])
    if not isinstance(resolved_reviews, list) or len(resolved_reviews) > 100:
        raise ValueError("invalid review resolution history")
    return {
        "schema_version": SCHEMA, "mode": "OBSERVE",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "observations": observations, "comparisons": comparisons,
        "observed_this_run": len(rows),
        "new_baselines_this_run": sum(x["status"] == "BASELINE_ONLY" for x in comparisons),
        "unchanged_this_run": sum(x["status"] == "UNCHANGED" for x in comparisons),
        "review_candidate_count": len(queue),
        "new_review_candidate_count": new_review_count,
        "pending_review_count": len(queue),
        "resolved_reviews": resolved_reviews,
        "research_fact_counts_this_run": {
            category: sum(len(obs["facts"][category])
                          for obs in observations if (obs["entity_id"], obs["source_ref"]) in seen)
            for category in CATEGORIES
        },
        "review_queue": queue, "approved_buyers": 0, "qualified_leads": 0,
        "verified_revenue": False, "demand_inferred": False,
        "buyer_intent_inferred": False, "outreach_enabled": False,
        "payment_authorized": False, "execution_authority": "none",
    }
