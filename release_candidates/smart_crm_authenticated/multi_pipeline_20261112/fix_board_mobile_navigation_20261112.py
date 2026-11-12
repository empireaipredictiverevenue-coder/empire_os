"""Bounded responsive navigation fix for newly released private CRM board.
Exact source hashes, root-only pre-image, no service restart, DB or auth changes.
"""
from pathlib import Path
from hashlib import sha256
import os,stat,tempfile,json
from urllib.request import urlopen
from urllib.error import HTTPError
from datetime import datetime,timezone

ROOT=Path("/srv/empire_os")
STAGE=ROOT/"release_candidates/smart_crm_authenticated/multi_pipeline_20261112"
SOURCES=[
 ROOT/"empire_os/static/revenue_crm_multi_pipeline_board.html",
 STAGE/"empire_crm_multi_pipeline_20261112/revenue_crm_multi_pipeline_board.html",
 Path("/opt/empire-ai/crm-multi-pipeline-20261112/empire_crm_multi_pipeline_20261112/revenue_crm_multi_pipeline_board.html"),
]
ACT=STAGE/"activate_crm_multi_pipeline_20261112.py"
BACKUP=Path("/var/backups/empire-crm/multi-pipeline-20261112")
OLD="163207be0c710686684481280d7fd72d24a4c9a7408fb2d93173a3c63a8c2a69"
A='@media(max-width:400px){.header-right a{display:none}.metric{padding:14px}.metric strong{font-size:24px}}'
B='@media(max-width:400px){header{flex-wrap:wrap}.header-right{width:100%;justify-content:space-between}.header-right a{display:inline-flex;font-size:12px}.metric{padding:14px}.metric strong{font-size:24px}}'

def require(v,m):
 if not v:raise RuntimeError(m)

def sha(b):return sha256(b).hexdigest()
def code(path):
 try:
  with urlopen("http://127.0.0.1:8783"+path,timeout=8) as r:return r.status,r.read(200000).decode(errors="replace")
 except HTTPError as e:return e.code,""
def write(p,data,st):
 fd,temp=tempfile.mkstemp(dir=p.parent,prefix=".board-mobile-")
 try:
  with os.fdopen(fd,"wb") as f:
   f.write(data);f.flush();os.fsync(f.fileno())
   os.fchmod(f.fileno(),stat.S_IMODE(st.st_mode))
   os.fchown(f.fileno(),st.st_uid,st.st_gid)
  os.replace(temp,p)
 finally:
  if os.path.exists(temp):os.unlink(temp)

def main(apply):
 originals=[]
 for p in SOURCES:
  require(p.is_file() and not p.is_symlink(),"source_not_regular")
  content=p.read_bytes()
  require(sha(content)==OLD,"concurrent_board_source_changed")
  require(content.count(A.encode())==1,"responsive_selector_changed")
  originals.append((p,content,p.stat()))
 new=originals[0][1].replace(A.encode(),B.encode())
 new_sha=sha(new)
 require(ACT.read_text().count(OLD)==1,"release_pin_not_unique")
 require(code("/health")[0]==200,"existing_crm_not_healthy")
 require(code("/v1/revenue-crm/pipelines/view")[0]==200,"board_unavailable")
 require(code("/v1/revenue-crm/pipelines/board")[0]==401,"unsigned_data_not_protected")
 if not apply:
  print(json.dumps({"status":"MOBILE_NAV_SINGLE_RULE_PREFLIGHT_PASS",
        "original_sha256":OLD,"new_sha256":new_sha,"production_writes":False}))
  return
 require(os.geteuid()==0,"requires_original_release_owner_root")
 require(BACKUP.is_dir() and BACKUP.stat().st_uid==0 and BACKUP.stat().st_mode&0o077==0,"backup_not_protected")
 oldbackup=BACKUP/"mobile_nav_original.html"
 receipt=BACKUP/"mobile_nav_fix_receipt.json"
 require(not oldbackup.exists() and not receipt.exists(),"already_attempted")
 with oldbackup.open("xb") as f:
  f.write(originals[0][1]);f.flush();os.fsync(f.fileno())
 os.chmod(oldbackup,0o600);os.chown(oldbackup,0,0)
 changed=[]
 try:
  for p,original,st in originals:
   require(p.read_bytes()==original,"concurrent_html_edit")
   write(p,new,st)
   changed.append((p,original,st))
  response,content=code("/v1/revenue-crm/pipelines/view")
  require(response==200 and B in content and A not in content,"live_mobile_rule_not_adopted")
  require(code("/v1/revenue-crm/journeys/entry")[0]==200,"journey_signin_turned_off")
  require(code("/v1/revenue-crm/pipelines/board")[0]==401,"tenant_auth_broadened")
  require(code("/health")[0]==200,"existing_CRM_lost")
  script=ACT.read_text()
  require(script.count(OLD)==1,"activation_pin_race")
  ACT.write_text(script.replace(OLD,new_sha))
  require(all(sha(p.read_bytes())==new_sha for p in SOURCES),"post_fix_source_drift")
  result={"status":"PRIVATE_CRM_MOBILE_NAVIGATION_VERIFIED",
   "source_sha256":new_sha,"original_sha256":OLD,
   "browser_test_pending":True,"root_only_backup":str(oldbackup),
   "service_restart":False,"db_writes":False,
   "timestamp_utc":datetime.now(timezone.utc).isoformat()}
  with receipt.open("x") as f:json.dump(result,f,indent=2,sort_keys=True)
  os.chmod(receipt,0o600);os.chown(receipt,0,0)
  print(json.dumps(result,sort_keys=True))
 except BaseException:
  for p,original,st in reversed(changed):
   if p.read_bytes()==new:write(p,original,st)
  raise

if __name__=="__main__":
 import argparse
 parser=argparse.ArgumentParser();parser.add_argument("--apply",action="store_true")
 args=parser.parse_args();main(args.apply)
