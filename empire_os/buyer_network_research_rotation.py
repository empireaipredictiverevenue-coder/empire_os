"""Bounded, fair first-party buyer research selector.

No buyer is promoted to commercial readiness by this planner.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping
from empire_os.buyer_review_holds import is_do_not_pursue_domain
import re

INVALID_DOMAINS = frozenset({
    "empire-ai.co.uk", "empire-ai.com", "empire-ai.co",
    "yourdomain.com", "example.com", "example.org", "example.net",
    "localhost", "test.com",
})
ALLOWED_TLDS = frozenset({
    "com", "co", "uk", "io", "ai", "net", "org", "us", "ca",
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
    if d.endswith((".local", ".internal", ".test", ".example", ".localhost")):
        return False
    labels = d.split(".")
    if len(labels) < 2 or labels[-1] not in ALLOWED_TLDS:
        return False
    return all(
        len(label) <= 63
        and re.fullmatch(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?", label) is not None
        for label in labels
    )


def choose_research_batch(
    backlog: Mapping[str, Any],
    ledger: Mapping[str, Any] | None = None,
    *,
    now_epoch: float,
    limit: int = 8,
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
    candidate_items.sort(key=lambda c: (
        0 if c.get("status") == "VERIFY_REQUIREMENTS" else 1,
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
