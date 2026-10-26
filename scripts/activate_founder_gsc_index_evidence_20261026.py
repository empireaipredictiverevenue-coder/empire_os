#!/usr/bin/env python3
"""Guarded one-time activation of the EXISTING Founder Search Console build.

Must be explicitly run by founder with root service authority. Verifies the
whole current app source snapshot first. Stops ONLY original Founder Console,
swaps prebuilt candidate .next atomically and restarts original systemd unit.
On failed live readback restores the original compiled .next and service.
No API, DB, website, outbound, credentials or payment writes.
"""
from __future__ import annotations

import argparse
import fcntl
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.request

ROOT = Path("/srv/empire_os")
APP = ROOT / "apps/search-command-centre"
RELEASE = Path("/home/ubuntu/empire_releases/seo_founder_indexed_evidence_20261026_v1")
SOURCE = RELEASE / "current_founder_app"
CANDIDATE = APP / ".next_seo_indexed_evidence_candidate_20261026"
ACTIVE = APP / ".next"
BACKUP = APP / ".next_before_gsc_index_evidence_20261026"
FAILED = APP / ".next_failed_gsc_index_evidence_20261026"
RECEIPT = RELEASE / "current_founder_build_preflight.json"
RESULT = RELEASE / "founder_gsc_index_evidence_activation.json"
SERVICE = "empire-founder-console.service"
LOCAL_URL = "http://127.0.0.1:3001/department/evidence"
IGNORE = {"node_modules"}

def sha(p: Path) -> str:
    return sha256(p.read_bytes()).hexdigest()

def inventory(base: Path) -> dict[str, str]:
    result = {}
    for p in base.rglob("*"):
        rel = p.relative_to(base)
        if any(part in IGNORE or part == ".next" or part.startswith(".next_")
               for part in rel.parts):
            continue
        if p.is_symlink():
            continue
        if p.is_file() and (
            rel.parts[0] in {"src", "public"} or str(rel) in {
                "next.config.ts", "package.json", "package-lock.json",
                "postcss.config.mjs", "tsconfig.json", "next-env.d.ts",
                "eslint.config.mjs",
            }
        ):
            result[str(rel)] = sha(p)
    return result

def run_command(*args: str, timeout: int = 45) -> None:
    subprocess.run(args, check=True, timeout=timeout, stdout=subprocess.DEVNULL)

def service_active() -> bool:
    return subprocess.run(
        ["systemctl", "is-active", "--quiet", SERVICE], check=False
    ).returncode == 0

def inspect_live() -> bool:
    for _ in range(16):
        try:
            with urllib.request.urlopen(LOCAL_URL, timeout=9) as response:
                body = response.read(450_000).decode("utf-8", "replace")
                if (response.status == 200 and
                    "Indexed versions" in body and
                    "five owned pages" in body and
                    "Google reported indexed version" in body):
                    return True
        except (OSError, TimeoutError):
            pass
        time.sleep(1)
    return False

def preflight():
    if not RECEIPT.is_file() or RECEIPT.is_symlink():
        raise RuntimeError("ORIGINAL_SNAPSHOT_RECEIPT_MISSING")
    if not ROOT.is_dir() or not SOURCE.is_dir() or not APP.is_dir():
        raise RuntimeError("SOURCE_OR_APP_MISSING")
    record = json.loads(RECEIPT.read_text())
    if record.get("status") != "FULL_CURRENT_FOUNDER_BUILD_PREPARED_NOT_LIVE":
        raise RuntimeError("PREPARED_BUILD_STATUS_UNTRUSTED")
    saved = record.get("snapshot_source_hashes")
    if not isinstance(saved, dict) or len(saved) < 35:
        raise RuntimeError("FULL_SOURCE_FINGERPRINT_REQUIRED")
    actual = inventory(APP)
    if saved != actual:
        names = sorted(k for k in set(saved) | set(actual)
                       if saved.get(k) != actual.get(k))
        raise RuntimeError("FOUNDER_SOURCE_DRIFT_REBUILD_REQUIRED:" + ",".join(names[:6]))
    if inventory(SOURCE) != saved:
        raise RuntimeError("SOURCE_SNAPSHOT_CHANGED_AFTER_BUILD")
    if not CANDIDATE.is_dir() or CANDIDATE.is_symlink():
        raise RuntimeError("NEW_NEXT_BUILD_NOT_STAGED")
    if (not (CANDIDATE / "BUILD_ID").is_file()
        or (CANDIDATE / "BUILD_ID").read_text().strip() != record.get("candidate_build_id")):
        raise RuntimeError("CANDIDATE_BUILD_ID_MISMATCH")
    if not ACTIVE.is_dir() or ACTIVE.is_symlink():
        raise RuntimeError("CURRENT_COMPILED_BUILD_MISSING")
    if (ACTIVE / "BUILD_ID").read_text().strip() != record.get("previous_build_id"):
        raise RuntimeError("CONCURRENT_FOUNDER_BUILD_REPLACEMENT")
    if BACKUP.exists() or FAILED.exists() or RESULT.exists():
        raise RuntimeError("ACTIVATION_OR_BACKUP_ALREADY_EXISTS")
    code = subprocess.run(
        ["git", "-C", str(ROOT), "merge-base", "--is-ancestor", "8393e75d1", "HEAD"],
        check=False,
    ).returncode
    if code != 0:
        raise RuntimeError("ORIGINAL_SEO_FOUNDER_CODE_NOT_IN_ACTIVE_BRANCH")
    if not service_active():
        raise RuntimeError("EXISTING_FOUNDER_SERVICE_NOT_RUNNING")
    return record

