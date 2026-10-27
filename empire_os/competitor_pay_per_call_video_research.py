"""Primary-source pay-per-call YouTube findings for original EmpireOS.

Static evidence with distinction between full transcripts, operator excerpts
and video-only descriptions; no YouTube scraping, ad spend or contact action.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

SCHEMA = "empire.competitor_pay_per_call_video_research.v1"
INPUT_SCHEMA = "empire.competitor_video_strategy_sources.v1"
SOURCE = Path("docs/commercial/PAY_PER_CALL_YOUTUBE_OPERATOR_RESEARCH_20261027.json")
DEST = Path("runtime/competitive_intelligence/pay_per_call_youtube_research_latest.json")
EVIDENCE = {
    "PUBLISHED_FULL_INTERVIEW_TRANSCRIPT",
    "VERBATIM_EXCERPT_ON_OPERATOR_SITE",
    "PUBLISHED_OPERATOR_VIDEO_EXCERPT",
    "OFFICIAL_VIDEO_DESCRIPTION_ONLY_NO_FULL_TRANSCRIPT",
    "OFFICIAL_TUTORIAL_TITLE_ONLY",
}
OWNER_HOSTS = {"ringba.com", "www.ringba.com", "adamyoung.com", "support.ringbax.com"}
CASE_HOSTS = {"www.ringba.com", "www.performcb.com", "unik360.beehiiv.com"}
ALLOWED_IDS = {
    "leadsmart_traffic", "adam_full_interview", "ringba_partner_management",
    "ringba_account_manager", "ringba_journey", "ringbax_call_logs",
    "ringbax_seller_tree",
}
CATEGORIES = {
    "SEARCH_ACQUISITION", "SOCIAL_ACQUISITION", "ORGANIC_CONTENT",
    "ATTRIBUTION", "COMPLIANT_CREATIVE", "BUYER_QA",
    "ALTERNATIVE_SOURCE_DISCOVERY", "PUBLISHER_GOVERNANCE",
    "BUYER_GOVERNANCE", "ACCESS_GOVERNANCE", "REPORTING",
    "EXPERT_INTERVIEW_RESEARCH", "CHANNEL_SOURCE_RULES",
    "ROUTING_RESEARCH",
}


def _url(url: str, host_allowlist: set[str]) -> str:
    if not isinstance(url, str) or not 20 <= len(url) <= 440:
        raise ValueError("invalid evidence URL")
    p = urlsplit(url)
    if (p.scheme != "https" or p.hostname not in host_allowlist
            or p.username or p.password or p.port is not None or p.fragment):
        raise ValueError("off-allowlist official evidence URL")
    return url


def _video(url: str) -> str:
    _url(url, {"www.youtube.com"})
    p = urlsplit(url)
    ids = p.query.split("&")
    if (p.path != "/watch" or len(ids) != 1 or not ids[0].startswith("v=")
            or not re.fullmatch("[A-Za-z0-9_-]{11}", ids[0][2:])):
        raise ValueError("invalid direct YouTube watch ID")
    return ids[0][2:]


def build_research(source: dict, *, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("review clock must be aware")
    now = now.astimezone(timezone.utc)
    if (not isinstance(source, dict) or source.get("schema_version") != INPUT_SCHEMA
            or source.get("vertical") != "US_HOME_SERVICES_PAY_PER_CALL"):
        raise ValueError("untrusted video research")
    reviewed = datetime.fromisoformat(source["reviewed_at_utc"].replace("Z", "+00:00"))
    if reviewed.tzinfo is None or reviewed > now:
        raise ValueError("review timestamp invalid")
    videos = source.get("videos")
    if not isinstance(videos, list) or len(videos) != len(ALLOWED_IDS):
        raise ValueError("incomplete original video review")
    identifiers = set()
    video_ids = set()
    ordered = []
    transcript_count = 0
    for video in videos:
        if not isinstance(video, dict) or video.get("id") not in ALLOWED_IDS:
            raise ValueError("unknown operator video")
        ident = video["id"]
        if ident in identifiers:
            raise ValueError("duplicate video")
        identifiers.add(ident)
        youtube_id = _video(video["youtube_url"])
        if youtube_id in video_ids:
            raise ValueError("duplicate YouTube URL")
        video_ids.add(youtube_id)
        _url(video["owner_url"], OWNER_HOSTS)
        if video.get("evidence_type") not in EVIDENCE:
            raise ValueError("missing transcript disclosure")
        if not isinstance(video.get("insights"), list) or not 1 <= len(video["insights"]) <= 4:
            raise ValueError("unbounded video claims")
        if any(not isinstance(s, str) or not 30 <= len(s) <= 400 for s in video["insights"]):
            raise ValueError("missing explicit public claims")
        if (not isinstance(video.get("classifications"), list)
                or any(k not in CATEGORIES for k in video["classifications"])):
            raise ValueError("unreviewed video taxonomy")
        if type(video.get("priority")) is not int or not 1 <= video["priority"] <= 7:
            raise ValueError("bad review order")
        if not video.get("target_owner") or not video.get("age_scope"):
            raise ValueError("missing owner or historical caveat")
        transcript_count += int(video["evidence_type"] == "PUBLISHED_FULL_INTERVIEW_TRANSCRIPT")
        ordered.append({
            **video, "youtube_id": youtube_id,
            "full_youtube_video_verified_watched": False,
            "full_transcript_available": video["evidence_type"] == "PUBLISHED_FULL_INTERVIEW_TRANSCRIPT",
            "claims_audited_independently": False,
            "current_channel_profits_verified": False,
        })
    if identifiers != ALLOWED_IDS or {v["priority"] for v in ordered} != set(range(1, 8)):
        raise ValueError("video set must be complete")
    cases = source.get("external_case_evidence")
    if not isinstance(cases, list) or len(cases) != 3:
        raise ValueError("missing operator case cross-checks")
    case_data = []
    for item in cases:
        _url(item.get("source_url"), CASE_HOSTS)
        if (not isinstance(item.get("findings"), list)
                or not 1 <= len(item["findings"]) <= 4
                or any(not isinstance(v, str) or len(v) < 30 for v in item["findings"])):
            raise ValueError("unsupported case claim")
        case_data.append(item)
    actions = source.get("prioritized_actions")
    if (not isinstance(actions, list) or len(actions) != 5
            or [a.get("rank") for a in actions] != list(range(1, 6))
            or any(not a.get("owner") or not a.get("testable_evidence") for a in actions)):
        raise ValueError("missing original owner handoff")
    gates = source.get("controls")
    if (not isinstance(gates, dict) or len(gates) != 9
            or any(v is not False for v in gates.values())):
        raise ValueError("research cannot approve activity")
    missing = source.get("observed_results")
    if (not isinstance(missing, dict) or len(missing) != 4
            or any(v is not None for v in missing.values())):
        raise ValueError("marketing claims are not actual operator economics")
    return {
        "schema_version": SCHEMA, "mode": "OBSERVE",
        "reviewed_at_utc": reviewed.isoformat(),
        "generated_at": now.isoformat(),
        "video_count": len(ordered),
        "full_published_transcript_count": transcript_count,
        "case_source_count": len(case_data),
        "video_watchlist": sorted(ordered, key=lambda v: v["priority"]),
        "operator_case_evidence": case_data,
        "owner_research_actions": actions,
        "full_video_playback_claimed": False,
        "self_reported_results_not_own_revenue": True,
        "live_competitor_traffic_share_established": False,
        "buyer_specific_source_approved": False,
        "seo_publication_authorized": False,
        "paid_traffic_authorized": False,
        "outbound_authorized": False,
        "new_agent_or_database": False,
        "execution_authority": "none",
    }


def refresh(root: Path) -> dict:
    original = json.loads((root / SOURCE).read_text(encoding="utf-8"))
    report = build_research(original)
    dst = root / DEST
    if not dst.parent.is_dir() or dst.parent.is_symlink() or dst.is_symlink():
        raise ValueError("unsafe original competitive intelligence directory")
    fd, tmp = tempfile.mkstemp(prefix=".yt-ppc-study-", dir=dst.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as writer:
            json.dump(report, writer, indent=2, sort_keys=True)
            writer.write("\n")
            writer.flush()
            os.fsync(writer.fileno())
        os.replace(tmp, dst)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return report
