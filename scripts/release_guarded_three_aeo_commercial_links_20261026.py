#!/usr/bin/env python3
"""Exact-three AEO pages: original generator -> same commercial B2B action.

Does not rebuild/mass-publish 205+ pages. Keeps every other current byte
unchanged, preserving real page evidence, H1/canonical, roofing contextual
link and all non-AEO pages. One-time immutable backup and live hash readback.
"""
from __future__ import annotations
import argparse
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

PROD=Path("/srv/empire_os")
GEN=PROD/"scripts/aeo_metro_gen.py"
SITE=PROD/"runtime/aeo"
RELEASE=Path("/home/ubuntu/empire_releases/seo_aeo_direct_commercial_bridge_20261026_v1")
PUBLIC="https://empire-ai.co.uk"
SCOPE=(("general_contractor","NYC"),("hvac","DFW"),("roofing","DFW"))
CTA='<a class="btn btn-secondary" href="/commercial">Discuss a scoped market assessment</a>'

def sha(data:bytes)->str:return sha256(data).hexdigest()

def public(url: str)->bytes:
 r=requests.get(PUBLIC+url,timeout=14,headers={"Cache-Control":"no-cache"})
 if r.status_code!=200 or r.url.rstrip("/")!=(PUBLIC+url).rstrip("/"):
  raise ValueError("PUBLIC_HTTPS_ROUTE_NOT_EXACT:"+url)
 if not 100<len(r.content)<250000:
  raise ValueError("BOUNDED_REAL_HTML_REQUIRED:"+url)
 return r.content

def oldsource():
 # Exact published live bytes are the source of truth, never an older generated bundle.
 return {(a,b):(SITE/a/b/"index.html").read_bytes() for a,b in SCOPE}

def prepare():
 if RELEASE.exists(): raise ValueError("IMMUTABLE_RELEASE_DIR_ALREADY_EXISTS")
 if not GEN.is_file() or GEN.is_symlink():raise ValueError("EXISTING_AEO_GENERATOR_MISSING")
 spec=importlib.util.spec_from_file_location("original_aeo_market_gen",GEN)
 m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 if not all(pair[0] in m.NICHE_INFO and pair[1] in m.METROS for pair in SCOPE):
  raise ValueError("ORIGINAL_AEO_MARKET_UNRECOGNISED")
 target=BeautifulSoup(public("/commercial"),"html.parser")
 if ([a.get("href") for a in target.select('link[rel=canonical]')]
     != [PUBLIC+"/commercial"] or len(target.select("main h1"))!=1):
  raise ValueError("EXISTING_COMMERCIAL_ROUTE_NOT_ELIGIBLE")
 before=oldsource()
 manifest=[]
 after={}
 for niche,metro in SCOPE:
  key=(niche,metro)
  route=f"/aeo/{niche}/{metro}/"
  expected_old=before[key]
  if public(route)!=expected_old:raise ValueError("LIVE_AEO_OWNERSHIP_CHANGED:"+route)
  expected_new=m.generate_page(niche,metro).encode()
  if expected_new.count(CTA.encode())!=1:
   raise ValueError("GENERATOR_EXPECTED_EXACT_ONE_B2B_CTA:"+route)
  if expected_new.replace(CTA.encode(),b"",1)!=expected_old:
   raise ValueError("NOT_EXACT_GENERATOR_ADDITIVE_CHANGE:"+route)
  a=BeautifulSoup(expected_old,"html.parser")
  b=BeautifulSoup(expected_new,"html.parser")
  if [x.get_text(" ",strip=True) for x in a.select("h1, h2")]!=[x.get_text(" ",strip=True) for x in b.select("h1, h2")]:
   raise ValueError("H1_H2_CHANGED:"+route)
  if [x.get("href") for x in a.select('link[rel=canonical]')]!=[x.get("href") for x in b.select('link[rel=canonical]')]:
   raise ValueError("CANONICAL_CHANGED:"+route)
  for old_link in a.select('a[href]'):
   if b.select('a[href="'+old_link["href"]+'"]')==[]:
    raise ValueError("EXISTING_LINK_REMOVED:"+route)
  if len(b.select('main a[href="/commercial"]'))!=1 or len(a.select('main a[href="/commercial"]'))!=0:
   raise ValueError("DIRECT_COMMERCIAL_LINK_SHAPE_WRONG:"+route)
  manifest.append({
      "route":route,"niche":niche,"metro":metro,
      "file":str((SITE/niche/metro/"index.html")),
      "before_sha256":sha(expected_old),"after_sha256":sha(expected_new),
      "only_byte_change":CTA,"new_direct_commercial_anchors":1,
      "existing_heading_and_canonical_preserved":True,
      "homeowner_customer_form_added":False,
  })
  after[key]=expected_new
 return {
   "schema_version":"empire.seo.three_aeo_b2b_cta_release.v1",
   "status":"GUARDED_PREFLIGHT",
   "time":datetime.now(timezone.utc).isoformat(),
   "original_generator_sha256":sha(GEN.read_bytes()),
   "file_count":3,"direct_commercial_links_added":3,
   "other_aeo_pages_touched":0,
   "other_html_assets_touched":0,
   "buyer_terms_or_paid_traffic_changed":False,
   "automated_outbound_sent":False,
   "database_writes":False,
   "pages":manifest,
 },after

