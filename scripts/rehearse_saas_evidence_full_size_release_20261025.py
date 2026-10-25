"""Full-sized paired SaaS publication rehearsal; ALWAYS isolated temp copies.

This exercises the actual exact-scope release transaction with all 662
production-baseline file bytes, the 672-file candidate, and fault-injected
post-copy rollback. It NEVER writes to apps/empire-public-site/out, owns no
root archive, and confers no release permission.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import shutil
import tempfile

from scripts import owner_publish_saas_evidence_20261025 as publisher
from scripts import review_saas_evidence_release_candidate_20261025 as qa


class InjectedRollback(Exception):
    pass


def run() -> dict:
    qa.review()
    base=qa.read_index(qa.LIVE)
    final=qa.read_index(qa.CANDIDATE)
    # Two exact payload replacements, 10 assets, 660 untouched existing.
    changed=sorted(k for k in base if base[k]!=final[k])
    added=sorted(set(final)-set(base))
    if changed!=sorted(qa.REPLACE) or len(added)!=10 or len(base)!=662 or len(final)!=672:
        raise ValueError("RELEASE_REHEARSAL_SCOPE_UNEXPECTED")
    results=[]
    with tempfile.TemporaryDirectory(prefix="empire-saas-release-full-rehearsal-",
                                     dir="/home/ubuntu/empire_worktrees") as scratch:
        tmp=Path(scratch)
        for mode in ("positive","rollback"):
            live=tmp/mode
            shutil.copytree(qa.LIVE,live)
            if qa.read_index(live)!=base:
                raise ValueError("ISOLATED_BASELINE_NOT_IDENTICAL")
            def after_install():
                if qa.read_index(live)!=final:
                    raise ValueError("POST_APPLY_INVENTORY_NOT_PINNED")
                if mode=="rollback":
                    raise InjectedRollback("SYNTHETIC_BROWSER_POSTCHECK_FAILURE")
            if mode=="positive":
                receipt=publisher.transaction(
                    live, qa.CANDIDATE, base, final,
                    on_applied=after_install,
                )
                if qa.read_index(live)!=final:
                    raise ValueError("SUCCESS_RESULT_NOT_IDENTICAL_TO_CANDIDATE")
                results.append({
                    "scenario":"full_662_to_672_success",
                    "expected_total":672,
                    "new_file_count":len(added),
                    "replaced_route_count":len(changed),
                    "other_original_file_bytes_preserved":660,
                    "result":receipt,
                    "exact_final_inventory_verified":True,
                })
            else:
                caught=False
                try:
                    publisher.transaction(
                        live, qa.CANDIDATE,base,final,on_applied=after_install)
                except InjectedRollback:
                    caught=True
                if not caught or qa.read_index(live)!=base:
                    raise ValueError("FULL_SIZE_ROLLBACK_DID_NOT_RESTORE_ALL_662")
                results.append({
                    "scenario":"full_size_injected_post_install_failure",
                    "injected_failure_confirmed":caught,
                    "exact_662_original_file_hashes_restored":True,
                    "unrelated_pages_preserved":True,
                    "ten_new_assets_removed":True,
                })
    if qa.read_index(qa.LIVE)!=base:
        raise ValueError("PRODUCTION_WAS_CHANGED_DURING_REHEARSAL")
    return {
        "schema_version":"empire.website.saas_evidence_full_size_rehearsal.v1",
        "status":"PASS_FULL_SIZE_ISOLATED_SCOPED_RELEASE_AND_ROLLBACK",
        "checked_at_utc":datetime.now(timezone.utc).isoformat(),
        "live_baseline_file_count":662,
        "candidate_file_count":672,
        "paired_route_replacements":sorted(qa.REPLACE),
        "new_hashed_assets":len(added),
        "preserved_existing_site_files":660,
        "scenarios":results,
        "production_live_tree_unchanged":True,
        "protected_root_rollback_created":False,
        "independent_astra_owner_signoff_verified":False,
        "publication_authorized":False,
        "publication_performed":False,
    }


def main() -> None:
    print(json.dumps(run(),sort_keys=True))


if __name__=="__main__":
    main()
