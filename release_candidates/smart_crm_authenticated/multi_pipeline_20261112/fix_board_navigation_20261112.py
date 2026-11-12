"""Guarded one-link correction to the new private CRM board (no restart).
Reuses the existing Journey Designer login entry route, preserves all prior
versioned releases and writes a root-only before/after receipt.
"""
from pathlib import Path
from hashlib import sha256
from urllib.request import urlopen
from urllib.error import HTTPError
import json,os,stat,tempfile
from datetime import datetime,timezone
ROOT=Path("/srv/empire_os")
RELEASE=ROOT/"release_candidates/smart_crm_authenticated/multi_pipeline_20261112"
CAND=RELEASE/"empire_crm_multi_pipeline_20261112/revenue_crm_multi_pipeline_board.html"
SOURCE=ROOT/"empire_os/static/revenue_crm_multi_pipeline_board.html"
LIVE=Path("/opt/empire-ai/crm-multi-pipeline-20261112/empire_crm_multi_pipeline_20261112/revenue_crm_multi_pipeline_board.html")
ACT=RELEASE/"activate_crm_multi_pipeline_20261112.py"
BACKUP=Path("/var/backups/empire-crm/multi-pipeline-20261112")
OLD="35f600ac8263120c51ce2ab87ba8b42875d1c6361dc44424aa28195eb0effbdc"
BEFORE='href="/v1/revenue-crm/journeys/designer"'
AFTER='href="/v1/revenue-crm/journeys/entry"'
def h(b):return sha256(b).hexdigest()
def req(ok,msg):
 if not ok:raise RuntimeError(msg)
def get(path):
 try:
  with urlopen("http://127.0.0.1:8783"+path,timeout=9) as r:
   return r.status,r.read(200000).decode(errors="replace")
 except HTTPError as e:return e.code,""
def write(p,data,st):
 fd,tmp=tempfile.mkstemp(dir=p.parent,prefix=".board-link-")
 try:
  with os.fdopen(fd,"wb") as f:
   f.write(data);f.flush();os.fsync(f.fileno())
   os.fchmod(f.fileno(),stat.S_IMODE(st.st_mode))
   os.fchown(f.fileno(),st.st_uid,st.st_gid)
  os.replace(tmp,p)
 finally:
  if os.path.exists(tmp):os.unlink(tmp)
def run(apply):
 files=[SOURCE,CAND,LIVE]
 old=[]
 for p in files:
  req(p.is_file() and not p.is_symlink(),"source_not_regular")
  b=p.read_bytes();req(h(b)==OLD,"concurrent_live_board_change")
  req(b.count(BEFORE.encode())==1,"exact_link_contract_changed")
  old.append((p,b,p.stat()))
 req(ACT.read_text().count(OLD)==1,"release_source_pin_changed")
 new=old[0][1].replace(BEFORE.encode(),AFTER.encode())
 new_sha=h(new)
 req(get("/health")[0]==200,"existing_CRM_unhealthy")
 req(get("/v1/revenue-crm/journeys/entry")[0]==200,"original_journey_login_missing")
 req(get("/v1/revenue-crm/pipelines/view")[0]==200,"board_missing")
 req(get("/v1/revenue-crm/pipelines/board")[0]==401,"board_auth_regressed")
 if not apply:
  print(json.dumps({"status":"ONE_LINK_NAVIGATION_PRECHECK_PASS",
    "source_sha_before":OLD,"source_sha_after":new_sha,
    "production_write":False,"restart":False}))
  return
 req(os.geteuid()==0,"root_required_for_versioned_release")
 req(BACKUP.is_dir() and BACKUP.stat().st_uid==0 and BACKUP.stat().st_mode&0o077==0,"backup_not_private")
 original_copy=BACKUP/"navigation_original.html"
 receipt=BACKUP/"navigation_fix_receipt.json"
 req(not original_copy.exists() and not receipt.exists(),"previous_one_link_fix_exists")
 with original_copy.open("xb") as f:
  f.write(old[0][1]);f.flush();os.fsync(f.fileno())
 os.chmod(original_copy,0o600);os.chown(original_copy,0,0)
 done=[]
 try:
  for p,b,st in old:
   req(p.read_bytes()==b,"source_concurrent_change")
   write(p,new,st);done.append((p,b,st))
  status,body=get("/v1/revenue-crm/pipelines/view")
  req(status==200 and AFTER in body and BEFORE not in body,"live_navigation_wrong")
  req(get("/v1/revenue-crm/journeys/entry")[0]==200,"journey_entry_unreachable")
  req(get("/v1/revenue-crm/pipelines/board")[0]==401,"private_board_access_regressed")
  req(get("/health")[0]==200,"original_CRM_unhealthy_after_link_change")
  text=ACT.read_text()
  req(text.count(OLD)==1,"activation_checksum_race")
  ACT.write_text(text.replace(OLD,new_sha))
  req(all(h(p.read_bytes())==new_sha for p in files),"post_fix_bundle_drift")
  result={"status":"PRIVATE_CRM_NAVIGATION_LINK_VERIFIED","source_sha_after":new_sha,
    "old_sha_preserved":OLD,"changed_files":len(files),
    "journey_entry_http":200,"private_board_unauthorized_http":401,
    "service_restarted":False,"database_writes":False,"emails_sent":False,
    "verified_at_utc":datetime.now(timezone.utc).isoformat()}
  with receipt.open("x") as f:
   json.dump(result,f,sort_keys=True,indent=2)
  os.chmod(receipt,0o600);os.chown(receipt,0,0)
  print(json.dumps(result,sort_keys=True))
 except BaseException:
  for p,b,st in reversed(done):
   if p.read_bytes()==new:write(p,b,st)
  raise

if __name__=="__main__":
 import argparse
 p=argparse.ArgumentParser()
 p.add_argument("--apply",action="store_true")
 a=p.parse_args();run(a.apply)