def record(status: str, **extra: object) -> None:
    data = {
        "schema_version": "empire.search.founder_indexed_evidence_activation.v1",
        "status": status, "original_service": SERVICE,
        "new_service_installed": False, "database_writes": False,
        "google_indexing_submission": False, "new_provider_account": False,
        "outbound_sent": False, "website_changed": False,
        **extra,
    }
    tmp = RESULT.with_name(RESULT.name + ".pending")
    tmp.write_text(json.dumps(data,sort_keys=True,indent=2)+"\n")
    os.replace(tmp, RESULT)

def activate() -> None:
    lock = Path("/run/lock/empire-founder-gsc-index-evidence-20261026.lock")
    fd = os.open(lock, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "rb") as f:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        packet = preflight()
        # Exact preflight is complete BEFORE the original service is stopped.
        run_command("systemctl", "stop", SERVICE, timeout=45)
        moved_old = False
        moved_candidate = False
        try:
            os.rename(ACTIVE, BACKUP)
            moved_old = True
            os.rename(CANDIDATE, ACTIVE)
            moved_candidate = True
            run_command("systemctl", "start", SERVICE, timeout=45)
            if not inspect_live() or not service_active():
                raise RuntimeError("ACTIVATED_FOUNDER_SEARCH_PANEL_READBACK_FAILED")
            record("ORIGINAL_FOUNDER_GSC_INDEX_EVIDENCE_LIVE_VERIFIED",
                   old_build_id=packet["previous_build_id"],
                   new_build_id=packet["candidate_build_id"],
                   loopback_console_readback_http=200,
                   old_build_rollback=str(BACKUP))
            print(json.dumps({"status":"ORIGINAL_FOUNDER_GSC_INDEX_EVIDENCE_LIVE_VERIFIED",
              "service":SERVICE,"route":"/department/evidence",
              "rollback":str(BACKUP)},sort_keys=True))
        except Exception:
            run_command("systemctl", "stop", SERVICE, timeout=45)
            if moved_candidate and ACTIVE.exists() and not FAILED.exists():
                os.rename(ACTIVE, FAILED)
            if moved_old and BACKUP.is_dir() and not ACTIVE.exists():
                os.rename(BACKUP, ACTIVE)
            try:
                run_command("systemctl", "start", SERVICE, timeout=45)
            except Exception:
                record("ROLLBACK_RESTART_FAILED_REQUIRE_OPERATOR")
                raise
            record("ROLLED_BACK_OLD_FOUNDER_BUILD_RESTORED")
            raise

def main() -> None:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--activate", action="store_true")
    args = parser.parse_args()
    if args.activate and os.geteuid() != 0:
        raise SystemExit("Privileged founder console restart required: run with sudo.")
    if args.preflight:
        record_info = preflight()
        print(json.dumps({"status":"EXISTING_FOUNDER_BUILD_READY_TO_ACTIVATE",
          "source_files_checked":len(record_info["snapshot_source_hashes"]),
          "candidate_build_id":record_info["candidate_build_id"],
          "new_service":False,"database_writes":False},sort_keys=True))
    else:
        activate()

if __name__ == "__main__":
    main()
