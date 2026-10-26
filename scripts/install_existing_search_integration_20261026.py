"""Bounded file overlay of already-tested SEO/GSC/earned authority feature scope.

No git branch reset, no DB migrations, no service or website touches.
Requires byte-identical verified feature baseline before replacing each file.
"""
from __future__ import annotations
import hashlib, json, os, shutil, subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path("/srv/empire_os")
SOURCE=Path("/home/ubuntu/empire_worktrees/seo_unified_existing_stack_release_20261026")
RELEASE=Path("/home/ubuntu/empire_releases/seo_unified_existing_stack_20261026_v1")
REL=(
 "empire_os/search_intelligence/api.py",
 "empire_os/search_intelligence/earned_authority_reconciliation.py",
 "empire_os/search_intelligence/owned_url_inspection.py",
 "empire_os/weekly_keyword_intent_review.py",
 "scripts/inspect_owned_gsc_indexed_version_readonly.py",
 "tests/search_intelligence/test_owned_gsc_indexed_version_api_20261026.py",
 "tests/search_intelligence/test_owned_gsc_url_inspection.py",
 "tests/search_intelligence/test_earned_authority_reconciliation_20261026.py",
 "tests/test_weekly_keyword_intent_review_20261026.py",
 "docs/seo/EMPIRE_UNIFIED_SEO_AEO_GEO_AI_SEARCH_RESEARCH_20261026.md",
 "docs/seo/EMPIRE_UNIFIED_SEARCH_EXISTING_STACK_RELEASE_20261026.md",
 "docs/seo/EMPIRE_BACKLINK_EDITORIAL_EXCHANGE_RECONCILIATION_20261026.md",
 "docs/search/MARCUS_WEEKLY_SEARCH_OPPORTUNITY_RELEASE_20261026.md",
)
def sha(data): return hashlib.sha256(data).hexdigest()
def git(*args): return subprocess.run(["git","-C",str(ROOT),*args],capture_output=True,text=True,check=True).stdout
def baseline(rel):
 p=subprocess.run(["git","-C",str(SOURCE),"show",f"HEAD^:{rel}"],capture_output=True)
 return p.stdout if p.returncode==0 else None

def main():
 if RELEASE.exists():raise RuntimeError("release_path_already_exists_no_overwrite")
 if git("status","--porcelain","--",*REL).strip():
  # Explicit new paths in current workspace cannot be untracked already.
  raise RuntimeError("production_target_files_have_uncommitted_owner_edits")
 manifest=[]
 for rel in REL:
  src=SOURCE/rel; dest=ROOT/rel
  if not src.is_file() or src.is_symlink():raise RuntimeError("source_missing_or_symlink:"+rel)
  expected=baseline(rel)
  if dest.exists() and (not dest.is_file() or dest.is_symlink()):
   raise RuntimeError("production_target_not_normal_file:"+rel)
  current=dest.read_bytes() if dest.exists() else None
  if expected is None and current is not None:
   raise RuntimeError("new_file_collides_with_other_agent:"+rel)
  if expected is not None and current != expected:
   raise RuntimeError("production_source_drift_since_feature_baseline:"+rel)
  manifest.append({"relative_path":rel,"pre_sha256":sha(current) if current else None,
                   "post_sha256":sha(src.read_bytes()),
                   "existed_pre":current is not None})
 RELEASE.mkdir(parents=True,mode=0o700)
 (RELEASE/"before").mkdir(mode=0o700)
 (RELEASE/"after").mkdir(mode=0o700)
 try:
  # Back up all pre-images BEFORE a production byte changes.
  for item in manifest:
   rel=item["relative_path"]; dest=ROOT/rel
   if item["existed_pre"]:
    backup=RELEASE/"before"/rel
    backup.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(dest,backup)
   candidate=RELEASE/"after"/rel
   candidate.parent.mkdir(parents=True,exist_ok=True)
   shutil.copy2(SOURCE/rel,candidate)
  stamp={"schema_version":"empire.seo.unified_existing_stack_release.v1",
         "started_utc":datetime.now(timezone.utc).isoformat(),
         "source_commit":subprocess.check_output(["git","-C",str(SOURCE),"rev-parse","HEAD"],text=True).strip(),
         "scope":"source_files_only_search_intelligence_keyword_backlinks_google_index_inspection",
         "status":"STAGED_BACKUP_VERIFIED",
         "files":manifest,"website_changed":False,"database_writes":False,
         "services_restarted":False,"outbound_sent":False,"payments_changed":False}
  (RELEASE/"preflight.json").write_text(json.dumps(stamp,indent=2,sort_keys=True)+"\n")
  # Copy only exact reviewed files. Do not touch concurrently modified paths.
  for item in manifest:
   rel=item["relative_path"]; dest=ROOT/rel
   current=dest.read_bytes() if dest.exists() else None
   if (sha(current) if current is not None else None)!=item["pre_sha256"]:
    raise RuntimeError("concurrent_production_target_drift:"+rel)
   dest.parent.mkdir(parents=True,exist_ok=True)
   temp=dest.with_name(dest.name+".seo_20261026_candidate")
   if temp.exists():raise RuntimeError("unexpected_temporary_file:"+rel)
   shutil.copy2(RELEASE/"after"/rel,temp)
   os.replace(temp,dest)
   if sha(dest.read_bytes()) != item["post_sha256"]:
    raise RuntimeError("installed_byte_mismatch:"+rel)
  stamp["status"]="SOURCE_INSTALLED_TESTS_PENDING"
  stamp["completed_source_install_utc"]=datetime.now(timezone.utc).isoformat()
  (RELEASE/"install_receipt.json").write_text(json.dumps(stamp,indent=2,sort_keys=True)+"\n")
  print(json.dumps({"status":stamp["status"],"files":len(manifest),"source_commit":stamp["source_commit"],
                    "receipt":str(RELEASE/"install_receipt.json")},sort_keys=True))
 except Exception:
  # Avoid silently reverting potential concurrent changes; retain backups for review.
  (RELEASE/"manual_recovery_required").write_text("Check install_receipt and exact backed-up hashes before targeted rollback\n")
  raise

if __name__=="__main__":
 main()
