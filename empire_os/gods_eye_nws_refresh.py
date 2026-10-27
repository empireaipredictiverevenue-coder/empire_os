"""Bounded automatic, private official NWS zone coverage for God's Eye.

Run ONLY from the existing Media OS research bridge (every ~30 minutes).
Coverage is an official NWS forecast/county zone -- NOT an event footprint,
damage map, buyer geography, commercial intent, or actionable lead.
"""
from __future__ import annotations

from datetime import datetime,timezone
from pathlib import Path
import json,os,stat,tempfile
from typing import Callable, Mapping,Any

from empire_os.gods_eye_nws_geojson import _time,_geometry,MAX_AGE
from empire_os.gods_eye_nws_zones import _zone_link,build_nws_advisory_zone_review
from scripts.review_gods_eye_nws_zones_once_20261027 import (
    ALERTS,MAX_ALERTS,MAX_ZONE_BYTES,_get,
)
OUTPUT=Path("runtime/media_os/last30days/nws_advisory_zones_latest.geojson")
MAX_FETCH=8
MAX_BYTES=4_000_000

def refresh_official_nws_coverage(
    repo_root:Path, *,
    now:datetime|None=None,
    get:Callable[[str,int],dict]=_get,
    enable_fetch:bool=True,
)->dict[str,Any]:
    """Network failures preserve old payload for read-time expiry enforcement."""
    if not repo_root.is_absolute() or repo_root.is_symlink():
        raise ValueError("canonical_absolute_root_required")
    if not enable_fetch:
        return {"status":"READ_ONLY_NO_NWS_REFRESH","fetched":False}
    clock=now or datetime.now(timezone.utc)
    if clock.tzinfo is None or clock.utcoffset() is None:
        raise ValueError("utc_clock_required")
    clock=clock.astimezone(timezone.utc)
    document=get(ALERTS,MAX_ALERTS)
    if (not isinstance(document,dict) or document.get("type")!="FeatureCollection"
        or not isinstance(document.get("features"),list)
        or len(document["features"])>2000):
        raise ValueError("official_alerts_invalid")
    urls=[];seen=set()
    for alert in document["features"][:200]:
        if not isinstance(alert,dict):continue
        p=alert.get("properties")
        if not isinstance(p,dict):continue
        sent,expires=_time(p.get("sent")),_time(p.get("expires"))
        if (sent is None or expires is None or sent>clock or expires<=clock
            or clock-sent>MAX_AGE or p.get("status")!="Actual"
            or _geometry(alert.get("geometry")) is not None):continue
        for ref in (p.get("affectedZones") or [])[:15]:
            if _zone_link(ref) and ref not in seen:
                seen.add(ref);urls.append(ref)
    responses={};failures=0
    for url in urls[:MAX_FETCH]:
        try:responses[url]=get(url,MAX_ZONE_BYTES)
        except (OSError,ValueError,TimeoutError,json.JSONDecodeError):
            failures+=1
    review=build_nws_advisory_zone_review(
        document,responses,now=clock,alerts_transport_verified=True,
        zone_transports_verified=True,
    )
    encoded=(json.dumps(review,sort_keys=True,separators=(",",":"))+"\n").encode()
    if len(encoded)>MAX_BYTES:raise ValueError("official_nws_private_export_too_large")
    target=repo_root/OUTPUT
    if target.is_symlink() or target.parent.is_symlink():
        raise ValueError("unsafe_private_nws_target")
    target.parent.mkdir(parents=True,exist_ok=True)
    fd,temp=tempfile.mkstemp(prefix=".gods-eye-nws-",suffix=".tmp",dir=target.parent)
    try:
        os.fchmod(fd,stat.S_IRUSR|stat.S_IWUSR)
        with os.fdopen(fd,"wb") as f:
            f.write(encoded);f.flush();os.fsync(f.fileno())
        os.replace(temp,target)
    finally:
        if os.path.exists(temp):os.unlink(temp)
    return {
        "status":review["empire_review"]["status"],
        "fetched":True,
        "zone_count":len(review["features"]),
        "alert_count":len(document["features"]),
        "official_zone_docs_read":len(responses),
        "official_zone_docs_failed":failures,
        "path":str(OUTPUT),
        "commercial_authority":"none",
        "public_publish_authorized":False,
    }
