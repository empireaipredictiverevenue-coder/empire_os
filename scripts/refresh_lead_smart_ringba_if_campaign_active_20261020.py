#!/usr/bin/env python3
"""Credential-isolated Ringba refresh only while the recognised roofing campaign runs.

The root-owned secret stays in /etc/empire_ringba.env and is used solely by
the existing restricted observer. No calls, new routing, payouts or notifications.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
import os
import stat

from empire_os.lead_smart_site_handoff import CAMPAIGN, NUMBER, CONFIG
from scripts.refresh_lead_smart_ringba_tracking_root_once_20261019 import refresh

SOURCE = "gmail:1a1551ac7204ff8a"

def run(*, path: Path = CONFIG, now: datetime | None = None, refresher=refresh) -> dict:
    report={"schema_version":"empire.lead_smart.ringba_campaign_refresh.v1",
            "credential_exposed":False,"calls_changed":False,
            "buyer_route_modified":False,"payout_modified":False}
    if os.geteuid()!=0:
        return {**report,"status":"HOLD_RESTRICTED_ROOT_ONLY"}
    try:
        if path.is_symlink() or not stat.S_ISREG(path.stat().st_mode):
            raise ValueError("untrusted_control")
        control=json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(control,dict):
            raise ValueError("untrusted_control")
        end=datetime.fromisoformat(str(control.get("ends_at","")).replace("Z","+00:00"))
        when=now or datetime.now(timezone.utc)
        if when.tzinfo is None or end.tzinfo is None:
            raise ValueError("invalid_date")
        active=(control.get("schema_version")=="empire.lead_smart.site_handoff_control.v1"
            and control.get("campaign_id")==CAMPAIGN
            and control.get("tracking_number")==NUMBER
            and control.get("enabled") is True
            and control.get("mode")=="FULL_CAMPAIGN"
            and control.get("buyer_live_authorization_ref")==SOURCE
            and control.get("traffic_source")=="EMPIRE_FIRST_PARTY_ORGANIC"
            and when.astimezone(timezone.utc)<end.astimezone(timezone.utc))
        if not active:
            return {**report,"status":"INACTIVE_NO_PROVIDER_REQUEST"}
    except (OSError,ValueError,TypeError,UnicodeError,json.JSONDecodeError):
        return {**report,"status":"HOLD_UNTRUSTED_CONTROL"}
    response=refresher(apply=True)
    if response.get("status")=="TRACKING_FRESH_NO_CALL_AUTHORITY" and response.get("tracking_verification_refreshed") is True:
        return {**report,"status":"TRACKING_REFRESHED"}
    return {**report,"status":"PROVIDER_REFRESH_UNVERIFIED"}

def main()->int:
    response=run()
    print(json.dumps(response,sort_keys=True))
    return 0 if response["status"] in ("TRACKING_REFRESHED","INACTIVE_NO_PROVIDER_REQUEST") else 2

if __name__=="__main__":
    raise SystemExit(main())
