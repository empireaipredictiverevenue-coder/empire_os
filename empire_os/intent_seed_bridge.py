"""Bridge durable pre-identity intent signals into bounded Buyer Scout seeds.

Public/community intent observations are evidence, not canonical identities.
This module only extracts first-party business URL candidates from the durable
signal inbox and prepares review-only Buyer Scout seed rows.

No prospect is created here. No outreach, terms, payment or revenue authority
is granted.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse


SIGNAL_INBOX = Path("runtime/acquisition/signal_inbox.json")

HOME_SERVICE_INTENT_NICHES = {
    "roofing",
    "residential_roofing",
    "roof_repair",
    "hvac",
    "solar",
    "plumbing",
    "restoration",
    "water_damage_restoration",
    "general_contractor",
    "siding",
    "gutter",
}

NON_BUSINESS_HOSTS = {
    "reddit.com",
    "old.reddit.com",
    "www.reddit.com",
    "linkedin.com",
    "www.linkedin.com",
    "facebook.com",
    "www.facebook.com",
    "x.com",
    "www.x.com",
    "twitter.com",
    "www.twitter.com",
    "youtube.com",
    "www.youtube.com",
}


def _host(value: Any) -> str:
    try:
        host = urlparse(str(value or "").strip()).netloc.casefold()
    except ValueError:
        return ""
    host = host.split("@")[-1].split(":")[0]
    return host[4:] if host.startswith("www.") else host


def _score(value: Any) -> int:
    try:
        return max(0, min(100, int(value)))
    except (TypeError, ValueError):
        return 0


def _profile_for_niche(niche: str) -> tuple[str, list[str]]:
    key = str(niche or "").strip().casefold().replace(" ", "_")
    if key in HOME_SERVICE_INTENT_NICHES:
        return (
            "intent_driven_home_service_growth",
            ["local_and_smb_buyers", "software_and_advisory_buyers"],
        )
    if "legal" in key or "law" in key:
        return (
            "legal_plaintiff_growth_firm",
            ["enterprise_and_data_buyers", "software_and_advisory_buyers"],
        )
    if "insurance" in key:
        return (
            "insurance_distribution_growth",
            ["enterprise_and_data_buyers", "software_and_advisory_buyers"],
        )
    return "enterprise_growth_data_team", ["software_and_advisory_buyers"]


def build_intent_seed_records(
    signals: Mapping[str, Any],
    *,
    limit: int = 12,
) -> list[dict[str, Any]]:
    """Build deduplicated first-party scout seeds from durable intent signals."""
    bounded_limit = max(1, min(int(limit), 50))
    ordered = sorted(
        (
            (str(signal_id), raw)
            for signal_id, raw in signals.items()
            if isinstance(raw, Mapping)
        ),
        key=lambda item: str(item[1].get("last_seen_at") or ""),
        reverse=True,
    )

    rows: list[dict[str, Any]] = []
    seen_domains: set[str] = set()

    for signal_id, raw_value in ordered:
        raw = dict(raw_value)
        source = str(raw.get("source") or "").strip()
        if not source.endswith("_intent"):
            continue
        if raw.get("status") not in {"unresolved", "needs_review"}:
            continue

        candidate_raw = raw.get("raw")
        candidate_raw = (
            dict(candidate_raw)
            if isinstance(candidate_raw, Mapping)
            else {}
        )
        observation = candidate_raw.get("community_intent")
        observation = (
            dict(observation)
            if isinstance(observation, Mapping)
            else {}
        )

        score = _score(
            observation.get("intent_score")
            if observation.get("intent_score") is not None
            else raw.get("lead_score")
        )
        band = str(observation.get("intent_band") or "").strip()
        if score < 35 and band not in {"medium", "high"}:
            continue

        evidence_urls = (
            candidate_raw.get("evidence_urls")
            or observation.get("evidence_urls")
            or ()
        )
        website = ""
        domain = ""
        for value in evidence_urls:
            candidate = str(value or "").strip()
            host = _host(candidate)
            if (
                not candidate.startswith(("http://", "https://"))
                or not host
                or host in NON_BUSINESS_HOSTS
                or host in seen_domains
            ):
                continue
            website = candidate
            domain = host
            break
        if not website:
            continue

        niche = str(
            raw.get("niche")
            or observation.get("niche")
            or "commercial_intent"
        ).strip()
        profile_key, pools = _profile_for_niche(niche)
        title = str(observation.get("title") or "").strip()
        text = str(observation.get("text") or "").strip()
        summary = " ".join(value for value in (title, text) if value)[:1800]

        seen_domains.add(domain)
        rows.append({
            "id": None,
            "business_name": "",
            "niche": niche,
            "website": website,
            "icp_profile_key": profile_key,
            "seed_buyer_pools": pools,
            "seed_product_code": "managed_service",
            "seed_source": "community_intent_signal",
            "seed_intent_signal_id": str(raw.get("signal_id") or signal_id),
            "seed_intent_source": source,
            "seed_intent_score": score,
            "seed_intent_band": band or None,
            "seed_intent_observed_at": (
                str(observation.get("observed_at") or "").strip() or None
            ),
            "seed_intent_pain_points": list(
                observation.get("pain_points") or ()
            ),
            "seed_intent_evidence_url": (
                str(raw.get("url") or observation.get("url") or "").strip()
                or None
            ),
            "seed_intent_summary": summary or None,
            "recovery_source": "signal_inbox",
            "outreach_authorized": False,
            "execution_authority": "none",
        })
        if len(rows) >= bounded_limit:
            break

    return rows


def load_intent_seed_records(
    repo_root: str | Path,
    *,
    limit: int = 12,
) -> list[dict[str, Any]]:
    root = Path(repo_root).resolve()
    try:
        payload = json.loads(
            (root / SIGNAL_INBOX).read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        return []
    signals = payload if isinstance(payload, dict) else {}
    return build_intent_seed_records(signals, limit=limit)
