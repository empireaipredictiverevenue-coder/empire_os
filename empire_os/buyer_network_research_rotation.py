"""Bounded, fair first-party buyer research selector.

No buyer is promoted to commercial readiness by this planner.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping
from urllib.parse import urlsplit
import time
from empire_os.buyer_review_holds import is_do_not_pursue_domain
import re

INVALID_DOMAINS = frozenset({
    "empire-ai.co.uk", "empire-ai.com", "empire-ai.co",
    "yourdomain.com", "example.com", "example.org", "example.net",
    "localhost", "test.com", "yoursite.com", "company.com", "insider.com",
})
ALLOWED_TLDS = frozenset({
    "com", "co", "uk", "io", "ai", "net", "org", "us", "ca", "au",
    "biz", "info", "pro", "media", "marketing", "agency",
    "digital", "group", "company", "services", "solutions",
})
NON_BUYER_DOMAINS = frozenset({
    "ahrefs.com", "semrush.com", "serpapi.com",
    "localfalcon.com", "aol.com",
})

COOLDOWN_SECONDS = 24 * 3600
RESULT_TTL_SECONDS = 7 * 24 * 3600


def accepted_domain(domain: str) -> bool:
    d = (domain or "").strip().lower().rstrip(".")
    if (not d or d in INVALID_DOMAINS or d in NON_BUYER_DOMAINS
            or d.startswith(("empire.", "localhost."))
            or is_do_not_pursue_domain(d)):
        return False
    if d.endswith((".local", ".internal", ".test", ".example", ".localhost", ".sentry.io")):
        return False
    labels = d.split(".")
    if len(labels) < 2 or labels[-1] not in ALLOWED_TLDS:
        return False
    return all(
        len(label) <= 63
        and re.fullmatch(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?", label) is not None
        for label in labels
    )



def verified_first_party_snapshot_results(snapshot: Mapping[str, Any] | None,
                                          *, now_epoch: float | None = None) -> dict[str, dict[str, Any]]:
    """Current source-owned site evidence; does not grant sales permissions."""
    if (not isinstance(snapshot, dict)
            or snapshot.get("schema_version") != "buyer-direct-site-verification-v1"
            or snapshot.get("authority") != "OBSERVE"
            or not isinstance(snapshot.get("governance"), dict)
            or any(snapshot["governance"].get(k) is not False
                   for k in ("outbound", "traffic_activation", "commercial_terms"))
            or not isinstance(snapshot.get("results"), list)
            or len(snapshot["results"]) > 3000):
        return {}
    now = time.time() if now_epoch is None else now_epoch
    try:
        generated = float(snapshot["generated_epoch"])
    except (KeyError, TypeError, ValueError):
        return {}
    if not 0 <= now - generated <= RESULT_TTL_SECONDS:
        return {}
    valid = {}
    duplicates = set()
    for row in snapshot["results"]:
        if not isinstance(row, dict):
            continue
        domain = str(row.get("domain") or "").lower()
        try:
            observed = float(row.get("observed_epoch") or 0)
        except (TypeError, ValueError):
            continue
        evidence = row.get("evidence")
        if (not accepted_domain(domain)
                or not 0 <= now - observed <= RESULT_TTL_SECONDS
                or row.get("corroborated") is not True
                or row.get("buyer_role") is not True
                or type(row.get("pages_successful")) is not int
                or row["pages_successful"] < 1
                or type(row.get("positive_category_count")) is not int
                or row["positive_category_count"] < 2
                or not isinstance(evidence, dict)
                or evidence.get("negative_program") is True):
            continue
        if domain in valid:
            duplicates.add(domain)
        else:
            valid[domain] = row
    for domain in duplicates:
        valid.pop(domain, None)
    return valid


def verified_site_snippets(row: Mapping[str, Any]) -> list[str]:
    """Only snippets from the single verified official domain may be scored."""
    domain = str(row.get("domain") or "").lower()
    snippets = row.get("snippets")
    if not accepted_domain(domain) or not isinstance(snippets, list):
        return []
    evidence = []
    for item in snippets[:12]:
        if not isinstance(item, dict):
            continue
        try:
            url = urlsplit(str(item.get("url") or ""))
            host = str(url.hostname or "").lower()
        except ValueError:
            continue
        if url.scheme != "https" or host not in (domain, "www." + domain):
            continue
        value = item.get("text")
        if isinstance(value, str) and value.strip():
            evidence.append(value.strip()[:1000])
    return list(dict.fromkeys(evidence))

def choose_research_batch(
    backlog: Mapping[str, Any],
    ledger: Mapping[str, Any] | None = None,
    *,
    now_epoch: float,
    limit: int = 8,
    priority_hints: Mapping[str, int] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Attempt every eligible VERIFY/WATCH in bounded batches, fair within lane.

    Under cooldown, do not repeatedly exhaust the top-ranked domains.
    High-priority VERIFY is first while unobserved, then WATCH progresses.
    """
    seen: set[str] = set()
    candidate_items: list[dict[str, Any]] = []
    counts = {"total": 0, "invalid": 0, "duplicate": 0,
              "cooldown": 0, "eligible": 0, "selected": 0}
    state = (ledger or {}).get("domains") or {}
    for raw in backlog.get("candidates") or []:
        if not isinstance(raw, dict):
            continue
        if raw.get("status") not in ("VERIFY_REQUIREMENTS", "WATCH"):
            continue
        counts["total"] += 1
        d = str(raw.get("domain") or "").lower().rstrip(".")
        if not accepted_domain(d):
            counts["invalid"] += 1
            continue
        if d in seen:
            counts["duplicate"] += 1
            continue
        seen.add(d)
        history = state.get(d) if isinstance(state, dict) else None
        history = history if isinstance(history, dict) else {}
        try:
            last = float(history.get("last_attempt_epoch") or 0)
        except (TypeError, ValueError):
            last = 0.0
        if last > 0 and not (last <= now_epoch - COOLDOWN_SECONDS):
            counts["cooldown"] += 1
            continue
        counts["eligible"] += 1
        candidate_items.append({**raw, "domain": d, "_last_attempt": last})
    # Original eligibility and 24h cooldown always apply. The existing
    # buyer team brain may only change order among already eligible sites.
    hints = priority_hints if isinstance(priority_hints, Mapping) else {}
    candidate_items.sort(key=lambda c: (
        0 if c.get("status") == "VERIFY_REQUIREMENTS" else 1,
        -int(hints.get(c["domain"], 0))
            if type(hints.get(c["domain"], 0)) is int
            and 0 <= hints.get(c["domain"], 0) <= 150 else 0,
        c["_last_attempt"],
        -int(c.get("score") or 0),
        c["domain"],
    ))
    selected = [{k: v for k, v in c.items() if k != "_last_attempt"}
                for c in candidate_items[:max(0, min(8, int(limit)))]]
    counts["selected"] = len(selected)
    return selected, counts


