#!/usr/bin/env python3
"""Read-only immutable Empire Analytics private console release gate."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError, URLError

ROOT=Path("/srv/empire_os")
PRIOR=Path("/home/ubuntu/empire_worktrees/empire_founder_gsc_trends_commercial_v2_candidate_20261019")
TARGET=Path("/home/ubuntu/empire_worktrees/empire_analytics_platform_branded_candidate_20261019")
APP=ROOT/"apps/search-command-centre"
EXPECTED={
 ".next/BUILD_ID":"b495bfc5fc93c1ce6deb060e542a85aae34431f2cf7367089deea1bd044a6c03",
 ".next/server/app/department/page.js":"ad25658ed9a0e43ed8cb181b7dc467624eea922eab1ee3f312e98f7036bd2b4b",
 ".next/server/app/department/evidence/page.js":"7b04223687360b453e47b3f656a5eec10804e7b41871e5d8e3164b452127dccb",
 ".next/server/app/founder/commercial-pipeline/page.js":"a17a41790a5158d054f703a85058fc430134222b9d1671f0aa020a64dd3f7f9d",
 ".next/server/app/founder/mail/page.js":"28bcd13ce97e691eb661ab7ba5aed2c6d40e802801d0c1e7c676ad1f08463bb4",
 ".next/server/app/page.js":"618f17f8a02fa889af2570102459977c57fb98ccb1a3e1d1e32e1f3448d07d7b",
}
OLD_ROUTES=("/","/founder","/founder/mail","/founder/results",
 "/founder/solar","/founder/youtube","/founder/intent-review",
 "/founder/commercial-pipeline","/revenue","/department")
PUBLIC_PATHS=("/department","/department/evidence","/v1/search/department/review")
BRAND_SHA="a89c4e6c179e6fdeb5ae1e5b140d1c6007a4f359d633f51390a9fc7a1f79a64c"

class NoRedirect(HTTPRedirectHandler):
 def redirect_request(self,request,fp,code,msg,headers,newurl):return None

def get(url: str) -> tuple[int|None,dict]:
 allowed={f"http://127.0.0.1:3001{p}" for p in OLD_ROUTES}
 allowed.update(f"https://empire-ai.co.uk{p}" for p in PUBLIC_PATHS)
 allowed.add("http://127.0.0.1:8771/v1/search/department/review")
 if url not in allowed:return None,{}
 try:
  req=Request(url,method="GET",headers={"Accept":"application/json",
   "User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131.0 Safari/537.36"})
  with build_opener(NoRedirect()).open(req,timeout=9) as response:
   if url=="http://127.0.0.1:8771/v1/search/department/review":
    body=response.read(65537)
    if len(body)>65536:return None,{}
    try:return response.status,json.loads(body)
    except (ValueError,TypeError):return response.status,{}
   return response.status,{}
 except HTTPError as exc:return exc.code,{}
 except (OSError,URLError,TimeoutError,ValueError):return None,{}

def release_frozen() -> bool:
 try:
  if PRIOR.is_symlink() or TARGET.is_symlink() or not PRIOR.is_dir() or not TARGET.is_dir():return False
  def enumerate_source(root:Path):
   base=root/"src"
   return {str(p.relative_to(base)):p for p in base.rglob("*") if p.is_file()}
  a,b=enumerate_source(PRIOR),enumerate_source(TARGET)
  if not 10 <= len(a) <= 125 or len(b)>130:return False
  added=set(b)-set(a)
  changed={k for k in set(a)&set(b) if a[k].read_bytes()!=b[k].read_bytes()}
  if added!={"app/department/analytics.module.css","app/department/evidence/page.tsx"}:return False
  if set(a)-set(b) or changed!={"app/department/page.tsx","app/page.tsx"}:return False
  if any(p.is_symlink() or p.stat().st_size>750000 for p in b.values()):return False
  for path in added|changed:
   if b[path].read_bytes()!=(APP/"src"/path).read_bytes():return False
  if (TARGET/"node_modules").readlink()!=(APP/"node_modules"):return False
  logo=TARGET/"public/brand/empire-ai-official-brand-logo-lockup.png"
  if logo.is_symlink() or not logo.is_file() or logo.stat().st_size>1000000:return False
  for candidate in (logo,APP/"public/brand/empire-ai-official-brand-logo-lockup.png",ROOT/"apps/empire-public-site/out/brand/empire-ai-official-brand-logo-lockup.png"):
   if hashlib.sha256(candidate.read_bytes()).hexdigest()!=BRAND_SHA:return False
  for relative,digest in EXPECTED.items():
   p=TARGET/relative
   if p.is_symlink() or not p.is_file() or p.stat().st_size>18000000:return False
   if hashlib.sha256(p.read_bytes()).hexdigest()!=digest:return False
  proc=subprocess.run(["git","-C",str(ROOT),"merge-base","--is-ancestor","c46f438c","HEAD"],capture_output=True,timeout=5)
  if proc.returncode!=0:return False
  return True
 except (OSError,ValueError,subprocess.TimeoutExpired):return False

def owner_unchanged() -> bool:
 try:
  p=subprocess.run(["systemctl","show","empire-founder-console.service","-p","WorkingDirectory","-p","DropInPaths","-p","ActiveState","-p","ExecStart","--no-pager"],capture_output=True,text=True,timeout=5)
  if p.returncode!=0:return False
  data=dict(line.split("=",1) for line in p.stdout.splitlines() if "=" in line)
  drops=data.get("DropInPaths","").split()
  return (data.get("ActiveState")=="active" and data.get("WorkingDirectory")==str(PRIOR)
   and len(drops)==7 and drops[-1].endswith("/98-private-gsc-trend-release.conf")
   and "-H 127.0.0.1 -p 3001" in data.get("ExecStart","")
   and not any("99-private-empire-analytics-release.conf" in d for d in drops))
 except (OSError,subprocess.TimeoutExpired,ValueError):return False

def assess(*,frozen:bool,prior:bool,old_routes:bool,public_closed:bool,backend:dict) -> dict:
 chart=backend.get("gsc_daily_chart") if isinstance(backend,dict) else None
 api_ok=(isinstance(backend,dict) and backend.get("schema_version")=="empire.search_growth.department_integration.v1"
  and backend.get("status")=="DEPARTMENT_CONNECTED_EVIDENCE_GAPS_OPEN"
  and backend.get("search_rankings_verified") is False
  and backend.get("realised_revenue_verified") is False
  and isinstance(chart,dict) and chart.get("source")=="google_search_console_date_dimension"
  and chart.get("status")=="DATE_DIMENSION_ROWS_OBSERVED"
  and chart.get("independent_google_rank_positions_verified") is False
  and chart.get("realised_revenue_verified") is False)
 ready=frozen and prior and old_routes and public_closed and api_ok
 return {
  "status":"FROZEN_BRANDED_ANALYTICS_READY_FOR_FOUNDER_RELEASE" if ready else "HOLD_BRANDED_ANALYTICS_OWNER_OR_SOURCE",
  "mode":"READ_ONLY","frozen_brand_and_source_verified":frozen,
  "existing_founder_owner_preserved":prior,"ten_existing_routes_healthy":old_routes,
  "public_department_routes_closed":public_closed,"backend_first_party_evidence_ready":api_ok,
  "gsc_is_website_sessions":False,"visitor_analytics_connected":False,
  "revenue_verified":False,"service_restarted":False,"production_changed":False,
  "execution_authority":"NONE",
 }

def inspect()->dict:
 old=all(get("http://127.0.0.1:3001"+p)[0]==200 for p in OLD_ROUTES)
 public=all(get("https://empire-ai.co.uk"+p)[0]==404 for p in PUBLIC_PATHS)
 code,backend=get("http://127.0.0.1:8771/v1/search/department/review")
 return assess(frozen=release_frozen(),prior=owner_unchanged(),old_routes=old,
  public_closed=public,backend=backend if code==200 else {})

def main(argv=None)->int:
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument("--read-only",required=True,action="store_true")
 parser.parse_args(argv)
 result=inspect()
 print(json.dumps(result,sort_keys=True))
 return 0 if result["status"]=="FROZEN_BRANDED_ANALYTICS_READY_FOR_FOUNDER_RELEASE" else 2

if __name__=="__main__":
 raise SystemExit(main())
