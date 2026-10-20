#!/usr/bin/env python3
"""Deploy an explicit, bounded recurring Lead Smart Direct roofing campaign.

--preview is read only; --stage writes a DISABLED configuration; --activate
requires source-backed preflight, a verified auto-stop and buyer hours.
This never purchases traffic, changes Ringba routes or certifies revenue.
"""
from __future__ import annotations
import argparse
import json
import subprocess
from pathlib import Path
from datetime import datetime,timedelta,timezone
from zoneinfo import ZoneInfo
from empire_os.lead_smart_site_handoff import CAMPAIGN,NUMBER,CONFIG,LEDGER,_control
from scripts.activate_lead_smart_supervised_retry import change_control
from scripts.disable_lead_smart_pilot_control import stop_control
from scripts.materialize_lead_smart_launch_readiness import (
    compute_live_launch_readiness,founder_full_campaign_approved,
)
from scripts.refresh_lead_smart_full_campaign_sources import refresh,ROOT,PYTHON

PROJECT_ROOT=Path(__file__).resolve().parents[1]
CHICAGO=ZoneInfo("America/Chicago")
SOURCE="gmail:1a1551ac7204ff8a"
DIRECTIVE="docs/evidence/lead_smart_full_campaign_founder_directive_20261020.json"

def campaign_window(start_local:str,days:int):
    if type(days) is not int or not 1<=days<=14:
        raise ValueError("days must be 1-14")
    start=datetime.fromisoformat(start_local)
    if start.tzinfo is not None or start.minute or start.second or start.hour!=8:
        raise ValueError("start must be a Chicago local day opening at 08:00")
    start=start.replace(tzinfo=CHICAGO)
    end=start+timedelta(days=days)
    # End is the next local morning, accounting for daylight-saving transitions.
    return start.astimezone(timezone.utc),end.astimezone(timezone.utc)

def proposed(previous,from_local,days,daily,total):
    if (previous.get("enabled") is not False
            or previous.get("campaign_id")!=CAMPAIGN
            or previous.get("tracking_number")!=NUMBER
            or previous.get("stop_method")!="atomic_site_handoff_gate"):
        raise ValueError("not a disabled known Lead Smart control")
    if (type(daily) is not int or type(total) is not int
            or not 1<=daily<=1000 or not daily<=total<=10000):
        raise ValueError("invalid daily/total limits")
    start,end=campaign_window(from_local,days)
    if (end-start).total_seconds()>14*86400:
        # A DST-end 14-day local period may run one extra UTC hour.
        raise ValueError("date range exceeds 14-day bounded campaign maximum")
    return {
        **previous,"mode":"FULL_CAMPAIGN","enabled":False,
        "starts_at":start.isoformat(),"ends_at":end.isoformat(),
        "max_site_handoffs":total,"max_daily_site_handoffs":daily,
        "founder_authority_ref":DIRECTIVE,
        "buyer_live_authorization_ref":SOURCE,
        "traffic_source":"EMPIRE_FIRST_PARTY_ORGANIC",
    }

def _timer(unit,when_seconds,command,repeat=False):
    if not 1<=when_seconds<=14*86400:
        raise ValueError("invalid timer range")
    args=["sudo","-n","systemd-run","--unit="+unit,
          "--on-active="+str(when_seconds)+"s",
          "--timer-property=AccuracySec=1s" if not repeat else
             "--timer-property=AccuracySec=60s",
          "--property=WorkingDirectory=/srv/empire_os",
          "--property=User=ubuntu"]
    if repeat:
        args.append("--on-unit-active="+str(when_seconds)+"s")
    args.extend([str(PYTHON),"-B","-m",command])
    if not repeat:
        args.append("--apply")
    subprocess.run(args,cwd=ROOT,check=True,timeout=25,
                   capture_output=True,text=True)
    subprocess.run(["systemctl","is-active","--quiet",unit+".timer"],
                   check=True,timeout=10)

