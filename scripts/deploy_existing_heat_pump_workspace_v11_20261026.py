#!/usr/bin/env python3
"""Scoped V11 original Workspace monitor release: hash guards + backup + rollback.

No SQL, no CRM edit, no new timer/service or outbound authority.
This intentionally preserves the pre-existing priority-payer monitor.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
from datetime import datetime, timezone

ORIGINAL = Path("/srv/empire_os")
STAGED = Path(__file__).resolve().parents[1]
RELEASE = Path("/home/ubuntu/empire_releases/heat_pump_workspace_v11_20261026")
POLL = "scripts/poll_workspace_solar_outreach_readonly.py"
CYCLE = "scripts/run_buyer_gmail_evidence_cycle.py"
HEAT = "empire_os/workspace_heat_pump_reply_tracking.py"
PRIORITY = "empire_os/workspace_priority_payer_reply.py"
EXPECTED = {
    POLL: "c7d50756ffc1b8b566c319813c37af2a0dfa54ddad7291784c309551727718fd",
    CYCLE: "e722e602ebcb0bfaba66cd8c2d67651a0202e1f6ef56d900b56b6050b3a99f94",
    PRIORITY: "b3b217c51904cf6bb7aaddb724af0778c57ca1da2944f0ede2aa86734b8e63bd",
}
MANIFEST = RELEASE / "manifest.json"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic_write(path, data, mode):
    fd, temp = tempfile.mkstemp(prefix=".workspace_v11_", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temp, mode)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def preflight():
    assert ORIGINAL.is_dir() and STAGED.is_dir()
    assert not MANIFEST.exists(), "RELEASE_ALREADY_HAS_MANIFEST"
    assert not (ORIGINAL / HEAT).exists(), "ORIGINAL_HEAT_MODULE_ALREADY_EXISTS"
    for name, expected_hash in EXPECTED.items():
        p = ORIGINAL / name
        assert p.is_file() and not p.is_symlink(), "ORIGINAL_FILE_UNSAFE:" + name
        assert digest(p) == expected_hash, "ORIGINAL_OWNER_FILE_CHANGED:" + name
    for name in (POLL, CYCLE, HEAT, PRIORITY):
        p = STAGED / name
        assert p.is_file() and not p.is_symlink(), "STAGED_FILE_INVALID:" + name
    assert digest(STAGED/PRIORITY) == EXPECTED[PRIORITY], "PRIORITY_OWNER_CODE_DRIFT"
    source = (STAGED / POLL).read_text()
    assert "collect_priority_payer_threads" in source
    assert "collect_heat_pump_threads" in source
    assert "newly_observed_heat_pump_candidates" in source
    cycle = (STAGED / CYCLE).read_text()
    assert cycle.count('"poll_workspace_solar_outreach_readonly.py"') == 1
    assert "refresh_workspace_sent_domain_receipts.py" in cycle
    assert "run_permit_compliance_cycle_observer.py" in cycle
    state = subprocess.run(["systemctl","is-active","empire-buyer-gmail-evidence.service"],
                           capture_output=True, text=True, check=False)
    assert state.stdout.strip() == "inactive", "ORIGINAL_GMAIL_SERVICE_ACTIVE_HOLD"
    return {name: digest(STAGED/name) for name in (POLL,CYCLE,HEAT)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    assert args.preflight != args.apply, "EXACTLY_ONE_MODE_REQUIRED"
    generated = preflight()
    if args.preflight:
        print(json.dumps({"status":"GUARDED_V11_PREFLIGHT_PASS",
                          "mode":"OBSERVE",
                          "stage_sha256":generated,
                          "original_owner_priority_preserved":True,
                          "production_mutated":False},sort_keys=True))
        return
    RELEASE.mkdir(mode=0o700,parents=True,exist_ok=True)
    backup = RELEASE/"original"
    backup.mkdir(mode=0o700,exist_ok=False)
    originals = {}
    for name in (POLL,CYCLE):
        p = ORIGINAL/name
        originals[name] = p.read_bytes()
        copy = backup/Path(name).name
        with copy.open("xb") as output:
            output.write(originals[name])
        copy.chmod(0o600)
    stamp = datetime.now(timezone.utc).isoformat()
    replaced = []
    try:
        # In case another owner changed the live checkout while backing up.
        for name in EXPECTED:
            assert digest(ORIGINAL/name)==EXPECTED[name], "CONCURRENT_OWNER_CHANGE:"+name
        for name in (HEAT,POLL,CYCLE):
            target=ORIGINAL/name
            if name==HEAT:
                assert not target.exists(), "NEW_MODULE_ALREADY_EXISTS"
                mode=0o644
            else:
                mode=stat.S_IMODE(target.stat().st_mode)
                assert digest(target)==EXPECTED[name], "CONCURRENT_CHANGE:"+name
            atomic_write(target,(STAGED/name).read_bytes(),mode)
            replaced.append(name)
            assert digest(target)==generated[name], "POST_WRITE_HASH_MISMATCH:"+name
        manifest={"status":"SCOPED_CODE_INSTALLED_PENDING_REAL_READBACK",
                  "deployed_at":stamp,"mode":"OBSERVE",
                  "original_owner_priority_sha256":EXPECTED[PRIORITY],
                  "original_sha256":{k:EXPECTED[k] for k in (POLL,CYCLE)},
                  "deployed_sha256":generated,
                  "backup_directory":str(backup),
                  "existing_timer_unchanged":True,
                  "outbound_enabled":False,"payment_enabled":False,
                  "database_migrations":False,"crm_login_security_modified":False}
        atomic_write(MANIFEST,(json.dumps(manifest,indent=2,sort_keys=True)+"\n").encode(),0o600)
        print(json.dumps({"status":manifest["status"],
                          "deployed_sha256":generated,
                          "rollback_backups":str(backup),
                          "original_owner_priority_untouched":True},sort_keys=True))
    except BaseException:
        # Roll back only the files we installed. Do not touch the other owner's
        # priority module or wider original checkout.
        for name in reversed(replaced):
            target=ORIGINAL/name
            if name==HEAT and digest(target)==generated[name]:
                target.unlink()
            elif name in originals and digest(target)==generated[name]:
                atomic_write(target,originals[name],0o644)
        raise


if __name__ == "__main__":
    main()
