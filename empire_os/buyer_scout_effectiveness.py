"""Yield and source-recovery observer for the ORIGINAL Scout research cycle.

Joins only already-owned OBSERVE snapshots. An attempt, research seed, site
corroboration, or decreased gap is not accepted geography, buyer capacity,
completed qualification, payable terms or recognised revenue.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from empire_os.buyer_network_research_rotation import accepted_domain

SCHEMA = "empire.buyer_scout.effectiveness.v1"
BASE = Path("runtime/buyer_network_intelligence")
PUBLIC = Path("runtime/buyer_acquisition/public_research_seeds.json")
SCOUT = Path("runtime/buyer_acquisition/scout_latest.json")
MAX_ROWS = 500
MAX_AGE = 3 * 3600


def read_safe(path: Path, *, limit: int = 3_000_000) -> dict:
    try:
        if path.is_symlink() or not 30 <= path.stat().st_size <= limit:
            return {}
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError, UnicodeError):
        return {}


def timestamp(value: Any) -> float | None:
    try:
        instant = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return instant.timestamp() if instant.utcoffset() is not None else None
    except (ValueError, OverflowError, TypeError):
        return None


def quality_rows(source: dict, *, now_epoch: float) -> dict[str, dict] | None:
    at = timestamp(source.get("generated_at"))
    rows = source.get("targets")
    if (source.get("schema_version") != "empire.buyer_qualification_actions.v1"
            or source.get("mode") != "OBSERVE"
            or source.get("execution_authority") != "none"
            or source.get("outbound_enabled") is not False
            or source.get("outbound_sent") is not False
            or at is None or not -300 <= now_epoch - at <= MAX_AGE
            or not isinstance(rows, list) or len(rows) > MAX_ROWS):
        return None
    result = {}
    for row in rows:
        if not isinstance(row, dict) or not accepted_domain(row.get("domain", "")):
            return None
        domain = row["domain"]
        if domain in result:
            return None
        result[domain] = row
    return result


def ledger_attempts(before: dict, after: dict, site: dict,
                    *, now_epoch: float) -> dict[str, dict] | None:
    if (after.get("schema_version") != "empire.buyer_network_research_ledger.v1"
            or after.get("mode") != "OBSERVE"
            or site.get("schema_version") != "buyer-direct-site-verification-v1"
            or site.get("authority") != "OBSERVE"
            or any((site.get("governance") or {}).get(k) is not False
                   for k in ("outbound", "forms", "logins", "db_write",
                             "traffic_activation", "commercial_terms", "funds"))
            or not isinstance(after.get("domains"), dict)
            or len(after["domains"]) > 3000
            or not isinstance(site.get("results"), list)
            or len(site["results"]) > 3000):
        return None
    previous = before.get("domains", {}) if isinstance(before.get("domains"), dict) else {}
    observed = {}
    for row in site["results"]:
        if isinstance(row, dict) and accepted_domain(row.get("domain", "")):
            observed.setdefault(row["domain"], []).append(row)
    attempts = {}
    for domain, current in after["domains"].items():
        if not accepted_domain(domain) or not isinstance(current, dict):
            continue
        try:
            at = float(current["last_attempt_epoch"])
            old = float((previous.get(domain) or {}).get("last_attempt_epoch") or 0)
        except (TypeError, ValueError, KeyError, OverflowError, AttributeError):
            continue
        if not old < at or not 0 <= now_epoch - at <= MAX_AGE:
            continue
        matches = []
        for observation in observed.get(domain, []):
            try:
                if abs(float(observation["observed_epoch"]) - at) <= 1:
                    matches.append(observation)
            except (TypeError, ValueError, KeyError):
                pass
        if len(matches) != 1:
            continue
        obs = matches[0]
        first_party = (current.get("status") == "CORROBORATED_FIRST_PARTY"
                       and obs.get("corroborated") is True
                       and obs.get("buyer_role") is True
                       and type(obs.get("pages_successful")) is int
                       and obs["pages_successful"] > 0
                       and type(obs.get("positive_category_count")) is int
                       and obs["positive_category_count"] >= 2
                       and isinstance(obs.get("evidence"), dict)
                       and obs["evidence"].get("negative_program") is not True)
        attempts[domain] = {"observed_epoch": at, "first_party_role": first_party}
    return attempts


def research_effectiveness(before_quality: dict, after_quality: dict,
                           before_ledger: dict, after_ledger: dict,
                           site: dict, prior: dict, public: dict, scout: dict,
                           *, now: datetime) -> dict:
    now_epoch = now.timestamp()
    before = quality_rows(before_quality, now_epoch=now_epoch)
    after = quality_rows(after_quality, now_epoch=now_epoch)
    attempts = ledger_attempts(before_ledger, after_ledger, site, now_epoch=now_epoch)
    measurable = before is not None and after is not None and attempts is not None
    history_before = (prior.get("domain_yield_history") or {}
                      if prior.get("schema_version") == SCHEMA else {})
    history_before = history_before if isinstance(history_before, dict) else {}
    history = {}
    for domain, item in list(history_before.items())[:MAX_ROWS]:
        if accepted_domain(domain) and isinstance(item, dict):
            history[domain] = {
                "no_progress_streak": min(4, max(0, item.get("no_progress_streak", 0)))
                if type(item.get("no_progress_streak")) is int else 0,
                "last_attempt_epoch": item.get("last_attempt_epoch", 0),
            }
    improvements = []
    checked = []
    if measurable:
        for domain, observation in sorted(attempts.items()):
            old, new = before.get(domain), after.get(domain)
            if not old or not new:
                continue
            # Compare independently sourced qualification fields, not a newly
            # generated report time or an optimistic probe status.
            old_gaps = set(old.get("missing_evidence") or [])
            new_gaps = set(new.get("missing_evidence") or [])
            lost_gaps = sorted(old_gaps - new_gaps)
            gained_role = (old.get("site_corroborated_buyer_role") is not True
                           and new.get("site_corroborated_buyer_role") is True
                           and observation["first_party_role"])
            old_fit = (old.get("active_demand_sector_research_fit") or {}).get("state")
            new_fit = (new.get("active_demand_sector_research_fit") or {}).get("state")
            improved_fit = old_fit != "FIRST_PARTY_SECTOR_RESEARCH_FIT" and new_fit == "FIRST_PARTY_SECTOR_RESEARCH_FIT" and observation["first_party_role"]
            improved = bool(lost_gaps or gained_role or improved_fit)
            strikes = 0 if improved else min(4, history.get(domain, {}).get("no_progress_streak", 0) + 1)
            history[domain] = {"no_progress_streak": strikes,
                               "last_attempt_epoch": observation["observed_epoch"]}
            checked.append(domain)
            if improved:
                improvements.append({"domain": domain, "removed_gap_count": len(lost_gaps),
                                     "buyer_role_research_improved": gained_role,
                                     "sector_research_improved": improved_fit})
    # Advisory preference only. Original research eligibility and 24-hour
    # probe cooldown are enforced elsewhere and NEVER relaxed here.
    penalties = {d: min(60, 20 * record["no_progress_streak"])
                 for d, record in history.items()
                 if record.get("no_progress_streak", 0) >= 2 and d in (after or {})}
    public_at = timestamp(public.get("generated_at"))
    scout_at = timestamp(scout.get("generated_at"))
    public_fresh = (public.get("schema_version") == "empire.buyer_public_research_seeds.v1"
                    and public.get("mode") == "OBSERVE"
                    and public.get("outbound_sent") is False
                    and public_at is not None and 0 <= now_epoch-public_at <= MAX_AGE)
    scout_fresh = (scout.get("mode") == "OBSERVE" and scout.get("outbound_sent") is False
                   and scout_at is not None and 0 <= now_epoch-scout_at <= MAX_AGE)
    return {
        "schema_version": SCHEMA, "generated_at": now.isoformat(), "mode": "OBSERVE",
        "status": "MEASURED" if measurable else "UNMEASURABLE_MISSING_OR_UNSAFE_SOURCE",
        "source_fingerprints_sha256": {
            "qualification_before": source_fingerprint(before_quality),
            "qualification_after": source_fingerprint(after_quality),
            "original_scout_ledger_before": source_fingerprint(before_ledger),
            "original_scout_ledger_after": source_fingerprint(after_ledger),
            "original_scout_site_evidence": source_fingerprint(site),
        },
        "attempted_site_domains_with_joined_receipts": len(attempts or {}),
        "compared_qualification_domains": len(checked),
        "company_research_evidence_improvement_count": len(improvements),
        "without_evidence_improvement_count": len(checked)-len(improvements),
        "improvements": improvements[:25],
        "domain_yield_history": dict(sorted(history.items())[:MAX_ROWS]),
        "research_deprioritization_hints": penalties,
        "penalties_are_advisory_not_eligibility": True,
        "public_seed_lane": {
            "state": public.get("fresh_search_result_status") if public_fresh else "UNVERIFIED_OR_STALE",
            "fresh_domains": public.get("fresh_search_domain_count") if public_fresh else None,
            "repeat_search_deferred": (public.get("source_recovery") or {}).get("repeat_search_deferred") is True if public_fresh else False,
        },
        "original_scout": {
            "source_state": "FRESH" if scout_fresh else "UNVERIFIED_OR_STALE",
            "search_domains": scout.get("search_domain_count") if scout_fresh else None,
        },
        "source_recovery_route": "ORIGINAL_SITE_QUEUE_AND_OFFICIAL_FIRST_PARTY_SEEDS",
        "causality_proven": False, "commercial_buyer_accepted": False,
        "buyer_zip_capacity_verified": False, "outbound_sent": False,
        "database_writes": False, "payment_authorized": False,
    }


def source_fingerprint(source: dict) -> str:
    return sha256(json.dumps(source, sort_keys=True, default=str).encode()).hexdigest()
