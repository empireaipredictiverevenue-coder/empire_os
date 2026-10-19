"""Owned *industry page* campaign collector release: extension, not replacement.

This validates a separately approved, immutable measurement-only release.
It NEVER modifies the existing five-campaign research release, registers a
campaign, publishes, issues consent, or creates a DB table.

Events reuse public.record_owned_campaign_event through the existing
OwnedCampaignRepository and its campaign_id:landing asset constraint.
Accepted browser events are observations, NOT verified unique visitors.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping
from uuid import UUID
from urllib.parse import parse_qs, urlsplit

from empire_os.organic_campaign_touch import normalize_organic_touch

from empire_os.owned_campaign_preflight import CAMPAIGN_ID, digest
from empire_os.owned_campaign_intake import _strict

ROOT = Path("/srv/empire_os")
RELEASE = Path("runtime/astra/owned_industry_campaign_measurement_release.v1.json")
SCHEMA = "empire.owned_industry_measurement_release.v1"
ALLOWED = {
    "/industries/solar": "solar",
    "/industries/roofing": "roofing",
}
EVENTS = frozenset(("campaign_page_view", "campaign_cta_click"))
REQUIRED = (
    "event_id", "event_type", "campaign_id", "asset_id",
    "source", "channel", "occurred_at",
)


def _hex_digest(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def load_industry_release(
    root: Path = ROOT,
    *,
    research_release: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Fail closed unless a separately deployed and reviewed release is intact.

    research_release is ONLY the return of the existing load_release(root).
    If it is missing, the original research release hasn't passed its gate.
    """
    if research_release is None:
        from empire_os.owned_campaign_release import load_release
        research_release = load_release(root)
    if not isinstance(research_release, Mapping):
        return None
    try:
        path = root / RELEASE
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 32768:
            return None
        release = json.loads(path.read_text("utf-8"))
        if not isinstance(release, dict) or release.get("schema_version") != SCHEMA:
            return None
        if (release.get("status") != "OWNER_APPROVED_DEPLOYED_MEASUREMENT_ONLY"
                or release.get("execution_authority") != "measurement_only"
                or release.get("zero_paid_spend") is not True
                or release.get("automatic_publication") is not False
                or release.get("automatic_outbound") is not False
                or release.get("payments_enabled") is not False):
            return None
        reviews = release.get("reviews")
        if not isinstance(reviews, dict):
            return None
        for name in ("privacy", "website", "collector", "founder"):
            entry = reviews.get(name)
            if (not isinstance(entry, dict)
                    or entry.get("status") != "APPROVED"
                    or not isinstance(entry.get("evidence_ref"), str)
                    or not 8 <= len(entry["evidence_ref"]) <= 200):
                return None
        deployment = release.get("deployment_evidence_ref")
        if not isinstance(deployment, str) or not 8 <= len(deployment) <= 200:
            return None
        if (not isinstance(release.get("research_release_sha256"), str)
                or not _hex_digest(release["research_release_sha256"])
                or release["research_release_sha256"] != digest(research_release["campaigns"])):
            return None
        rows = release.get("campaigns")
        if not isinstance(rows, list) or not 1 <= len(rows) <= 10:
            return None
        ids = set()
        paths = set()
        for row in rows:
            if not isinstance(row, dict) or set(row) != {
                "campaign_id", "asset_id", "landing_path",
                "sector", "html_sha256", "source_evidence_ref"
            }:
                return None
            cid, route = row["campaign_id"], row["landing_path"]
            if (not isinstance(cid, str) or not CAMPAIGN_ID.fullmatch(cid)
                    or route not in ALLOWED
                    or row["sector"] != ALLOWED[route]
                    or row["asset_id"] != f"{cid}:landing"
                    or not _hex_digest(row["html_sha256"])
                    or not isinstance(row["source_evidence_ref"], str)
                    or not 8 <= len(row["source_evidence_ref"]) <= 200
                    or cid in ids or route in paths):
                return None
            ids.add(cid)
            paths.add(route)
            if cid in {
                c.get("campaign_id") for c in research_release["campaigns"]
                if isinstance(c, dict)
            }:
                return None
            file = root / ("apps/empire-public-site/out" + route + ".html")
            if not file.is_file() or file.is_symlink():
                return None
            if sha256(file.read_bytes()).hexdigest() != row["html_sha256"]:
                return None
        return release
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        return None


