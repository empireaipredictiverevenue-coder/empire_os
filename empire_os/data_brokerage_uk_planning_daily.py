"""Original Empire Data Brokerage daily planning-source owned research lane."""
from __future__ import annotations
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import fcntl
import json
import os
import re
import stat
import requests
from empire_os import data_brokerage_uk_roofing_pilot as pilot

ROOT=Path("/srv/empire_os/runtime/data_brokerage")
STATE=ROOT/"uk_planning_daily_refresh_state.json"
QUALITY=ROOT/"uk_planning_qualification_comparison_latest.json"
QUALITY_MD=ROOT/"uk_planning_qualification_comparison_latest.md"
LOCK=ROOT/".uk_planning_daily_refresh.lock"
BRANCH="https://api.github.com/repos/PlanIndex/uk-planning-applications/branches/main"
SCHEMA="empire.data_brokerage.uk_planning_daily_refresh.v1"
QUALITY_SCHEMA="empire.data_brokerage.uk_planning_quality_comparison.v1"
MAX_REQUESTS=22

class DailyHold(ValueError):pass
def check(value,reason):
    if not value:raise DailyHold(reason)

def branch_sha(*,request=None):
    get=request or requests.get
    response=get(BRANCH,timeout=(4,9),allow_redirects=False,
        headers={"Accept":"application/vnd.github+json",
                 "User-Agent":"EmpireAI-OriginalBrokerageResearch/1.0"})
    check(response.status_code==200 and
          10<len(response.content)<=16000,"PLANINDEX_COMMIT_REQUEST_HELD")
    try:sha=response.json()["commit"]["sha"]
    except (KeyError,TypeError,ValueError) as e:raise DailyHold("PLANINDEX_COMMIT_PAYLOAD_INVALID") from e
    check(type(sha) is str and re.fullmatch("[a-f0-9]{40}",sha) is not None,
          "PLANINDEX_BRANCH_SHA_INVALID")
    return sha

def previous_state():
    if not STATE.exists():return None
    check(STATE.is_file() and not STATE.is_symlink() and
          STATE.stat().st_uid==os.geteuid() and
          stat.S_IMODE(STATE.stat().st_mode)==0o600 and
          0<STATE.stat().st_size<=10000,"ORIGINAL_DAILY_STATE_UNTRUSTED")
    try:state=json.loads(STATE.read_bytes())
    except (ValueError,OSError) as e:raise DailyHold("ORIGINAL_DAILY_STATE_INVALID") from e
    check(type(state) is dict and state.get("schema_version")==SCHEMA,
          "ORIGINAL_DAILY_STATE_SCHEMA_CHANGED")
    return state

def quality(receipt,*,now,prior=None):
    rows=receipt.get("research_records") or []
    count=len(rows)
    summary=receipt.get("summary") or {}
    check(receipt.get("schema_version")==pilot.SCHEMA
          and 5<=count<=10 and summary.get("official_verified_cases")==count
          and all(r.get("official_council_verified") is True and
                  r.get("independent_official_reference_matched") is True and
                  r.get("planning_permission_or_work_award_confirmed") is False
                  for r in rows),"UNVERIFIED_RESEARCH_RECORDS_CANNOT_BE_COMPARED")
    accepted=[r for r in rows if r.get("research_rank",0)>0]
    excluded=[r for r in rows if r.get("research_rank")==0]
    check(len(accepted)>=5 and len(excluded)>=1 and
          len(accepted)+len(excluded)==count,
          "NO_VALID_UNFILTERED_VS_FILTERED_COMPARISON")
    before={r["reference"] for r in (prior or {}).get("research_records",[])
            if isinstance(r,dict) and isinstance(r.get("reference"),str)}
    current={r["reference"] for r in rows}
    return {
      "schema_version":QUALITY_SCHEMA,
      "status":"IDENTICAL_SAMPLE_INTERNAL_RULE_SCREENING_MEASURED",
      "as_of_utc":now.isoformat(),
      "source_commit":receipt["source"]["source_repository_commit"],
      "source_csv_sha256":receipt["source"]["source_csv_sha256"],
      "data_credit":"PlanIndex, planindex.co.uk — CC BY 4.0",
      "source_total_rows":summary["raw_csv_rows"],
      "keyword_recent_candidates":summary["recent_awaiting_trade_keyword_candidates"],
      "reviewed_sample":count,
      "keyword_unfiltered_relevant_by_our_rules":len(accepted),
      "keyword_unfiltered_noise_by_our_rules":len(excluded),
      "keyword_unfiltered_screening_yield":round(len(accepted)/count,4),
      "qualified_filtered_sample":len(accepted),
      "qualified_screening_yield":1.0,
      "within_same_sample_screening_gain_pp":round(100*len(excluded)/count,2),
      "council_verified":count,
      "held_official_checks":summary.get("official_verification_holds",0),
      "new_in_selected_sample_not_new_buyers":len(current-before) if prior else None,
      "no_longer_selected_not_withdrawn":len(before-current) if prior else None,
      "customer_vendor_name":"Planning Pipe (reported by Contractors Marketing Services)",
      "customer_vendor_feed_compared":False,
      "customer_vendor_gain_verified":False,
      "actual_contractor_intent_verified":False,
      "customer_saved_time_verified":False,
      "measurement_limits":"Same selected examples and our own rule-based relevance labels; no independent ground truth, no direct customer vendor comparison.",
      "no_outreach":True,"crm_writes":False,"buyer_contracts_verified":0,
    }

