"""Durable pre-identity signal inbox for specialist acquisition sources.

Signals such as permits, Reddit demand posts, weather alerts and municipal
events are evidence of commercial opportunity, not canonical business
identities. This store retains them without creating fake prospects.

No outreach, payment, revenue recognition or authority expansion occurs here.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from empire_os.locale_intelligence import resolve_locale

ROOT = Path("/srv/empire_os/runtime/acquisition")
INBOX = ROOT / "signal_inbox.json"
LOCK = ROOT / "signal_inbox.lock"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _data(candidate: Any) -> dict[str, Any]:
    if isinstance(candidate, Mapping):
        return dict(candidate)
    if is_dataclass(candidate):
        return asdict(candidate)
    return {
        key: getattr(candidate, key, None)
        for key in (
            "name", "email", "phone", "niche", "metro", "state",
            "country_code", "language_code", "source_language", "timezone",
            "details", "source", "lead_score", "url", "raw",
        )
    }


def _fingerprint(row: Mapping[str, Any]) -> str:
    raw = row.get("raw")
    material = {
        "source": str(row.get("source") or "").strip().lower(),
        "url": str(row.get("url") or "").strip(),
        "name": str(row.get("name") or "").strip().lower(),
        "metro": str(row.get("metro") or "").strip().lower(),
        "niche": str(row.get("niche") or "").strip().lower(),
        "raw_id": (
            str(raw.get("id") or raw.get("job__") or raw.get("permalink") or "")
            if isinstance(raw, Mapping)
            else ""
        ),
    }
    return hashlib.sha256(
        json.dumps(material, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _load() -> dict[str, dict[str, Any]]:
    try:
        value = json.loads(INBOX.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def enqueue_signal(candidate: Any, *, quality: Any = None) -> dict[str, Any]:
    ROOT.mkdir(parents=True, exist_ok=True)
    LOCK.touch(exist_ok=True)
    row = _data(candidate)
    locale = resolve_locale(row)
    fp = _fingerprint(row)

    with LOCK.open("r+") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            data = _load()
            existing = data.get(fp)
            if isinstance(existing, dict):
                existing["last_seen_at"] = _now()
                existing["seen_count"] = int(existing.get("seen_count") or 1) + 1
                decision = "matched"
                record = existing
            else:
                q = (
                    quality.to_evidence()
                    if quality is not None and hasattr(quality, "to_evidence")
                    else {}
                )
                record = {
                    "signal_id": fp,
                    "status": "unresolved",
                    "created_at": _now(),
                    "last_seen_at": _now(),
                    "seen_count": 1,
                    "source": str(row.get("source") or "").strip(),
                    "name": str(row.get("name") or "").strip(),
                    "niche": str(row.get("niche") or "").strip(),
                    "metro": str(row.get("metro") or "").strip(),
                    "state": str(row.get("state") or "").strip(),
                    "phone": str(row.get("phone") or "").strip(),
                    "email": str(row.get("email") or "").strip(),
                    "url": str(row.get("url") or "").strip(),
                    "details": str(row.get("details") or "").strip(),
                    "lead_score": row.get("lead_score"),
                    "raw": row.get("raw"),
                    "locale": locale.as_dict(),
                    "quality": q,
                    "entity_id": None,
                    "prospect_id": None,
                    "resolution_attempts": 0,
                    "next_resolution_at": _now(),
                    "execution_authority": "none",
                }
                data[fp] = record
                decision = "created"

            tmp = INBOX.with_suffix(".json.tmp")
            tmp.write_text(
                json.dumps(data, indent=2, sort_keys=True, default=str) + "\n",
                encoding="utf-8",
            )
            tmp.replace(INBOX)
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    return {
        "decision": decision,
        "signal_id": fp,
        "status": record.get("status"),
        "source": record.get("source"),
        "locale": record.get("locale"),
        "execution_authority": "none",
    }



HOME_SERVICE_NICHES = {
    "roofing",
    "residential_roofing",
    "roof_repair",
    "siding",
    "hvac",
    "plumbing",
    "restoration",
    "water_damage_restoration",
    "solar",
    "general_contractor",
}


def _signal_evidence_urls(row: Mapping[str, Any]) -> list[str]:
    raw = row.get("raw")
    raw = raw if isinstance(raw, Mapping) else {}
    community = raw.get("community_intent")
    community = community if isinstance(community, Mapping) else {}
    values = [
        *(community.get("evidence_urls") or ()),
        *(raw.get("evidence_urls") or ()),
    ]
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        url = str(value or "").strip()
        if (
            url.startswith(("http://", "https://"))
            and url not in seen
        ):
            seen.add(url)
            output.append(url)
    return output


def intent_seed_records(
    *,
    inbox: Path = INBOX,
    limit: int = 20,
    min_intent_score: int = 35,
) -> list[dict[str, Any]]:
    """Project durable intent signals into review-only Buyer Scout seeds.

    A first-party URL is only an identity research lead. This function does not
    assert that the public author owns the linked business, create a prospect,
    or grant outreach authority.
    """
    try:
        value = json.loads(inbox.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    data = value if isinstance(value, dict) else {}

    candidates: list[dict[str, Any]] = []
    seen_domains: set[str] = set()
    for signal_id, raw_row in sorted(
        data.items(),
        key=lambda item: str(
            (item[1] if isinstance(item[1], Mapping) else {}).get(
                "last_seen_at"
            )
            or ""
        ),
        reverse=True,
    ):
        if not isinstance(raw_row, Mapping):
            continue
        row = dict(raw_row)
        source = str(row.get("source") or "").strip()
        if not source.endswith("_intent"):
            continue
        if row.get("status") not in {"unresolved", "needs_review"}:
            continue
        try:
            score = int(row.get("lead_score") or 0)
        except (TypeError, ValueError):
            score = 0
        if score < max(0, int(min_intent_score)):
            continue

        raw = row.get("raw")
        raw = raw if isinstance(raw, Mapping) else {}
        observation = raw.get("community_intent")
        observation = (
            observation if isinstance(observation, Mapping) else {}
        )
        niche = str(row.get("niche") or "").strip().casefold()
        home_service = niche in HOME_SERVICE_NICHES
        profile_key = (
            "home_service_growth_intent"
            if home_service
            else "enterprise_growth_data_team"
        )
        buyer_pools = (
            ["local_and_smb_buyers", "software_and_advisory_buyers"]
            if home_service
            else ["software_and_advisory_buyers"]
        )
        product_code = (
            "managed_service"
            if home_service
            else "predictive_revenue_intelligence_os"
        )
        evidence_summary = " ".join(
            part
            for part in (
                str(observation.get("title") or "").strip(),
                str(observation.get("text") or "").strip(),
            )
            if part
        )[:3000]

        for website in _signal_evidence_urls(row):
            try:
                host = (
                    website.split("://", 1)[1]
                    .split("/", 1)[0]
                    .split("@")[-1]
                    .split(":")[0]
                    .casefold()
                )
            except (IndexError, AttributeError):
                continue
            if host.startswith("www."):
                host = host[4:]
            if not host or host in seen_domains:
                continue
            seen_domains.add(host)
            candidates.append({
                "id": f"intent:{signal_id}",
                "business_name": "",
                "niche": niche or "commercial_intent",
                "website": website,
                "icp_profile_key": profile_key,
                "seed_buyer_pools": buyer_pools,
                "seed_product_code": product_code,
                "seed_intent_signal_id": str(signal_id),
                "seed_intent_source": source,
                "seed_intent_score": score,
                "seed_intent_band": str(
                    observation.get("intent_band") or ""
                ).strip() or None,
                "seed_intent_pain_points": list(
                    observation.get("pain_points") or ()
                ),
                "seed_intent_evidence_url": str(
                    row.get("url") or ""
                ).strip() or None,
                "seed_intent_summary": evidence_summary or None,
                "recovery_source": "community_intent_signal_inbox",
                "outreach_authorized": False,
            })
            if len(candidates) >= max(1, min(int(limit), 100)):
                return candidates
    return candidates

def snapshot() -> dict[str, Any]:
    data = _load()
    statuses: dict[str, int] = {}
    sources: dict[str, int] = {}
    for row in data.values():
        if not isinstance(row, dict):
            continue
        status = str(row.get("status") or "unknown")
        source = str(row.get("source") or "unknown")
        statuses[status] = statuses.get(status, 0) + 1
        sources[source] = sources.get(source, 0) + 1
    return {
        "total": len(data),
        "by_status": statuses,
        "by_source": sources,
        "execution_authority": "none",
    }