def retain_recent_results(
    prior_results: list[dict[str, Any]],
    new_results: list[dict[str, Any]],
    *,
    now_epoch: float,
) -> list[dict[str, Any]]:
    """Preserve only bounded-age, actually fetched evidence, not search prose."""
    merged = {}
    for item in prior_results + new_results:
        if not isinstance(item, dict):
            continue
        d = str(item.get("domain") or "").lower()
        if not accepted_domain(d):
            continue
        try:
            observed = float(item.get("observed_epoch") or 0)
        except (ValueError, TypeError):
            continue
        if observed <= 0 or not 0 <= now_epoch - observed <= RESULT_TTL_SECONDS:
            continue
        merged[d] = item
    return [merged[d] for d in sorted(merged)]


def make_research_summary(
    backlog: Mapping[str, Any],
    ledger: Mapping[str, Any],
    recent_results: list[dict[str, Any]],
) -> dict[str, Any]:
    status = {}
    for c in backlog.get("candidates") or []:
        if isinstance(c, dict) and c.get("status") in ("WATCH", "VERIFY_REQUIREMENTS"):
            status[str(c["domain"]).lower()] = c["status"]
    checked = {
        d: v for d, v in ((ledger.get("domains") or {}).items())
        if d in status and isinstance(v, dict)
        and v.get("last_attempt_epoch")
    }
    checked_watch = sum(status[d] == "WATCH" for d in checked)
    checked_verify = sum(status[d] == "VERIFY_REQUIREMENTS" for d in checked)
    corroborated = {
        r["domain"]: r for r in recent_results
        if r.get("corroborated") is True
    }
    return {
        "schema_version": "empire.buyer_network_research_progress.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "OBSERVE",
        "source_queue_generated_at": backlog.get("generated_at"),
        "verify_requirements_count": sum(s == "VERIFY_REQUIREMENTS" for s in status.values()),
        "watch_count": sum(s == "WATCH" for s in status.values()),
        "verify_attempted_count": checked_verify,
        "watch_attempted_count": checked_watch,
        "outstanding_verify_count": sum(s == "VERIFY_REQUIREMENTS" for s in status.values()) - checked_verify,
        "outstanding_watch_count": sum(s == "WATCH" for s in status.values()) - checked_watch,
        "recent_first_party_corroborated_count": len(corroborated),
        "recent_first_party_corroborated_domains": sorted(corroborated),
        "direct_buyer_payment_proven": False,
        "commercial_terms_verified": False,
        "founder_review_packets_automatically_approved": False,
        "outbound_sent": False,
        "execution_authority": "NONE",
    }