def narrative(q):
    return (
      "# Empire Data Brokerage | Southampton daily source-quality result\n\n"
      "Original evidence only; internal founder review. PlanIndex, "
      "planindex.co.uk (CC BY 4.0); original register Southampton City Council.\n\n"
      "Source checked at "+q["as_of_utc"]+"; pinned revision "+q["source_commit"]+".\n\n"
      "Current file: "+str(q["source_total_rows"])+" rows; "
      +str(q["keyword_recent_candidates"])+" recent trade-keyword matches. "
      "On the same "+str(q["reviewed_sample"])+" independently council-checked "
      "cases, "+str(q["keyword_unfiltered_relevant_by_our_rules"])+
      " were retained and "+str(q["keyword_unfiltered_noise_by_our_rules"])+
      " excluded. Unfiltered internal screening yield: "+
      str(q["keyword_unfiltered_screening_yield"]*100)+"%; "
      "after rules: 100%. A "+str(q["within_same_sample_screening_gain_pp"])+
      " percentage-point within-sample screening difference.\n\n"
      "This is not independent precision validation. The compared vendor "
      "Planning Pipe dataset, staff time and sales outcomes are unavailable, "
      "so **customer improvement remains unverified**. "
      "Planning applications are not purchase orders, leads or consent.\n"
    )

def run_due(*,now=None,request_branch=None,fetch_source=None):
    now=(now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    check(ROOT.is_dir() and not ROOT.is_symlink() and
          ROOT.stat().st_uid==os.geteuid() and
          stat.S_IMODE(ROOT.stat().st_mode)==0o700,
          "ORIGINAL_BROKERAGE_RUNTIME_NOT_PRIVATE")
    check(not LOCK.is_symlink(),"DAILY_LOCK_SYMLINK_DENIED")
    fd=os.open(LOCK,os.O_CREAT|os.O_RDWR,0o600)
    with os.fdopen(fd,"r+") as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX)
        prior_state=previous_state()
        today=now.date().isoformat()
        if prior_state and prior_state.get("attempt_day")==today:
            return {"status":"DAILY_PLANNING_ALREADY_ATTEMPTED" if prior_state.get("status")!="SUCCESS"
                    else "DAILY_PLANNING_ALREADY_VERIFIED",
                    "network_requests":0,"attempt_date":today,
                    "original_source_mining_owner":True,"new_timer":False}
        state={"schema_version":SCHEMA,"attempt_day":today,
               "attempted_at_utc":now.isoformat(),"status":"RESERVED",
               "previous_success":(prior_state or {}).get("previous_success"),
               "network_budget":MAX_REQUESTS,"external_actions_authorized":False}
        pilot._atomic(STATE,(json.dumps(state,sort_keys=True,indent=2)+"\n").encode())
        spent=0
        try:
            spent+=1
            commit=branch_sha(request=request_branch)
            def bounded_source(url):
                nonlocal spent
                check(spent<MAX_REQUESTS,"DAILY_PLANNING_REQUEST_LIMIT")
                spent+=1
                return (fetch_source or pilot.get)(url)
            prior=None
            if pilot.RECEIPT.is_file() and not pilot.RECEIPT.is_symlink():
                try:
                    candidate=json.loads(pilot.RECEIPT.read_bytes())
                    if candidate.get("schema_version")==pilot.SCHEMA:prior=candidate
                except (ValueError,OSError):pass
            result=pilot.run(now=now,fetch=bounded_source,source_commit=commit)
            current=json.loads(pilot.RECEIPT.read_bytes())
            measured=quality(current,now=now,prior=prior)
            pilot._atomic(QUALITY,(json.dumps(measured,sort_keys=True,indent=2)+"\n").encode())
            pilot._atomic(QUALITY_MD,narrative(measured).encode())
            state.update({"status":"SUCCESS","previous_success":now.isoformat(),
              "source_commit":commit,"request_count":spent,
              "quality_sha256":sha256(QUALITY.read_bytes()).hexdigest()})
            pilot._atomic(STATE,(json.dumps(state,sort_keys=True,indent=2)+"\n").encode())
            return {"status":"DAILY_PLANNING_COUNCIL_VERIFIED",
                "source_commit":commit,"verified_cases":measured["council_verified"],
                "excluded_noise":measured["keyword_unfiltered_noise_by_our_rules"],
                "within_sample_gain_pp":measured["within_same_sample_screening_gain_pp"],
                "vendor_comparison_verified":False,
                "network_requests":spent,"original_source_mining_owner":True,
                "new_timer":False,"outbound_sent":False,"crm_writes":False}
        except Exception as exc:
            state.update({"status":"HELD","reason_class":type(exc).__name__,
                          "request_count":spent})
            pilot._atomic(STATE,(json.dumps(state,sort_keys=True,indent=2)+"\n").encode())
            return {"status":"DAILY_PLANNING_SOURCE_HELD",
               "reason_class":type(exc).__name__,
               "previous_verified_evidence_preserved":True,
               "network_requests":spent,"new_timer":False,"outbound_sent":False}
