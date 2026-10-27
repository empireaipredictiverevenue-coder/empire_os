"""Read-only evidence bridge: traffic source -> independently settled calls.

Uses original SEO and YouTube owners' existing observation receipts. The
call-to-cash receipt belongs to a protected commercial owner: metadata is
observed, never chmod'ed, parsed or claimed as earned money here.
No service, DB schema, ad campaign, web publisher, CRM or routing mutation.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

SCHEMA = "empire.competitor_call_conversion_readiness.v1"
GSC_FOLDER = Path("/home/ubuntu/empire_releases/seo_weekly_gsc_two_page_20261022")
GSC_NAME = re.compile("weekly_seo_growth_actions_[0-9]{4}-[0-9]{2}-[0-9]{2}[.]json$")
YOUTUBE_PATH = Path("runtime/media_os/youtube_private_analytics/youtube_growth_analytics_latest.json")
CASH_PATH = Path("runtime/revenue/lead_smart/commercial_pulse/call_to_cash_latest.json")
SOURCE_REGISTRY = Path("runtime/competitive_intelligence/call_traffic_source_registry_latest.json")
DEST = Path("runtime/competitive_intelligence/call_conversion_readiness_latest.json")


def _review_date(value: Any) -> date:
    if not isinstance(value, str):
        raise ValueError("date missing")
    return date.fromisoformat(value)


def _observed_at(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ValueError("time missing")
    t = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if t.tzinfo is None:
        raise ValueError("timezone missing")
    return t.astimezone(timezone.utc)


def _load(path: Path, *, max_size: int = 100_000) -> dict | None:
    try:
        if path.is_symlink() or not path.is_file():
            return None
        stat = path.stat()
        if not 10 <= stat.st_size <= max_size:
            return None
        raw = json.loads(path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else None
    except (OSError, ValueError, UnicodeError):
        return None


def _latest_gsc_review(folder: Path) -> dict | None:
    """Read an already-produced weekly owner report, never fetch GSC."""
    try:
        if folder.is_symlink() or not folder.is_dir():
            return None
        reports = sorted(
            (p for p in folder.iterdir() if GSC_NAME.fullmatch(p.name)
             and p.is_file() and not p.is_symlink()),
            key=lambda p: p.name,
            reverse=True,
        )
    except OSError:
        return None
    # Latest valid report, not a fabricated zero when an owner export is missing.
    for report in reports[:6]:
        data = _load(report, max_size=300_000)
        if data is not None:
            return data
    return None


def build_readiness(*, gsc: dict | None, youtube: dict | None,
                    sources: dict | None, cash_source_state: str,
                    now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("timezone-aware review time required")
    now = now.astimezone(timezone.utc)
    source_ok = (
        isinstance(sources, dict)
        and sources.get("schema_version") == "empire.call_traffic_source_registry.v1"
        and sources.get("mode") == "OBSERVE"
        and sources.get("source_count") == 15
        and sources.get("organic_earned_count") == 7
        and sources.get("paid_candidate_count") == 7
        and sources.get("policy_excluded_count") == 1
        and sources.get("media_spend_authorized") is False
        and sources.get("execution_authority") == "none"
    )
    gsc_valid = False
    if isinstance(gsc, dict):
        try:
            age = (now.date() - _review_date(gsc.get("as_of"))).days
            gsc_valid = (
                gsc.get("schema_version") == "empire.search.seo_growth_action_queue.v1"
                and gsc.get("mode") == "OBSERVE"
                and gsc.get("execution_authority") == "none"
                and gsc.get("source_property") == "sc-domain:empire-ai.co.uk"
                and gsc.get("database_writes") is False
                and gsc.get("outbound_sent") is False
                and type(gsc.get("gsc_returned_page_rows")) is int
                and 0 <= gsc["gsc_returned_page_rows"] <= 100_000
                and type(gsc.get("gsc_pages_without_reported_row")) is int
                and 0 <= gsc["gsc_pages_without_reported_row"] <= 100_000
                and 0 <= age <= 14
            )
        except (TypeError, ValueError, OverflowError):
            pass

    youtube_valid = False
    if isinstance(youtube, dict):
        try:
            youtube_age = (now - _observed_at(youtube.get("observed_at"))).total_seconds()
            youtube_valid = (
                youtube.get("schema_version") == "empire.media.youtube_growth_command_centre.v1"
                and youtube.get("mode") == "OBSERVE"
                and youtube.get("execution_authority") == "none"
                and youtube.get("owned_analytics_authenticated") is True
                and youtube.get("source") == "youtube_analytics_api"
                and youtube.get("automatic_upload_authorized") is False
                and 0 <= youtube_age <= 30 * 86400
            )
        except (TypeError, ValueError, OverflowError):
            pass

    if cash_source_state not in {
        "PROTECTED_BY_COMMERCIAL_OWNER", "ABSENT",
        "AVAILABLE_UNPARSED_OWNER_ONLY",
    }:
        raise ValueError("untrusted commercial receipt availability")
    organic = {
        "available": gsc_valid,
        "report_as_of": gsc.get("as_of") if gsc_valid else None,
        "gsc_page_rows": gsc.get("gsc_returned_page_rows") if gsc_valid else None,
        "sitemap_pages_without_reported_row": gsc.get("gsc_pages_without_reported_row") if gsc_valid else None,
        "exact_keyword_query_matches": gsc.get("keyword_exact_query_matches") if gsc_valid else None,
        "direct_site_sessions_verified": False,
        "gsc_impressions_not_paid_leads": True,
        "report_does_not_authorise_seo_edit_or_publication": True,
    }
    yt = {
        "available": youtube_valid,
        "observed_at": youtube.get("observed_at") if youtube_valid else None,
        "authenticated_analytics": youtube_valid,
        "verified_website_visits": (
            youtube.get("verified_website_traffic") if youtube_valid
            and type(youtube.get("verified_website_traffic")) is int else None
        ),
        "verified_commercial_enquiries": (
            youtube.get("verified_commercial_enquiries") if youtube_valid
            and type(youtube.get("verified_commercial_enquiries")) is int else None
        ),
        "youtube_video_views_are_not_calls": True,
    }
    steps = [
        {"priority": 1, "owner": "ORIGINAL_SEARCH_INTELLIGENCE_AND_WEBSITE_OWNERS",
         "task": "VERIFY_LANDING_SESSION_ATTRIBUTION",
         "evidence_required": "Actual source, page, session and campaign join; do not substitute GSC impressions",
         "status": "EVIDENCE_PARTIAL" if gsc_valid else "SOURCE_REPORT_UNAVAILABLE"},
        {"priority": 2, "owner": "ORIGINAL_PUBLISHER_AND_MEDIA_OWNERS",
         "task": "VERIFY_PUBLISHER_AND_VIDEO_REFERRAL_LINKS",
         "evidence_required": "Approved source tags, media link clicks and measured site arrivals",
         "status": "MEASURED_SITE_VISITS_NOT_PROVEN" if youtube_valid else "VIDEO_SOURCE_UNAVAILABLE"},
        {"priority": 3, "owner": "ORIGINAL_LEAD_SMART_CALL_OWNER",
         "task": "AUTHORITATIVE_SOURCE_TO_CALL_JOIN",
         "evidence_required": "First-party consented call choice, protected site handoff and Ringba call ID",
         "status": "PROTECTED_OWNER_DATA_NOT_ADOPTED"},
        {"priority": 4, "owner": "ORIGINAL_BUYER_COMMERCIAL_AND_FINANCE_OWNERS",
         "task": "AUTHORITATIVE_CALL_TO_SETTLEMENT_JOIN",
         "evidence_required": "Contract-qualified buyer acceptance, reversals and independently reconciled payout",
         "status": cash_source_state},
        {"priority": 5, "owner": "FOUNDER_AND_EXISTING_ADS_MEDIA_OWNER",
         "task": "PAID_TRAFFIC_UNIT_ECONOMICS_PRELAUNCH",
         "evidence_required": "Buyer-approved paid source and geo/hours, consent, ad policy, actual CPC and cost per settled call",
         "status": "HOLD_PAID_SPEND_NO_CALIBRATION"},
    ]
    return {
        "schema_version": SCHEMA, "mode": "OBSERVE",
        "generated_at": now.isoformat(),
        "source_registry_available": source_ok,
        "first_party_organic": organic,
        "owned_youtube": yt,
        "call_to_cash": {
            "source_state": cash_source_state,
            "authority_owner": "ORIGINAL_LEAD_SMART_COMMERCIAL_OWNER",
            "protected_content_read": False,
            "payable_call_count": None,
            "settled_revenue_usd": None,
        },
        "measurement_chain_steps": [
            {"stage": stage, "verified": False, "count": None}
            for stage in (
                "LANDING_SESSION_BY_CHANNEL", "GEO_ELIGIBLE_INTERACTION",
                "CONSENTED_CALL_CHOICE", "RINGBA_CONNECTED_CALL",
                "BUYER_ACCEPTED_PAYABLE_CALL", "INDEPENDENT_SETTLED_RECEIPT",
            )
        ],
        "exact_source_to_settlement_proven": False,
        "acquisition_source_profitability_calibrated": False,
        "next_owner_actions": steps,
        "no_duplicate_seo_or_buyer_service": True,
        "ad_spend_authorized": False,
        "content_publication_authorized": False,
        "external_send_authorized": False,
        "database_writes": False,
        "execution_authority": "none",
    }


def refresh(repo_root: Path) -> dict:
    gsc = _latest_gsc_review(GSC_FOLDER)
    yt = _load(repo_root / YOUTUBE_PATH)
    sources = _load(repo_root / SOURCE_REGISTRY)
    private = repo_root / CASH_PATH
    # This root-owned commercial receipt is outside this team's authority.
    # Presence can be observed without opening it, regardless of the
    # current process credentials. Its contents belong to the owning worker.
    try:
        private_status = "PROTECTED_BY_COMMERCIAL_OWNER" if private.is_file() else "ABSENT"
    except OSError:
        private_status = "ABSENT"
    report = build_readiness(
        gsc=gsc, youtube=yt, sources=sources,
        cash_source_state=private_status,
    )
    dst = repo_root / DEST
    if not dst.parent.is_dir() or dst.parent.is_symlink() or dst.is_symlink():
        raise ValueError("unsafe original intelligence directory")
    fd, tmp = tempfile.mkstemp(prefix=".call-conversion-readiness-", dir=dst.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, sort_keys=True)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, dst)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return report
