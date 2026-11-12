"""One-use, guarded release of the existing private Smart CRM board.

Only adds a versioned read-only overlay and one systemd ExecStart drop-in.
Keeps the original first-party login, tenant reader, service, source deployments,
route protections and credentials. Explicit rollback on any failed live check.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import time
from datetime import datetime,timezone
from pathlib import Path
from urllib.error import HTTPError,URLError
from urllib.request import urlopen

ROOT=Path("/srv/empire_os")
CAND=ROOT/"release_candidates/smart_crm_authenticated/multi_pipeline_20261112"
SRC=CAND/"empire_crm_multi_pipeline_20261112"
DEST=Path("/opt/empire-ai/crm-multi-pipeline-20261112")
PKG=DEST/"empire_crm_multi_pipeline_20261112"
REHEARSAL=CAND/"rehearse_private_crm_pipeline_20261112.py"
SERVICE="empire-revenue-crm-pilot.service"
ORIGINAL="crm_search_additive_20261109.entrypoint:app"
NEW="empire_crm_multi_pipeline_20261112.entrypoint:app"
DROP=Path("/etc/systemd/system/empire-revenue-crm-pilot.service.d/zzzzzzzzzzzzzz-crm-multi-pipeline-20261112.conf")
PRIOR=Path("/etc/systemd/system/empire-revenue-crm-pilot.service.d/zzzzzzzzzzzzz-crm-search-additive-20261109.conf")
BACKUP=Path("/var/backups/empire-crm/multi-pipeline-20261112")
LOCK=Path("/var/lock/empire-crm-private-release.lock")
PINS={
 "__init__.py":"ac2304a1243a7143cf7f1e741285b7b08775a6107c18bda3aa8398cb386d303a",
 "entrypoint.py":"e7fc29a14df78c04bd23bb47ead795a8b0cbfa627a82238f5d03aed8ee7bf978",
 "mount.py":"1b298133a0360f2f971600d8b3671f8bf00c2d8bb8b9055fe62472dd4344df31",
 "revenue_crm_multi_pipeline.py":"e43ab94c86cdb7b444f543473fa51d21e4f15869ef050f89768ae6da841756c7",
 "revenue_crm_multi_pipeline_board.html":"35f600ac8263120c51ce2ab87ba8b42875d1c6361dc44424aa28195eb0effbdc",
 "revenue_crm_multi_pipeline_board.js":"4b53dae73d2602bc98c24a8494bc42dbbc10b9f90f8d04721d4e4effc3ce60db",
}
REHEARSAL_PIN="7330b3c2d6aa5119ae7dcab7165f4bc18cdcd8840e598842c348126236bde4bb"
ORIGINAL_ENTRY_PIN="26e536dc1c00f3402e92849b4e908271ee89096b14df446866dc7dfaf7a711c4"
ORIGINAL_MOUNT_PIN="b57f2dd9ba35bb0994401cf8f795d83c42cdaeeca42afaf56dfb3720d70129c7"
SEARCH="/v1/revenue-crm/prospects/00000000-0000-0000-0000-000000000000/search-growth?site_id=00000000-0000-0000-0000-000000000000&query=release-check&engine=release-check"

def require(ok,message):
 if not ok:raise RuntimeError(message)

def digest(data):return hashlib.sha256(data).hexdigest()

def safe_bytes(path):
 require(path.is_file() and not path.is_symlink(),"not_regular_file:"+str(path))
 require(not any(p.is_symlink() for p in path.parents),"symlink_parent:"+str(path))
 return path.read_bytes()

def proc(*args):
 return subprocess.check_output(args,text=True,timeout=40).strip()

def prop(name):
 return proc("systemctl","show",SERVICE,"-p",name,"--value")

def code(path):
 try:
  with urlopen("http://127.0.0.1:8783"+path,timeout=8) as r:
   return r.status,r.read(1_000_000).decode("utf-8",errors="replace")
 except HTTPError as e:return e.code,""
 except (URLError,TimeoutError):return 0,""

def previous_pins():
 old=Path("/opt/empire-ai/crm-search-additive-20261109/crm_search_additive_20261109")
 require(digest(safe_bytes(old/"entrypoint.py"))==ORIGINAL_ENTRY_PIN,
         "original_search_entrypoint_changed")
 require(digest(safe_bytes(old/"mount.py"))==ORIGINAL_MOUNT_PIN,
         "original_search_mount_changed")
 require(ORIGINAL in safe_bytes(PRIOR).decode("utf-8"),"original_owner_dropin_changed")

def source_pins(folder):
 for file,expected in PINS.items():
  require(digest(safe_bytes(folder/file))==expected,"candidate_changed:"+file)
 require(digest(safe_bytes(REHEARSAL))==REHEARSAL_PIN,"read_only_rehearsal_changed")
 for file,source in (
  ("revenue_crm_multi_pipeline.py",ROOT/"empire_os/revenue_crm_multi_pipeline.py"),
  ("revenue_crm_multi_pipeline_board.html",ROOT/"empire_os/static/revenue_crm_multi_pipeline_board.html"),
  ("revenue_crm_multi_pipeline_board.js",ROOT/"empire_os/static/revenue_crm_multi_pipeline_board.js"),
 ):
  require(digest(safe_bytes(source))==PINS[file],"original_CRM_source_drift:"+file)

def rehearsal(root):
 spec=importlib.util.spec_from_file_location("empire_crm_release_rehearsal_20261112",REHEARSAL)
 module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 module.rehearse(root)

def baseline():
 require(os.geteuid()==0,"root_for_existing_release_gate")
 require(prop("ActiveState")=="active" and prop("Result")=="success","original_service_not_healthy")
 require(prop("NeedDaemonReload")=="no","pending_unreviewed_unit_change")
 require(ORIGINAL in prop("ExecStart"),"original_service_entrypoint_changed")
 require(prop("WorkingDirectory")=="/opt/empire-ai/crm-pilot-releases/smart-crm-work-queue-20261104v1",
         "original_crm_working_directory_changed")
 require(not DROP.exists() and not DROP.is_symlink(),"override_already_present")
 require(not DEST.exists() and not DEST.is_symlink(),"versioned_release_already_present")
 previous_pins()
 source_pins(SRC)
 for path,expected in (("/health",200),("/v1/revenue-crm/prospects?limit=1",401),
                       ("/v1/revenue-crm/journeys/designer",401),(SEARCH,401),
                       ("/v1/revenue-crm/pipelines/board",404),
                       ("/v1/revenue-crm/pipelines/view",404)):
  status,_=code(path)
  require(status==expected,"existing_route_changed:"+path)
 rehearsal(CAND)

def new_smoke():
 for _ in range(18):
  if prop("ActiveState")=="active" and prop("Result")=="success":
   checks=[
    ("/health",200),
    ("/v1/revenue-crm/prospects?limit=1",401),
    ("/v1/revenue-crm/journeys/designer",401),
    (SEARCH,401),
    ("/v1/revenue-crm/pipelines/board?limit=1",401),
    ("/v1/revenue-crm/pipelines/view",200),
    ("/v1/revenue-crm/pipelines/board.js",200),
   ]
   results={path:code(path) for path,_ in checks}
   if all(results[path][0]==expected for path,expected in checks):
    require("Commercial Pipeline Control" in results["/v1/revenue-crm/pipelines/view"][1],
            "live_board_login_shell_missing")
    require("sessionBearer" in results["/v1/revenue-crm/pipelines/board.js"][1],
            "live_existing_login_adapter_missing")
    require("Demo Roofing Contractor" not in results["/v1/revenue-crm/pipelines/view"][1],
            "unexpected_mock_records_in_production_shell")
    require(prop("NeedDaemonReload")=="no","unit_reload_mismatch")
    return {path:results[path][0] for path,_ in checks}
  time.sleep(1)
 raise RuntimeError("crm_live_runtime_smoke_failed")

def restored_smoke():
 for _ in range(18):
  if prop("ActiveState")=="active" and prop("Result")=="success":
   if (code("/health")[0]==200 and
       code("/v1/revenue-crm/prospects?limit=1")[0]==401 and
       code(SEARCH)[0]==401 and
       code("/v1/revenue-crm/pipelines/view")[0]==404 and
       code("/v1/revenue-crm/pipelines/board")[0]==404 and
       ORIGINAL in prop("ExecStart") and prop("NeedDaemonReload")=="no"):
    return True
  time.sleep(1)
 return False

def receipt(status,details):
 data={
  "schema_version":"empire.crm.multi_pipeline_guarded_release.v1",
  "status":status,
  "verified_utc":datetime.now(timezone.utc).isoformat(),
  "same_private_crm_service":SERVICE,
  "same_tenant_login":True,
  "same_database_and_credential_config":True,
  "rollback_remove_only_new_unit_dropin":str(DROP),
  "original_release_files_overwritten":False,
  "production_db_writes":False,
  "customer_emails_sent":False,
  "paid_actions_executed":False,
  "founder_authenticated_live_acceptance":False,
  "new_sales_writer_or_migration":False,
  **details,
 }
 if not BACKUP.exists():BACKUP.mkdir(mode=0o700,parents=True)
 path=BACKUP/"receipt.json"
 content=(json.dumps(data,sort_keys=True,indent=2)+"\n").encode()
 fd,tmp=tempfile.mkstemp(dir=BACKUP,prefix=".receipt-")
 try:
  with os.fdopen(fd,"wb") as f:
   f.write(content);f.flush();os.fsync(f.fileno());os.fchmod(f.fileno(),0o600);os.fchown(f.fileno(),0,0)
  os.replace(tmp,path)
 finally:
  if os.path.exists(tmp):os.unlink(tmp)
 print(json.dumps(data,sort_keys=True),flush=True)

def deploy():
 require(os.geteuid()==0,"root_required")
 fd=os.open(LOCK,os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
 with os.fdopen(fd,"w") as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  baseline()
  BACKUP.parent.mkdir(parents=True,mode=0o700,exist_ok=True)
  require(BACKUP.parent.stat().st_uid==0 and BACKUP.parent.stat().st_mode&0o077==0,
          "backup_parent_not_private")
  BACKUP.mkdir(mode=0o700)
  # Frozen original drop-in for independent comparison, no secret bytes.
  (BACKUP/"original_dropin.copy").write_bytes(safe_bytes(PRIOR))
  os.chmod(BACKUP/"original_dropin.copy",0o600)
  new_drop=("[Service]\n"
    "# Add only the bounded 3-route Pipedrive-style board to the existing CRM.\n"
    "# Reuse all previous auth, signed membership and limited tenant DB logins.\n"
    "ExecStart=\n"
    "ExecStart=/srv/empire_os/.venv/bin/uvicorn "+NEW+
    " --app-dir "+str(DEST)+" --host 127.0.0.1 --port 8783 --no-proxy-headers\n")
  (BACKUP/"new_dropin.reviewed").write_text(new_drop)
  os.chmod(BACKUP/"new_dropin.reviewed",0o600)
  require(not DEST.exists(),"concurrent_new_destination")
  PKG.mkdir(parents=True,mode=0o755)
  for filename,pin in PINS.items():
   target=PKG/filename
   with target.open("xb") as stream:
    data=safe_bytes(SRC/filename)
    require(digest(data)==pin,"source_race")
    stream.write(data);stream.flush();os.fsync(stream.fileno())
   os.chmod(target,0o644)
  require(digest(safe_bytes(PKG/"entrypoint.py"))==PINS["entrypoint.py"],"copy_error")
  rehearsal(DEST)
  require(not DROP.exists() and ORIGINAL in prop("ExecStart"),"service_concurrent_change")
  fd=os.open(DROP,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o644)
  try:
   with os.fdopen(fd,"w") as f:
    f.write(new_drop);f.flush();os.fsync(f.fileno());os.fchmod(f.fileno(),0o644)
  except BaseException:
   if DROP.exists():DROP.unlink()
   raise
  try:
   proc("systemctl","daemon-reload")
   require(NEW in prop("ExecStart"),"new_entrypoint_not_selected")
   require(prop("NeedDaemonReload")=="no","unit_reload_failed")
   proc("systemctl","restart",SERVICE)
   checks=new_smoke()
   source_pins(PKG)
   previous_pins()
   require(NEW in prop("ExecStart"),"unexpected_service_override")
   receipt("LIVE_PRIVATE_CRM_MULTI_PIPELINE_ROUTES_VERIFIED",{
     "routes":checks,"founder_browser_signin_required":True,
     "new_sales_motions":10,"unassigned_review_lane":True,
     "production_signed_customer_record_readback":False,
     "website_gateway_or_checkout_restarted":False,
   })
  except BaseException as failure:
   try:
    require(DROP.is_file() and not DROP.is_symlink(),"unexpected_dropin_state")
    require(safe_bytes(DROP)==new_drop.encode(),"concurrent_unit_override")
    DROP.unlink()
    proc("systemctl","daemon-reload")
    require(ORIGINAL in prop("ExecStart"),"original_unit_not_selected")
    subprocess.run(["systemctl","reset-failed",SERVICE],check=True,timeout=15)
    proc("systemctl","restart",SERVICE)
    require(restored_smoke(),"private_CRM_rollback_proof_failed")
    receipt("FAILED_RESTORED_EXISTING_PRIVATE_CRM",{
      "failure_type":type(failure).__name__,
      "failure_stage":str(failure)[:140] if isinstance(failure,RuntimeError) else "inspect_server",
    })
   except BaseException as rollback:
    receipt("FAILED_CRM_RECOVERY_HELD",{
      "failure_type":type(failure).__name__,
      "rollback_failure_type":type(rollback).__name__,
    })
   raise SystemExit(1)

if __name__=="__main__":
 parser=argparse.ArgumentParser()
 parser.add_argument("--apply-founder-approved",action="store_true")
 args=parser.parse_args()
 if args.apply_founder_approved:deploy()
 else:
  baseline()
  print(json.dumps({"status":"FULL_CHAIN_CRM_MULTI_PIPELINE_PREFLIGHT_PASS",
    "customer_data_access":False,"production_writes":False,
    "service_restart":False,"new_routes":3},sort_keys=True))