def install(receipt,after):
 RELEASE.mkdir(mode=0o700)
 before_dir=RELEASE/"before";before_dir.mkdir(mode=0o700)
 after_dir=RELEASE/"after";after_dir.mkdir(mode=0o700)
 for row in receipt["pages"]:
  name=f'{row["niche"]}_{row["metro"]}.html'
  file=Path(row["file"])
  if sha(file.read_bytes())!=row["before_sha256"]:raise ValueError("TARGET_SOURCE_CHANGED_BEFORE_BACKUP")
  shutil.copy2(file,before_dir/name)
  (after_dir/name).write_bytes(after[(row["niche"],row["metro"])])
 (RELEASE/"preflight.json").write_text(json.dumps(receipt,sort_keys=True,indent=2)+"\n")
 applied=[]
 try:
  for row in receipt["pages"]:
   file=Path(row["file"])
   if sha(file.read_bytes())!=row["before_sha256"]:
    raise ValueError("CONCURRENT_HTML_CHANGE_HOLD")
   temp=file.with_name("index.html.seo_20261026_candidate")
   if temp.exists():raise ValueError("UNEXPECTED_CANDIDATE_COLLISION")
   shutil.copy2(after_dir/f'{row["niche"]}_{row["metro"]}.html',temp)
   os.replace(temp,file)
   applied.append(row)
  for row in receipt["pages"]:
   remote=public(row["route"])
   if sha(remote)!=row["after_sha256"]:
    raise ValueError("PUBLIC_HTML_NOT_CURRENT_EXPECTED_HASH:"+row["route"])
   parsed=BeautifulSoup(remote,"html.parser")
   if len(parsed.select('main a[href="/commercial"]'))!=1:
    raise ValueError("PUBLIC_B2B_ACTION_NOT_PRESENT:"+row["route"])
  receipt["status"]="THREE_ORIGINAL_AEO_COMMERCIAL_LINKS_LIVE_VERIFIED"
  receipt["published_utc"]=datetime.now(timezone.utc).isoformat()
  (RELEASE/"release_receipt.json").write_text(json.dumps(receipt,sort_keys=True,indent=2)+"\n")
  print(json.dumps({"status":receipt["status"],
    "live_pages":3,"direct_buyer_links":3,
    "backup":str(before_dir),"receipt":str(RELEASE/"release_receipt.json"),
    "other_routes_changed":0},sort_keys=True))
 except Exception:
  for row in reversed(applied):
   dest=Path(row["file"])
   if sha(dest.read_bytes())==row["after_sha256"]:
    staged=dest.with_name("index.html.seo_20261026_restore")
    shutil.copy2(before_dir/f'{row["niche"]}_{row["metro"]}.html',staged)
    os.replace(staged,dest)
  (RELEASE/"rollback_review_required").write_text("Inspect exact pre- and post-hashes; guarded restoration attempted.\n")
  raise

def main():
 p=argparse.ArgumentParser()
 group=p.add_mutually_exclusive_group(required=True)
 group.add_argument("--dry-run",action="store_true")
 group.add_argument("--apply",action="store_true")
 p.add_argument("--original-three-page-approval",action="store_true")
 args=p.parse_args()
 if args.apply and not args.original_three_page_approval:
  p.error("Require explicit three-page only approval.")
 receipt,after=prepare()
 if args.dry_run:
  print(json.dumps({"status":"THREE_PAGE_AEO_RELEASE_PREFLIGHT_READY",
     "scope":[v["route"] for v in receipt["pages"]],
     "expected_source_only_change":"add exact one nonbinding commercial link per page",
     "other_pages_or_forms_changed":False},sort_keys=True))
 else:install(receipt,after)

if __name__=="__main__":
 main()
