"""Guarded Data Cloud owner search-source refresh on ORIGINAL gateway.

Fresh root-frozen v3 source + independently pinned release receipt; additive
systemd environment only (the original owned-index gateway ExecStart is kept).
No SQL, credentials, tenant changes, paid APIs or new service.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import stat
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

DATA = Path("/home/ubuntu/empire_worktrees/data_cloud_source_provenance_review_20261109")
SOURCE = Path("/home/ubuntu/empire_worktrees/search_fabric_business_growth_20261113")
SOURCE_COMMIT = "2dd2a063533aee021f2d85bdbc15877aebd319c9"
SOURCE_FILE = "empire_os/search_fabric/public_fallback.py"
SOURCE_SHA = "1edeec22be82f3be75588e94a251d418134afc484ba86cdee9e45607b1fbe993"
V2 = Path("/opt/empire-ai/data-cloud-founder-search-20261109-v2")
V3 = Path("/opt/empire-ai/data-cloud-founder-search-20261114-v3")
ORIGINAL_RECEIPT = Path("/var/lib/empire-data-cloud-search-owner-20261109-v2/OWNER_RECEIPT.json")
STATE = Path("/var/lib/empire-data-cloud-search-owner-20261114-v3")
RECEIPT = STATE / "OWNER_RECEIPT.json"
JOURNAL = STATE / "RELEASE.json"
OVERLAY = Path("/etc/systemd/system/empire-public-gateway.service.d/zzzzzzzzzzzzzzzzzzzzz-data-cloud-search-quality-20261114-v3.conf")
SERVICE = "empire-public-gateway.service"
CRM = "empire-revenue-crm-pilot.service"
ENTRY = "data_cloud_public_entrypoint_20261107.py"
ADAPTER = "empire_os/predictive_cloud_customer_api/gateway_candidate_entrypoint.py"
PROVENANCE = "empire_os/predictive_cloud_customer_api/SOURCE_PROVENANCE.json"
OWNER_ENTRY = "owned_index_gateway_entrypoint_20261113v2:app"


def assert_true(value, reason):
    if not value:
        raise RuntimeError(reason)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def compact(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def cmd(args, *, binary=False):
    res = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         timeout=30,
                         env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LC_ALL": "C"})
    assert_true(res.returncode == 0, "owner_operator_command_failed")
    return res.stdout if binary else res.stdout.decode().strip()


def service_active(unit):
    res = subprocess.run(
        ["systemctl", "is-active", unit],
        capture_output=True, timeout=5,
        env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LC_ALL": "C"},
    )
    return res.returncode == 0 and res.stdout.strip() == b"active"


def git(folder, *args, binary=False):
    return cmd(["git", "-c", "safe.directory=" + str(folder),
                "-C", str(folder), *args], binary=binary)


def pinned_file(path, *, owner=None):
    assert_true(path.is_file() and not path.is_symlink(),
                "release_source_file_missing")
    s = path.stat()
    assert_true(not (s.st_mode & 0o002) and (owner is None or s.st_uid == owner),
                "release_source_ownership_or_mode_changed")
    return path.read_bytes()


def approve_source(commit):
    assert_true(bool(re.fullmatch(r"[0-9a-f]{40}", commit or "")),
                "exact_data_cloud_source_commit_required")
    assert_true(git(DATA, "rev-parse", "HEAD") == commit,
                "data_cloud_source_head_changed")
    assert_true(git(DATA, "branch", "--show-current") ==
                "feature/data-cloud-source-provenance-review-20261109",
                "data_cloud_owner_branch_changed")
    assert_true(not git(DATA, "status", "--porcelain", "--untracked-files=all"),
                "data_cloud_source_worktree_not_clean")
    assert_true(git(SOURCE, "rev-parse", "HEAD") == SOURCE_COMMIT,
                "original_search_fabric_owner_commit_changed")
    producer = pinned_file(SOURCE / SOURCE_FILE, owner=1000)
    assert_true(sha(producer) == SOURCE_SHA, "source_fabric_fix_sha_changed")
    assert_true(git(SOURCE, "show", SOURCE_COMMIT + ":" + SOURCE_FILE,
                    binary=True) == producer,
                "search_fabric_source_not_from_owner_commit")
    for relative in (ADAPTER, PROVENANCE):
        blob = pinned_file(DATA / relative, owner=1000)
        assert_true(git(DATA, "show", commit + ":" + relative,
                        binary=True) == blob,
                    "data_cloud_adapter_not_exact_committed_blob")
    return {"source_sha": SOURCE_SHA,
            "adapter_sha": sha((DATA / ADAPTER).read_bytes()),
            "provenance_sha": sha((DATA / PROVENANCE).read_bytes())}


def baseline(*, resume=False):
    assert_true(cmd(["systemctl", "is-active", SERVICE]) == "active"
                and cmd(["systemctl", "is-active", CRM]) == "active",
                "original_gateway_or_crm_inactive")
    execution = cmd(["systemctl", "show", SERVICE, "-p", "ExecStart", "--value"])
    assert_true(OWNER_ENTRY in execution
                and "--host 127.0.0.1 --port 80 --workers 1" in execution,
                "current_owned_index_gateway_owner_changed")
    dropins = cmd(["systemctl", "show", SERVICE, "-p", "DropInPaths", "--value"])
    assert_true("search-fabric-owned-20261113v2.conf" in dropins
                and not OVERLAY.exists() and str(OVERLAY) not in dropins,
                "gateway_dropin_owner_collision")
    environment = cmd(["systemctl", "show", SERVICE, "-p", "Environment", "--value"])
    tokens = shlex.split(environment)
    pythonpaths = [t[len("PYTHONPATH="):] for t in tokens
                   if t.startswith("PYTHONPATH=")]
    assert_true(len(pythonpaths) == 1, "original_pythonpath_unavailable")
    pythonpath = pythonpaths[0]
    assert_true("/opt/empire-ai/search-fabric-owned-20261113v2" in pythonpath
                and str(V2) in pythonpath, "original_release_path_changed")
    if resume:
        assert_true(V3.is_dir() and STATE.is_dir() and JOURNAL.is_file(),
                    "reviewed_v3_rollback_artifacts_not_present")
        assert_true(json.loads(JOURNAL.read_bytes()).get("phase") == "rolled_back",
                    "original_v3_release_not_safely_rolled_back")
    else:
        assert_true(not V3.exists() and not STATE.exists(), "v3_release_already_present")
    old_receipt = json.loads(pinned_file(ORIGINAL_RECEIPT, owner=0))
    assert_true(
        old_receipt.get("scope") == "FOUNDER_ONLY_FIRST_PARTY_SEARCH_NO_PAID_API"
        and old_receipt.get("source_id") == "empire_search_fabric_public"
        and len(old_receipt.get("files", {})) >= 11
        and all(old_receipt.get("verified_requirements", {}).values()),
        "original_owner_source_receipt_invalid",
    )
    for name, digest in old_receipt["files"].items():
        relative = Path(name)
        assert_true(not relative.is_absolute() and ".." not in relative.parts,
                    "original_receipt_path_invalid")
        file = V2 / relative
        assert_true(sha(pinned_file(file, owner=0)) == digest,
                    "original_frozen_release_hash_mismatch")
    return {"execution": execution, "pythonpath": pythonpath,
            "dropins_sha": sha(dropins.encode()), "old_receipt": old_receipt}


def set_frozen(relative, contents):
    target = V3 / relative
    assert_true(target.is_file() and not target.is_symlink(),
                "v3_missing_frozen_source")
    target.chmod(0o600)
    target.write_bytes(contents)
    target.chmod(0o444)
    assert_true(target.stat().st_uid == 0 and sha(target.read_bytes()) == sha(contents),
                "v3_source_writeback_mismatch")


def stage(pre, sources, commit):
    # Original public gateway runs as ubuntu. Its already-approved source
    # receipt is root-owned, read-only 0444 under a traversable 0755 dir;
    # preserve that exact custody, not a root-private path the service cannot read.
    STATE.mkdir(mode=0o755)
    STATE.chmod(0o755)
    shutil.copytree(V2, V3, symlinks=False)
    assert_true(V3.stat().st_uid == 0 and not V3.is_symlink(),
                "v3_frozen_tree_ownership_changed")
    base = (V2 / ENTRY).read_text()
    old_version = 'RELEASE = Path("' + str(V2) + '")'
    new_version = 'RELEASE = Path("' + str(V3) + '")'
    old_proof = 'Path("/var/lib/empire-data-cloud-search-owner-20261109-v2/OWNER_RECEIPT.json")'
    new_proof = 'Path("' + str(RECEIPT) + '")'
    assert_true(base.count(old_version) == 1 and base.count(old_proof) == 1,
                "original_data_cloud_entrypoint_changed")
    modified = base.replace(old_version, new_version, 1).replace(old_proof, new_proof, 1)
    set_frozen(ENTRY, modified.encode())
    set_frozen(SOURCE_FILE, pinned_file(SOURCE / SOURCE_FILE, owner=1000))
    set_frozen(ADAPTER, pinned_file(DATA / ADAPTER, owner=1000))
    set_frozen(PROVENANCE, pinned_file(DATA / PROVENANCE, owner=1000))
    # Already-loaded canonical empire_os.search_fabric package needs its
    # frozen search subdirectory before the v3 module imports begin.
    old_path = "empire_os.__path__.insert(0, str(extension))"
    new_path = (old_path + "\n"
                "import empire_os.search_fabric as _frozen_search_fabric\n"
                "_frozen_search_fabric.__path__.insert(0, str(extension / 'search_fabric'))")
    changed_entry = (V3 / ENTRY).read_text()
    assert_true(changed_entry.count(old_path) == 1, "original_package_path_anchor_changed")
    set_frozen(ENTRY, changed_entry.replace(old_path, new_path, 1).encode())
    receipt = dict(pre["old_receipt"])
    receipt["files"] = {
        name: sha(pinned_file(V3 / name, owner=0))
        for name in pre["old_receipt"]["files"]
    }
    receipt["controlled_source_refresh"] = {
        "purpose": "founder-only query relevance and already-owned DDG HTML fallback",
        "search_fabric_owner_commit": SOURCE_COMMIT,
        "data_cloud_owner_commit": commit,
        "source_sha256": sources["source_sha"],
        "paid_provider_calls_authorized": False,
        "customer_buyer_identity_verified": False,
    }
    raw = compact(receipt)
    with open(RECEIPT, "xb") as f:
        f.write(raw)
        f.flush()
        os.fsync(f.fileno())
    RECEIPT.chmod(0o444)
    digest = sha(raw)
    assert_true(sha(RECEIPT.read_bytes()) == digest,
                "new_source_receipt_digest_mismatch")
    new_env = str(V3) + ":" + pre["pythonpath"]
    text = ('[Service]\n'
            '# Preserve the current original owned-index gateway ExecStart.\n'
            'Environment="PYTHONPATH=' + new_env + '"\n'
            'Environment="PYTHONDONTWRITEBYTECODE=1"\n'
            'Environment="EMPIRE_DATA_CLOUD_SEARCH_RECEIPT_SHA256=' + digest + '"\n')
    fd = os.open(OVERLAY, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    with os.fdopen(fd, "w") as stream:
        stream.write(text)
        stream.flush()
        os.fsync(stream.fileno())
    return digest


def http(path, *, port=80, method="GET"):
    req = urllib.request.Request("http://127.0.0.1:" + str(port) + path,
                                 method=method)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(req, timeout=4) as response:
            return response.status
    except urllib.error.HTTPError as e:
        return e.code
    except (OSError, urllib.error.URLError):
        return 0


def smoke():
    for _ in range(18):
        if service_active(SERVICE) and http("/") == 200:
            break
        time.sleep(1)
    else:
        assert_true(False, "original_gateway_failed_to_start")
    expected = {
        ("/", 80, "GET"): 200,
        ("/commercial", 80, "GET"): 200,
        ("/robots.txt", 80, "GET"): 200,
        ("/v1/data/usage", 80, "GET"): 401,
        ("/v1/data/search", 80, "POST"): 401,
        ("/v1/data/site-audits", 80, "POST"): 404,
        ("/health", 8783, "GET"): 200,
    }
    for (path, port, method), status in expected.items():
        assert_true(http(path, port=port, method=method) == status,
                    "original_gateway_or_crm_route_regressed")
    running = cmd(["systemctl", "show", SERVICE, "-p", "Environment", "--value"])
    execution = cmd(["systemctl", "show", SERVICE, "-p", "ExecStart", "--value"])
    assert_true(OWNER_ENTRY in execution and ("PYTHONPATH=" + str(V3) + ":") in running,
                "v3_gateway_not_running_exact_owner_chain")
    return {"public_gateway": 200, "protected_search": 401,
            "private_crm": 200, "prior_owner_preserved": True}


def journal(state):
    STATE.mkdir(mode=0o700, exist_ok=True)
    temp = STATE / (".release-" + str(os.getpid()) + ".tmp")
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(compact(state))
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp, JOURNAL)


def rollback():
    if OVERLAY.is_file() and not OVERLAY.is_symlink():
        OVERLAY.unlink()
        cmd(["systemctl", "daemon-reload"])
        cmd(["systemctl", "restart", SERVICE])
    if STATE.is_dir():
        journal({"phase": "rolled_back", "utc": int(time.time())})
    return smoke_old()


def smoke_old():
    for _ in range(15):
        if http("/") == 200 and service_active(SERVICE):
            return True
        time.sleep(1)
    raise RuntimeError("previous_gateway_not_recovered_after_rollback")


def verify_previous_v3(pre, sources):
    """Prove staged bytes and prior rollback BEFORE modifying receipt custody."""
    payload = json.loads(RECEIPT.read_bytes())
    controlled = payload.get("controlled_source_refresh", {})
    assert_true(
        payload.get("scope") == pre["old_receipt"].get("scope")
        and payload.get("owner_actor_id") == pre["old_receipt"].get("owner_actor_id")
        and payload.get("owner_tenant_id") == pre["old_receipt"].get("owner_tenant_id")
        and controlled.get("search_fabric_owner_commit") == SOURCE_COMMIT
        and controlled.get("source_sha256") == sources["source_sha"]
        and controlled.get("paid_provider_calls_authorized") is False,
        "staged_v3_receipt_or_scope_changed",
    )
    for name, digest in payload["files"].items():
        assert_true(
            sha(pinned_file(V3 / name, owner=0)) == digest,
            "staged_v3_source_hash_changed",
        )
    assert_true(sha(pinned_file(V3 / SOURCE_FILE, owner=0)) == SOURCE_SHA,
                "staged_v3_collector_changed")
    assert_true(sha(pinned_file(V3 / ADAPTER, owner=0)) == sources["adapter_sha"],
                "staged_v3_customer_adapter_changed")
    assert_true(sha(pinned_file(V3 / PROVENANCE, owner=0)) == sources["provenance_sha"],
                "staged_v3_source_receipt_changed")
    entry = pinned_file(V3 / ENTRY, owner=0)
    assert_true(str(V3).encode() in entry and str(RECEIPT).encode() in entry,
                "staged_v3_entrypoint_changed")
    assert_true(STATE.stat().st_uid == 0 and RECEIPT.stat().st_uid == 0,
                "staged_v3_root_custody_changed")
    return sha(RECEIPT.read_bytes())


def resume_original_v3(pre, sources, commit):
    """Resume SAME previously failed frozen bytes after correcting receipt ACL."""
    digest = verify_previous_v3(pre, sources)
    # The public gateway service user is ubuntu, as for the previous
    # founder-only receipt. The protected receipt is nonsecret and SHA-pinned.
    assert_true(STATE.stat().st_mode & 0o777 == 0o700,
                "staged_v3_state_preimage_changed")
    assert_true(RECEIPT.stat().st_mode & 0o777 == 0o400,
                "staged_v3_receipt_preimage_changed")
    STATE.chmod(0o755)
    RECEIPT.chmod(0o444)
    assert_true(sha(RECEIPT.read_bytes()) == digest,
                "resume_did_not_preserve_signed_receipt_bytes")
    line = ('[Service]\n'
            '# Preserve the current original owned-index gateway ExecStart.\n'
            'Environment="PYTHONPATH=' + str(V3) + ':' + pre["pythonpath"] + '"\n'
            'Environment="PYTHONDONTWRITEBYTECODE=1"\n'
            'Environment="EMPIRE_DATA_CLOUD_SEARCH_RECEIPT_SHA256=' + digest + '"\n')
    fd = os.open(OVERLAY, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    with os.fdopen(fd, "w") as output:
        output.write(line)
        output.flush()
        os.fsync(output.fileno())
    assert_true(
        cmd(["systemctl", "show", SERVICE, "-p", "ExecStart", "--value"])
        == pre["execution"],
        "original_gateway_owner_changed_during_resume",
    )
    journal({"phase": "resuming", "previous_phase": "rolled_back",
             "source_commit": commit, "receipt_sha256": digest,
             "utc": int(time.time())})
    cmd(["systemctl", "daemon-reload"])
    cmd(["systemctl", "restart", SERVICE])
    checks = smoke()
    journal({"phase": "active", "previous_phase": "rolled_back",
             "source_commit": commit, "receipt_sha256": digest,
             "verification": checks, "utc": int(time.time())})
    return checks


def main():
    parser = argparse.ArgumentParser()
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--preflight", action="store_true")
    actions.add_argument("--apply-founder-approved", action="store_true")
    actions.add_argument("--resume-preflight", action="store_true")
    actions.add_argument("--resume-founder-approved", action="store_true")
    actions.add_argument("--rollback", action="store_true")
    parser.add_argument("--source-commit")
    args = parser.parse_args()
    assert_true(os.geteuid() == 0, "original_owner_privileged_release_required")
    if args.rollback:
        rollback()
        print("SEARCH_SOURCE_V3_ROLLBACK_PASS")
        return
    sources = approve_source(args.source_commit)
    if args.resume_preflight or args.resume_founder_approved:
        pre = baseline(resume=True)
        verify_previous_v3(pre, sources)
        if args.resume_preflight:
            print("SEARCH_SOURCE_V3_ROLLBACK_RECOVERY_PREFLIGHT_PASS")
            return
        try:
            report = resume_original_v3(pre, sources, args.source_commit)
            print("FOUNDER_SEARCH_FABRIC_ORIGINAL_V3_RELEASE_ACTIVE")
            print(json.dumps(report, sort_keys=True))
        except Exception:
            rollback()
            raise RuntimeError("guarded_v3_resume_failed_and_rolled_back")
        return
    pre = baseline()
    if args.preflight:
        print("SEARCH_SOURCE_V3_READONLY_PREFLIGHT_PASS")
        return
    try:
        digest = stage(pre, sources, args.source_commit)
        journal({"phase": "staged", "source_commit": args.source_commit,
                 "receipt_sha256": digest, "utc": int(time.time())})
        # Refuse to restart if the original owner changed while staging.
        execution = cmd(["systemctl", "show", SERVICE, "-p", "ExecStart", "--value"])
        assert_true(execution == pre["execution"], "live_original_gateway_owner_changed_during_stage")
        cmd(["systemctl", "daemon-reload"])
        cmd(["systemctl", "restart", SERVICE])
        report = smoke()
        journal({"phase": "active", "source_commit": args.source_commit,
                 "receipt_sha256": digest, "verification": report,
                 "utc": int(time.time())})
        print("FOUNDER_SEARCH_FABRIC_ORIGINAL_V3_RELEASE_ACTIVE")
        print(json.dumps(report, sort_keys=True))
    except Exception:
        rollback()
        raise RuntimeError("guarded_search_source_v3_activation_failed_rolled_back")


if __name__ == "__main__":
    main()
