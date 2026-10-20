#!/usr/bin/env python3
"""Presence-only Agent Reach public-channel status for source routing.

This checks installation/doctor status but does not read site content,
export browser cookies, authenticate social accounts or dispatch research.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
from datetime import datetime, timezone

from empire_os.agent_tool_runtime import agent_reach_health

ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT/"runtime/a2a_commercial_signal_mining/agent_reach_public_channel_health_v1.json"
CHANNELS=("rss","web","reddit","linkedin","facebook","instagram","github","youtube")


def observe_health() -> dict:
    health=agent_reach_health()
    doctor=health.get("doctor",{}) if isinstance(health,dict) else {}
    if not isinstance(doctor,dict):
        doctor={}
    status={}
    for key in CHANNELS:
        row=doctor.get(key)
        stat=row.get("status") if isinstance(row,dict) else None
        status[key]={"status":stat if stat in ("ok","warn","off") else "not_checked"}
    return {
        "schema_version":"empire.a2a.agent_reach_public_channel_health.v1",
        "observed_at_utc":datetime.now(timezone.utc).isoformat(),
        "tool_installed":health.get("tool",{}).get("installed") is True,
        "tool_ready":health.get("tool",{}).get("ready") is True,
        "doctor":status,
        "probe_performed":False,
        "actual_fresh_source_retrieval_confirmed":False,
        "social_accounts_authenticated_for_a2a":False,
        "execution_authority":"NONE",
        "outbound_or_paid_actions":0,
        "private_credentials_serialised":False,
    }


def main() -> int:
    doc=observe_health()
    OUTPUT.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    if OUTPUT.is_symlink() or OUTPUT.parent.is_symlink():
        raise ValueError("UNSAFE_HEALTH_DESTINATION")
    fd, temp=tempfile.mkstemp(prefix=".reach_channel_health_",dir=OUTPUT.parent)
    try:
        os.fchmod(fd,0o600)
        with os.fdopen(fd,"w",encoding="utf-8") as f:
            json.dump(doc,f,indent=2,sort_keys=True)
            f.write("\n")
        os.replace(temp,OUTPUT)
    finally:
        if os.path.exists(temp):os.unlink(temp)
    print(json.dumps(doc,sort_keys=True))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
