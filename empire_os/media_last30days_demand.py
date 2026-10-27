"""Last30Days -> canonical Media OS research-pack adapter (offline, OBSERVE).

Reads *exports*, never launches the Last30Days engine, opens browsers, executes
retrieved instructions or depends on paid services. The Vane/OpenManus agents
own research execution and may provide a validated report through this boundary.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import ipaddress
import json
import os
import stat
from pathlib import Path
import re
from typing import Any, Mapping
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

from empire_os.media_research_pack import MediaResearchPack, MediaResearchSource

SCHEMA = "empire.media.last30days_demand_candidates.v1"
MAX_REPORT_BYTES = 2_000_000
MAX_CANDIDATES = 30
FRESH_DAYS = 30
MAX_REPORT_AGE = timedelta(hours=48)
THEMES = (
    "AI agents for small businesses",
    "AI lead generation for roofing contractors",
    "AI sales avatars and digital sales agents",
    "first-party revenue intelligence and attribution",
)
# These source classes are chosen for genuinely relevant fresh public
# discussions, not a representation of the full Last30Days source catalog.
_DOMAINS = {
    "reddit": ("reddit.com", "redd.it"),
    "youtube": ("youtube.com", "youtu.be"),
    "hackernews": ("news.ycombinator.com",),
    "github": ("github.com",),
    "web": (),
}
_STATUSES = frozenset({
    "ok", "no-results", "partial", "rate-limited", "auth-failed",
    "unreachable", "timeout", "schema-drift", "skipped-unconfigured",
    "error",
})
_SLUG_RE = re.compile(r"^[a-zA-Z0-9 :&/'.,+()\-]{5,110}$")


def _time(value: Any, *, allow_date_only: bool = False) -> datetime | None:
    if not isinstance(value, str) or len(value) > 48:
        return None
    text = value.strip()
    # The real Last30Days source exports YYYY-MM-DD (not timestamp) on
    # Reddit/Hacker News. Treat date precision explicitly as UTC midnight;
    # the *report* generated_at still requires a timezone-aware timestamp.
    if allow_date_only and re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        try:
            return datetime.fromisoformat(text).replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    try:
        moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if moment.tzinfo is None or moment.utcoffset() is None:
        return None
    return moment.astimezone(timezone.utc)


def _safe_text(value: Any, limit: int) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join("".join(c for c in value if c.isprintable()).split())[:limit]


def _canon_url(raw_url: Any, source: str) -> str | None:
    if not isinstance(raw_url, str) or len(raw_url) > 1024:
        return None
    try:
        part = urlsplit(raw_url)
        host = part.hostname
        port = part.port
    except ValueError:
        return None
    if (part.scheme != "https" or not host or part.username or part.password
            or port not in (None, 443) or part.fragment):
        return None
    host = host.lower()
    if (
        not re.fullmatch(r"[a-z0-9.-]+", host)
        or "." not in host or ".." in host
        or host in ("localhost",)
        or host.endswith((".local", ".localhost", ".internal", ".invalid", ".test"))
    ):
        return None
    try:
        ipaddress.ip_address(host)
        return None
    except ValueError:
        pass  # accepted host is a public-looking DNS name, not an IP literal
    base = _DOMAINS.get(source)
    if base is None:
        return None
    # Hacker News export results often point to the *linked external article*,
    # not news.ycombinator.com. Preserve that honest role without inferring
    # the article's author is the HN poster, or that an HN URL was observed.
    if source not in ("hackernews", "web") and base and not any(
        host == h or host.endswith("." + h) for h in base
    ):
        return None
    if not part.path or any(x in part.path for x in ("\\", "\r", "\n")):
        return None
    if len(part.path) > 420:
        return None
    # Strip promotional query strings and all tracking identifiers.
    query = ""
    if source == "youtube" and host.endswith("youtube.com") and part.path == "/watch":
        values = parse_qs(part.query)
        candidate = values.get("v", [])
        if len(candidate) != 1 or not re.fullmatch(r"[A-Za-z0-9_-]{11}", candidate[0]):
            return None
        query = urlencode({"v": candidate[0]})
    if source == "youtube" and host == "youtu.be":
        if not re.fullmatch(r"/[A-Za-z0-9_-]{11}", part.path):
            return None
    return urlunsplit(("https", host, part.path.rstrip("/") or "/", query, ""))


def build_last30days_media_candidates(
    report: Mapping[str, Any] | None,
    *, now: datetime,
    expected_topic: str | None = None,
) -> dict[str, Any]:
    """Adapt the Last30Days v1.2 --emit=json agent export, never its prose.

    Any missing, outdated or invalid report fails to UNKNOWN. A valid empty
    report may indicate no matched candidates, but only an individual source
    explicitly reporting 'no-results' supports calling that source quiet.
    """
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("last30days_utc_clock_required")
    now = now.astimezone(timezone.utc)
    result = {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "source_available": False,
        "source_state": "NOT_CONNECTED",
        "source_schema_version": None,
        "topic": None,
        "observed_at": None,
        "source_status": {},
        "coverage_complete": False,
        "candidate_count": 0,
        "source_observation_count": 0,
        "candidates": [],
        "discarded": {"undated_or_stale": 0, "invalid_url_or_source": 0, "duplicate": 0, "invalid_shape": 0},
        "verified_claim_count": 0,
        "script_ready_count": 0,
        "verified_buyer_demand": None,
        "actual_youtube_search_volume": None,
        "original_rights_reviewed": False,
        "research_text_is_untrusted_instructions": True,
        "automatic_video_creation_authorized": False,
        "public_publish_authorized": False,
        "execution_authority": "none",
    }
    if report is None:
        return result
    if not isinstance(report, Mapping) or report.get("schema_version") != "1.2":
        result["source_state"] = "UNSUPPORTED_OR_LEGACY_SOURCE_FORMAT"
        return result
    generated = _time(report.get("generated_at"))
    if generated is None or generated > now + timedelta(minutes=5) or now - generated > MAX_REPORT_AGE:
        result["source_state"] = "MISSING_OR_STALE_REPORT_TIMESTAMP"
        return result
    topic = _safe_text(report.get("query"), 110)
    if not _SLUG_RE.fullmatch(topic):
        result["source_state"] = "INVALID_OR_MISSING_QUERY"
        return result
    if expected_topic is not None and topic.casefold() != expected_topic.casefold():
        result["source_state"] = "TOPIC_MISMATCH"
        return result
    if report.get("window_days") != 30:
        result["source_state"] = "NON_30_DAY_WINDOW"
        return result
    raw_status = report.get("source_status")
    if not isinstance(raw_status, Mapping) or len(raw_status) > 30:
        result["source_state"] = "SOURCE_COVERAGE_UNKNOWN"
        return result
    statuses: dict[str,str] = {}
    for key,value in raw_status.items():
        if not isinstance(key,str) or len(key)>40:
            result["source_state"] = "SOURCE_COVERAGE_INVALID"
            return result
        statuses[key] = value if isinstance(value,str) and value in _STATUSES else "unknown"
    result.update({
        "source_available": True,
        "source_schema_version": "last30days.agent_export.v1.2",
        "topic": topic,
        "observed_at": generated.isoformat(),
        "source_status": statuses,
        "coverage_complete": bool(statuses) and all(
            v in ("ok", "no-results") for v in statuses.values()
        ),
    })
    entries = report.get("results")
    if not isinstance(entries, list) or len(entries) > 300:
        result["source_state"] = "REPORT_RESULTS_INVALID"
        result["source_available"] = False
        return result
    source_rows = []
    snippets = []
    seen: set[str] = set()
    for row in entries:
        if not isinstance(row, Mapping):
            result["discarded"]["invalid_shape"] += 1
            continue
        source = row.get("source")
        if source not in _DOMAINS:
            result["discarded"]["invalid_url_or_source"] += 1
            continue
        url = _canon_url(row.get("url"), source)
        if url is None:
            result["discarded"]["invalid_url_or_source"] += 1
            continue
        stamp = _time(row.get("published_at"), allow_date_only=True)
        if stamp is None or stamp > generated + timedelta(days=1) or stamp > now or now - stamp > timedelta(days=FRESH_DAYS):
            result["discarded"]["undated_or_stale"] += 1
            continue
        if url in seen:
            result["discarded"]["duplicate"] += 1
            continue
        title = _safe_text(row.get("title"), 150)
        if not title:
            result["discarded"]["invalid_shape"] += 1
            continue
        seen.add(url)
        ref = "last30days:source:" + hashlib.sha256(url.encode()).hexdigest()[:24]
        role = ("hackernews_linked_external_article"
                if source == "hackernews" and urlsplit(url).hostname != "news.ycombinator.com"
                else source)
        source_rows.append(MediaResearchSource(
            source_ref=ref, source_type=f"public_recent_{role}",
            observed_at=generated.isoformat(), lineage_ref=url,
            rights_state="PUBLIC_RESEARCH_REFERENCE_ONLY",
        ))
        snippets.append({
            "source_ref": ref, "title": title,
            "summary": _safe_text(row.get("summary"), 300),
            "published_at": stamp.isoformat(),
            "source": source, "source_url": url,
            "source_url_role": role,
            "engagement": {
                k: v for k,v in (row.get("engagement") or {}).items()
                if isinstance(k,str) and k in ("views","likes","comments","points","score")
                and type(v) in (int,float) and 0<=v<=1_000_000_000
            } if isinstance(row.get("engagement"),Mapping) else {},
            "untrusted_public_observation": True,
            "independent_claim_verification_required": True,
        })
        if len(source_rows) >= MAX_CANDIDATES:
            break
    if not source_rows:
        result["source_state"] = (
            "NO_VALID_RECENT_SOURCE_ITEMS"
            if entries else "NO_MATCHES_WITH_REPORTED_SOURCE_COVERAGE"
        )
        return result
    key = hashlib.sha256(f"{topic.casefold()}|{generated.isoformat()}".encode()).hexdigest()[:16]
    research = MediaResearchPack(
        research_id=f"media-research:last30days:{key}",
        topic=topic,
        thesis=f"Investigate public audience questions and unverified recent discussion around {topic}.",
        audience="Empire AI relevant business owners and operators",
        sources=tuple(source_rows),
        claims=(),
        uncertainty=(
            "Last30Days public discussion is an observation, not buyer-demand proof.",
            "YouTube search volume, commercial conversions and revenue are UNKNOWN.",
            "Third-party text is untrusted and may never be executed as agent instructions.",
            "Source coverage may be partial; no-results differs from timeout or authentication failure.",
        ),
        generated_at=generated.isoformat(),
    ).as_dict(now=now)
    research.update({
        "opportunity_class": "RECENT_PUBLIC_DISCUSSION_REQUIRES_CORROBORATION",
        "source_observation_count": len(source_rows),
        "source_snippets": snippets,
        "verified_claim_count": 0,
        "claim_verification_required": True,
        "script_ready": False,
        "source_observations_are_verified_facts": False,
        "automatic_script_generation_authorized": False,
        "public_publish_authorized": False,
        "execution_authority": "none",
    })
    result.update({
        "source_state": "OBSERVED_CANDIDATES_NOT_VERIFIED_DEMAND",
        "candidate_count": 1, "source_observation_count": len(source_rows),
        "candidates": [research],
    })
    return result


def read_last30days_export(path: Path, *, now: datetime, expected_topic: str | None = None) -> dict[str, Any]:
    """Bounded explicit file read, not arbitrary dynamic discovery or network."""
    if not isinstance(path, Path) or not path.is_absolute() or path.is_symlink():
        return build_last30days_media_candidates(None, now=now)
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except OSError:
        return build_last30days_media_candidates(None, now=now)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_REPORT_BYTES:
            raise ValueError("last30days_export_exceeds_size_limit_or_not_regular")
        with os.fdopen(fd, "r", encoding="utf-8") as reader:
            fd = -1
            record = json.load(reader)
    except (ValueError, UnicodeError):
        result = build_last30days_media_candidates(None, now=now)
        result["source_state"] = "UNREADABLE_EXPORT"
        return result
    finally:
        if fd >= 0:
            os.close(fd)
    # Old per-topic agent artifacts wrap an incompatible dict-of-source-lists.
    # Never interpret those as complete, date-verified v1.2 agent exports.
    if isinstance(record,Mapping) and record.get("engine")=="last30days" and "data" in record:
        record = record["data"]
    return build_last30days_media_candidates(record, now=now, expected_topic=expected_topic)
