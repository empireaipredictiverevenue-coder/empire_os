#!/usr/bin/env python3
"""Guarded single Commercial HTML hydration release to original static site.

No full-site overwrite, older flagship asset deletion, other HTML modification,
service restart, CRM or payment write. Build is current-production-source based.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
from bs4 import BeautifulSoup
import requests

LIVE=Path('/srv/empire_os/apps/empire-public-site/out')
NEW=Path('/home/ubuntu/empire_releases/seo_aeo_entry_claim_v2_20261026_stage/current_public_website_source_build/out')
APP=Path('/srv/empire_os/apps/empire-public-site')
SOURCE=NEW.parent
RELEASE=Path('/home/ubuntu/empire_releases/seo_aeo_entry_claim_v2_commercial_public_20261026')
ORIGIN='https://empire-ai.co.uk'

def sha(blob:bytes)->str:return hashlib.sha256(blob).hexdigest()

def semantic(raw:bytes):
 doc=BeautifulSoup(raw,'html.parser')
 main=doc.select_one('main')
 if main is None:raise RuntimeError('ORIGINAL_COMMERCIAL_MAIN_MISSING')
 return {
  'title':doc.title.get_text(' ',strip=True) if doc.title else None,
  'canonical':[x.get('href') for x in doc.select('link[rel=canonical]')],
  'headings':[(x.name,x.get_text(' ',strip=True)) for x in doc.select('main h1,main h2')],
  'main_text':main.get_text(' ',strip=True),
  'form_count':len(doc.select('main form')),
  'input_count':len(doc.select('main input')),
  'links':sorted(x.get('href') for x in doc.select('main a[href]')),
  'enquiry_section':bool(doc.select_one('#commercial-enquiry')),
 }

def published_raw(path:str)->bytes:
 response=requests.get(ORIGIN+path,timeout=13,headers={'Cache-Control':'no-cache'})
 if response.status_code!=200 or response.url.rstrip('/')!=(ORIGIN+path).rstrip('/'):
  raise RuntimeError('PUBLIC_FILE_NOT_EXACT_HTTP_200:'+path)
 if not 0<len(response.content)<120000:
  raise RuntimeError('PUBLIC_HTML_UNBOUNDED:'+path)
 return response.content

def safe_files():
 current=(LIVE/'commercial.html').read_bytes()
 candidate=(NEW/'commercial.html').read_bytes()
 if semantic(current)!=semantic(candidate):
  raise RuntimeError('COMMERCIAL_VISIBLE_CONTENT_OR_FORM_CHANGED')
 if published_raw('/commercial')!=current:
  raise RuntimeError('PUBLIC_COMMERCIAL_DOES_NOT_MATCH_CURRENT_SOURCE')
 if semantic(current)['canonical']!=[ORIGIN+'/commercial']:
  raise RuntimeError('COMMERCIAL_SELF_CANONICAL_MISSING')
 if not semantic(current)['enquiry_section']:
  raise RuntimeError('ORIGINAL_COMMERCIAL_ENQUIRY_MISSING')
 for rel in ('src/lib/commercial-entry-review.ts','src/app/commercial/page.tsx','next.config.ts','package.json'):
  if (APP/rel).read_bytes()!=(SOURCE/rel).read_bytes():
   raise RuntimeError('FOUNDER_SITE_SOURCE_CHANGED:'+rel)
 if RELEASE.exists():raise RuntimeError('SINGLE_RELEASE_ALREADY_PERFORMED')
 asset_list=[]
 for f in sorted((NEW/'_next/static').rglob('*')):
  if not f.is_file() or f.is_symlink():continue
  rel=f.relative_to(NEW)
  live=LIVE/rel
  if live.is_symlink():raise RuntimeError('LIVE_ASSET_SYMLINK_COLLISION:'+str(rel))
  if live.is_file() and live.read_bytes()!=f.read_bytes():
   raise RuntimeError('HASHED_ASSET_NAME_COLLISION:'+str(rel))
  if not live.exists():
   asset_list.append((f,live))
 missing_refs=set()
 doc=BeautifulSoup(candidate,'html.parser')
 for x in doc.select('script[src], link[href]'):
  path=x.get('src') or x.get('href') or ''
  if path.startswith('/_next/static/'):
   if not (NEW/path.lstrip('/')).is_file():missing_refs.add(path)
 if missing_refs:raise RuntimeError('COMMERCIAL_DEPENDENCIES_NOT_IN_GENERATED_BUILD')
 return current,candidate,asset_list

def publish():
 original,candidate,assets=safe_files()
 RELEASE.mkdir(mode=0o700)
 backup=RELEASE/'commercial.before.html';backup.write_bytes(original)
 records=[]
 added=[]
 try:
  for source,dest in assets:
   dest.parent.mkdir(parents=True,exist_ok=True)
   fd=os.open(dest,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o644)
   with os.fdopen(fd,'wb') as stream:
    stream.write(source.read_bytes())
    stream.flush()
    os.fsync(stream.fileno())
   if sha(dest.read_bytes())!=sha(source.read_bytes()):
    raise RuntimeError('NEW_STATIC_FILE_WRITE_MISMATCH')
   added.append(dest)
   records.append({'path':str(dest.relative_to(LIVE)),'sha256':sha(dest.read_bytes())})
  target=LIVE/'commercial.html'
  tmp=LIVE/'commercial.html.aeo_claim_20261026_new'
  if tmp.exists():raise RuntimeError('UNEXPECTED_COMMERICAL_TEMP_COLLISION')
  shutil.copy2(NEW/'commercial.html',tmp)
  if sha(target.read_bytes())!=sha(original):
   raise RuntimeError('CURRENT_COMMERCIAL_OWNER_SOURCE_DRIFT')
  os.replace(tmp,target)
  if published_raw('/commercial')!=candidate:
   raise RuntimeError('PUBLIC_COMMERCIAL_ROLLBACK_REQUIRED')
  document=BeautifulSoup(candidate,'html.parser')
  for x in document.select('script[src], link[href]'):
   path=x.get('src') or x.get('href') or ''
   if path.startswith('/_next/static/'):
    r=requests.get(ORIGIN+path,timeout=12)
    if r.status_code!=200 or r.content!=(NEW/path.lstrip('/')).read_bytes():
     raise RuntimeError('PUBLIC_NEW_STATIC_DEPENDENCY_FAILED:'+path)
  result={
   'status':'ORIGINAL_COMMERCIAL_CONSENTED_ENTRY_FRONTEND_LIVE_VERIFIED',
   'changed_html_routes':['/commercial'],
   'other_routes_changed':0,
   'added_hashed_static_assets':records,
   'old_html_sha256':sha(original),
   'new_html_sha256':sha(candidate),
   'semantic_content_unchanged':True,
   'original_form_unchanged':True,
   'existing_site_assets_replaced':False,
   'original_a eo_release_unchanged'.replace(' ',''):True,
   'backend_restart_performed':False,
   'crm_writes':False,
   'outbound_sent':False,
  }
  (RELEASE/'release_receipt.json').write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
  print(json.dumps({'status':result['status'],'new_assets':len(added),
   'site_html_routes_changed':1,'backup':str(backup),
   'receipt':str(RELEASE/'release_receipt.json')},sort_keys=True))
 except Exception:
  live=LIVE/'commercial.html'
  if live.exists() and sha(live.read_bytes())==sha(candidate):
   tmp=LIVE/'commercial.html.aeo_claim_20261026_restore'
   shutil.copy2(backup,tmp);os.replace(tmp,live)
  for p in reversed(added):
   if p.exists() and sha(p.read_bytes())==sha((NEW/p.relative_to(LIVE)).read_bytes()):
    p.unlink()
  (RELEASE/'rollback_attempted.json').write_text(
   json.dumps({'status':'ROLLBACK_ATTEMPTED','original_html_sha256':sha(original)})+'\n')
  raise

def main():
 p=argparse.ArgumentParser()
 exclusive=p.add_mutually_exclusive_group(required=True)
 exclusive.add_argument('--dry-run',action='store_true')
 exclusive.add_argument('--apply',action='store_true')
 args=p.parse_args()
 if args.dry_run:
  old,new,assets=safe_files()
  print(json.dumps({'status':'GUARDED_ONE_COMMERCIAL_ROUTE_PREFLIGHT',
   'only_one_html_route':True,'semantic_equal':True,
   'new_hashed_assets':len(assets),'previous_sha256':sha(old),
   'candidate_sha256':sha(new)},sort_keys=True))
 else:publish()

if __name__=='__main__':main()
