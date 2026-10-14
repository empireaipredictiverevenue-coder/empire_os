"""First-party YouTube campaign landing observation: opt-in deploy only.

This is NOT unique-visitor analytics, consent/legal clearance, verified lead
capture or revenue. No cookies, pixels, referrer/IP/UA persistence or identities.
The router factory is deliberately *unmounted* and disabled by default.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import stat
from typing import Any, Mapping

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from empire_os.media_youtube_campaign_tracking import make_owned_youtube_campaign_link
from empire_os.owned_campaign_http import IntakeLimiter

_ORIGIN = "https://empire-ai.co.uk"
_FIELDS = frozenset({"campaign", "video_ref", "placement", "destination_path", "landing_url"})
_SQL = """CREATE TABLE IF NOT EXISTS youtube_landing_daily (
    day TEXT NOT NULL,
    tracking_key TEXT NOT NULL,
    campaign TEXT NOT NULL,
    video_ref TEXT NOT NULL,
    placement TEXT NOT NULL,
    landing_beacons INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY(day, tracking_key)
)"""


def _validate_ledger_path(path: Path) -> None:
    if not isinstance(path, Path) or not path.is_absolute() or path.is_symlink():
        raise ValueError("youtube_landing_ledger_path_invalid")
    parent = path.parent
    if not parent.is_dir() or parent.is_symlink() or (parent.stat().st_mode & 0o077) != 0:
        raise ValueError("youtube_landing_private_directory_required")
    if path.exists():
        mode = path.stat().st_mode
        if not stat.S_ISREG(mode) or (mode & 0o077):
            raise ValueError("youtube_landing_ledger_not_private")


def _session(path: Path):
    _validate_ledger_path(path)
    # Atomic 0600 create in an already private directory. Do NOT change the
    # process-wide umask in a multi-threaded ASGI server.
    import os
    if not path.exists():
        try:
            descriptor = os.open(
                path,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
                0o600,
            )
            os.close(descriptor)
        except FileExistsError:
            _validate_ledger_path(path)
    connection = sqlite3.connect(path, isolation_level=None, timeout=2)
    connection.execute("PRAGMA busy_timeout=2000")
    return connection


def _validate_registry(approved_links: Mapping[str, Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    if not isinstance(approved_links, Mapping) or not approved_links:
        raise ValueError("youtube_landing_approved_registry_required")
    verified={}
    for key, data in approved_links.items():
        if not isinstance(key,str) or not isinstance(data,Mapping):
            raise ValueError("youtube_landing_registry_invalid")
        link=make_owned_youtube_campaign_link(
            campaign=data.get("campaign"),
            video_ref=data.get("video_ref"),
            placement=data.get("placement"),
            destination_path=data.get("destination_path"),
        )
        if key != link["tracking_key"] or data.get("url") != link["url"]:
            raise ValueError("youtube_landing_registry_invalid")
        verified[key]=link
    return verified


def _validate_landing(payload: Any, registry: Mapping[str, Mapping[str,Any]]) -> dict[str,Any]:
    if not isinstance(payload,dict) or set(payload) != _FIELDS:
        raise ValueError("youtube_landing_payload_fields_invalid")
    link=make_owned_youtube_campaign_link(
        campaign=payload["campaign"],video_ref=payload["video_ref"],
        placement=payload["placement"],destination_path=payload["destination_path"],
    )
    if payload["landing_url"] != link["url"]:
        raise ValueError("youtube_landing_url_does_not_match_campaign")
    key=link["tracking_key"]
    if key not in registry or registry[key]["url"] != link["url"]:
        raise ValueError("youtube_landing_unknown_or_unapproved_campaign")
    return link


def build_youtube_landing_router(
    *, enabled: bool = False, approved_links: Mapping[str,Mapping[str,Any]] | None = None,
    ledger_path: Path | None = None,
) -> APIRouter:
    """Preparation only; route not automatically installed into public gateway."""
    router = APIRouter(tags=["media-youtube-measurement"])
    if enabled:
        if ledger_path is None:
            raise ValueError("youtube_landing_ledger_explicit_path_required")
        _validate_ledger_path(ledger_path)
        registry=_validate_registry(approved_links)
    else:
        registry={}
    limiter=IntakeLimiter()

    @router.post("/api/media/youtube/landing")
    async def collect_landing(request: Request):
        headers={"Cache-Control":"no-store", "Referrer-Policy":"no-referrer"}
        def deny(reason: str, status: int):
            return JSONResponse({"accepted":False,"error":reason},status_code=status,headers=headers)
        if enabled is not True:
            return deny("youtube_landing_collection_disabled",503)
        if (
            request.headers.get("origin") != _ORIGIN
            or request.headers.get("sec-fetch-site") not in ("same-origin","none")
        ):
            return deny("same_origin_required",403)
        if request.headers.get("content-type","").split(";")[0].strip().lower() != "application/json":
            return deny("json_required",415)
        if not limiter.allow(request.client.host if request.client else "unknown", "event"):
            return deny("rate_limited",429)
        raw=await request.body()
        if len(raw)>1800:
            return deny("request_too_large",413)
        try:
            payload=json.loads(raw)
            link=_validate_landing(payload,registry)
            day=datetime.now(timezone.utc).date().isoformat()
            con=_session(ledger_path)
            try:
                con.execute("BEGIN IMMEDIATE")
                con.execute(_SQL)
                con.execute(
                    "INSERT INTO youtube_landing_daily "
                    "(day,tracking_key,campaign,video_ref,placement,landing_beacons) "
                    "VALUES (?,?,?,?,?,1) "
                    "ON CONFLICT(day,tracking_key) DO UPDATE SET "
                    "landing_beacons=landing_beacons+1",
                    (day,link["tracking_key"],link["campaign"],link["video_ref"],link["placement"]),
                )
                con.execute("COMMIT")
            finally:
                con.close()
        except (ValueError, TypeError, sqlite3.Error):
            return deny("invalid_or_unavailable_youtube_landing",422)
        return JSONResponse(
            {"accepted":True,
             "classification":"UNIQUE_PEOPLE_UNKNOWN_NONPERSONAL_PAGE_LOAD_BEACON",
             "click_proven":False,"enquiry_proven":False,
             "revenue_proven":False,"public_publish_authorized":False},
            status_code=202,headers=headers,
        )
    return router


def read_landing_aggregate(*, ledger_path: Path | None) -> dict[str,Any]:
    """Offline owner-only read. Never serves individual visitor data."""
    if ledger_path is None or not ledger_path.exists():
        return {
            "schema_version":"empire.media.youtube_aggregate_landing_observation.v1",
            "status":"NO_LANDING_LEDGER",
            "observed_beacons":None,
            "unique_visitors":None,
            "verified_enquiries":None,
            "recognized_revenue":None,
            "breakdown":[],
            "execution_authority":"none",
        }
    _validate_ledger_path(ledger_path)
    # Open an existing db only, never create via an owner-only read path.
    db=sqlite3.connect("file:"+str(ledger_path)+"?mode=ro",uri=True)
    try:
        total=db.execute(
            "SELECT COALESCE(SUM(landing_beacons),0) FROM youtube_landing_daily"
        ).fetchone()[0]
        categories=db.execute(
            "SELECT COUNT(*) FROM (SELECT 1 FROM youtube_landing_daily GROUP BY tracking_key)"
        ).fetchone()[0]
        rows=db.execute(
            "SELECT tracking_key,campaign,video_ref,placement,"
            "SUM(landing_beacons) FROM youtube_landing_daily "
            "GROUP BY tracking_key,campaign,video_ref,placement "
            "ORDER BY 5 DESC LIMIT 250"
        ).fetchall()
    finally:
        db.close()
    return {
        "schema_version":"empire.media.youtube_aggregate_landing_observation.v1",
        "status":"OBSERVED_UNVERIFIED_BROWSER_BEACONS",
        "observed_beacons":int(total),
        "breakdown_truncated":categories > len(rows),
        "unique_visitors":None,
        "verified_enquiries":None,
        "recognized_revenue":None,
        "breakdown":[{
            "tracking_key":key,"campaign":campaign,"video_ref":video,
            "placement":placement,"landing_beacons":n,
        } for key,campaign,video,placement,n in rows],
        "execution_authority":"none",
    }