def stage(from_local,days=7,daily=20,total=140,apply=False):
    current=json.loads(CONFIG.read_text())
    new=proposed(current,from_local,days,daily,total)
    if not founder_full_campaign_approved(root=PROJECT_ROOT):
        raise ValueError("founder campaign directive not deployed/verified")
    if LEDGER.exists():
        raise ValueError("existing handoff ledger must be reconciled before new window")
    out={"status":"STAGED_DISABLED" if apply else "PREVIEW_ONLY",
         "mode":"FULL_CAMPAIGN","start":new["starts_at"],
         "end":new["ends_at"],"daily_handoff_limit":daily,
         "total_handoff_limit":total,"calls_enabled":False,
         "buyer_go_ahead_source":SOURCE,"organic_only":True}
    if apply:
        change_control(current,new)
    return out

def activate():
    current=json.loads(CONFIG.read_text())
    if (current.get("mode")!="FULL_CAMPAIGN"
            or current.get("enabled") is not False):
        raise ValueError("full campaign must first be staged disabled")
    if not founder_full_campaign_approved(root=PROJECT_ROOT):
        raise ValueError("founder campaign directive missing")
    now=datetime.now(timezone.utc)
    _control({**current,"enabled":True},now)
    # A genuine upstream observer refresh, not a fabricated freshness reset.
    refreshed=refresh()
    if not refreshed["source_refresh_completed"]:
        raise ValueError("real source refresh failed; campaign stays OFF")
    check=compute_live_launch_readiness()
    if check["blockers"]!=["pilot_stop_verified"]:
        raise ValueError("launch held: "+json.dumps(check["blockers"]))
    stop_unit="empire-roofing-campaign-stop-"+now.strftime("%Y%m%d%H%M%S")
    refresh_unit="empire-roofing-campaign-sources-"+now.strftime("%Y%m%d%H%M%S")
    seconds=int((datetime.fromisoformat(current["ends_at"])-datetime.now(timezone.utc)).total_seconds())-20
    if seconds<60:raise ValueError("campaign window has expired")
    _timer(stop_unit,seconds,"scripts.disable_lead_smart_pilot_control")
    # Source freshness continues being observed, while the original API
    # independently holds calls if any verification becomes stale/missing.
    try:
        _timer(refresh_unit,1800,"scripts.refresh_lead_smart_full_campaign_sources",True)
        _control({**current,"enabled":True},datetime.now(timezone.utc))
        change_control(current,{**current,"enabled":True})
        ready=compute_live_launch_readiness()
        if not ready["launch_ready"]:
            raise RuntimeError("post activation readiness held: "+json.dumps(ready["blockers"]))
        return {"status":"LIVE_FULL_CAMPAIGN","calls_enabled":True,
                "max_daily_site_handoffs":current["max_daily_site_handoffs"],
                "max_site_handoffs":current["max_site_handoffs"],
                "stops_at":current["ends_at"],
                "stop_timer":stop_unit+".timer",
                "refresh_timer":refresh_unit+".timer"}
    except BaseException:
        stop_control(apply=True)
        raise

def main():
    p=argparse.ArgumentParser()
    g=p.add_mutually_exclusive_group(required=True)
    g.add_argument("--preview",action="store_true")
    g.add_argument("--stage",action="store_true")
    g.add_argument("--activate",action="store_true")
    g.add_argument("--stop",action="store_true")
    p.add_argument("--start-chicago",default=None,
                   help="YYYY-MM-DDT08:00 Chicago local start")
    p.add_argument("--days",type=int,default=7)
    p.add_argument("--daily-site-handoffs",type=int,default=20)
    p.add_argument("--total-site-handoffs",type=int,default=140)
    a=p.parse_args()
    try:
        if a.stop:
            result=stop_control(apply=True)
        elif a.activate:
            result=activate()
        else:
            start=a.start_chicago
            if start is None:
                start=datetime.now(CHICAGO).strftime("%Y-%m-%dT08:00")
            result=stage(start,a.days,a.daily_site_handoffs,
                         a.total_site_handoffs,apply=a.stage)
        print(json.dumps(result,sort_keys=True))
        return 0
    except (ValueError,RuntimeError,OSError,subprocess.SubprocessError,
            json.JSONDecodeError) as exc:
        print(json.dumps({"status":"HELD","calls_enabled":False,
                          "reason":str(exc)},sort_keys=True))
        return 2

if __name__=="__main__":
    raise SystemExit(main())