def validate_industry_event(
    payload: Any,
    release: Mapping[str, Any],
    *,
    now: datetime | None = None,
) -> dict[str, str]:
    """Accept only anonymous, bounded page-view/CTA observations for live rows."""
    _strict(payload, REQUIRED)
    cid = payload["campaign_id"]
    rows = release.get("campaigns") if isinstance(release, Mapping) else None
    if not isinstance(rows, list) or len(rows) > 10:
        raise ValueError("industry release missing")
    matches = [r for r in rows if r.get("campaign_id") == cid]
    if len(matches) != 1 or payload["asset_id"] != matches[0]["asset_id"]:
        raise ValueError("unreleased campaign or asset")
    if (payload["event_type"] not in EVENTS
            or payload["source"] != "owned_site"
            or payload["channel"] != "organic"):
        raise ValueError("not a supported browser observation")
    event_id = UUID(payload["event_id"])
    if event_id.version != 4:
        raise ValueError("fresh random UUID event required")
    stamp = datetime.fromisoformat(payload["occurred_at"].replace("Z", "+00:00"))
    current = now or datetime.now(timezone.utc)
    if (stamp.tzinfo is None or current.tzinfo is None
            or stamp > current + timedelta(minutes=5)
            or stamp < current - timedelta(days=7)):
        raise ValueError("outside event acceptance window")
    return {
        "event_id": str(event_id),
        "event_type": payload["event_type"],
        "campaign_id": cid,
        "asset_id": matches[0]["asset_id"],
        "source": "owned_site",
        "channel": "organic",
        "occurred_at": stamp.astimezone(timezone.utc).isoformat(),
    }


def validate_industry_referrer(
    browser_referrer: Any,
    payload: Mapping[str, str],
    release: Mapping[str, Any],
) -> None:
    """Bound claimed page source to exact released path and URL campaign token.

    Browser headers can be forged; this is a bounded consistency check, not
    authentication, proof of a platform click or a unique human visitor.
    """
    if not isinstance(browser_referrer, str) or len(browser_referrer) > 1600:
        raise ValueError("bounded first-party browser referrer required")
    parts = urlsplit(browser_referrer)
    if (parts.scheme != "https" or parts.netloc != "empire-ai.co.uk"
            or parts.username or parts.password or parts.fragment):
        raise ValueError("first-party referrer required")
    matches = [r for r in release["campaigns"]
               if r["campaign_id"] == payload["campaign_id"]]
    if len(matches) != 1 or parts.path != matches[0]["landing_path"]:
        raise ValueError("unreleased page observation")
    params = parse_qs(parts.query, keep_blank_values=True)
    names = ("utm_campaign", "utm_content", "utm_source", "utm_medium")
    if "utm_id" in params or any(len(params.get(k, [])) != 1 for k in names):
        raise ValueError("not an owned JEV link")
    touch = normalize_organic_touch({
        "campaign_id": params["utm_campaign"][0],
        "asset_id": params["utm_content"][0],
        "source": params["utm_source"][0],
        "medium": params["utm_medium"][0],
        "landing_path": parts.path,
    })
    if touch["campaign_id"] != payload["campaign_id"]:
        raise ValueError("referrer campaign does not match accepted event")


def review_unactivated_industry_release(
    *,
    root: Path = ROOT,
    research_release: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    active = load_industry_release(root, research_release=research_release)
    return {
        "schema_version": "empire.industry_measurement_release_observe.v1",
        "mode": "OBSERVE",
        "status": "OWNER_APPROVED_ACTIVE" if active else "NO_VALIDATED_INDUSTRY_RELEASE",
        "released_campaigns": len(active["campaigns"]) if active else 0,
        "observed_events": None,
        "new_website_or_db_write": False,
        "release_modified": False,
        "execution_authority": "none",
    }
