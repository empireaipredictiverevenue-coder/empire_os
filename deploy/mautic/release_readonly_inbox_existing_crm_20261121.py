#!/usr/bin/env python3
"""One-owner, root-only, rollback-safe additive Mautic inbox review release.

Stage is reversible and changes NO service. Apply has an exact founder scope,
requires current private CRM owner pin, safe no-send state, stages + imports
the release, and reloads only the existing CRM service once. There are no
source/identity claims, contact imports, DB grants, SMTP or producer changes.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
import pwd
import re
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import time

WORKTREE = Path("/home/ubuntu/empire_worktrees/mautic_integrated_active_20261119")
ROOT = Path("/opt/empire-ai/crm-mautic-readonly-20261121-v3")
PRIOR = Path("/opt/empire-ai/crm-documents-firstparty-20261121-v2")
PRIOR_ENTRY = PRIOR / "private_crm_documents_entrypoint_20261120.py"
PRIOR_SHA = "797ee750999ea01c133914f80829b4cf0228aea59addcfbdf5f055c8d27efbd0"
EXTENSION = ROOT / "empire_os"
ENTRY = "mautic_readonly_existing_crm_overlay_20261121.py"
SOURCES = {
    ("deploy/mautic/" + ENTRY): (
        ROOT / ENTRY,
        "e7682b8c7766f511ee14284ff7f480fe987a2f4bdc88ce23a73aaf9be597b53f",
    ),
    "empire_os/mautic_crm_review_api.py": (
        EXTENSION / "mautic_crm_review_api.py",
        "9fd7f8347acb955a7857a55a31c2747921d7234e94c35c797dc92153435d969f",
    ),
    "empire_os/mautic_crm_inbox.py": (
        EXTENSION / "mautic_crm_inbox.py",
        "a63e4f0d98a66cc8f91e2bfb9c9e2491b89209957fc948b7b4bd88ff504ce059",
    ),
}
UNIT = "empire-revenue-crm-pilot.service"
PORT = "http://127.0.0.1:8783"
REVIEW = "/v1/revenue-crm/integrations/mautic/inbox/reviews"
DROP = Path("/etc/systemd/system/empire-revenue-crm-pilot.service.d/"
            "zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz-mautic-readonly-20261121-v3.conf")
PRIOR_CMD = ("private_crm_documents_entrypoint_20261120:app --app-dir "
             "/opt/empire-ai/crm-documents-firstparty-20261121-v2")
RELEASE_CMD = ("/srv/empire_os/.venv/bin/uvicorn " + ENTRY[:-3]
               + ":app --app-dir " + str(ROOT)
               + " --host 127.0.0.1 --port 8783 --no-proxy-headers")


def run(*args: str, timeout: int = 14) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout)


def pinned(path: Path, expected: str, *, owner_root: bool = False) -> None:
    meta = path.lstat()
    if (not stat.S_ISREG(meta.st_mode) or meta.st_mode & 0o022
        or (owner_root and meta.st_uid != 0)
        or sha256(path.read_bytes()).hexdigest() != expected):
        raise RuntimeError("pinned_file_invalid:" + path.name)


def current() -> tuple[str, int]:
    if os.geteuid() != 0:
        raise RuntimeError("root_operator_required")
    if DROP.exists() or DROP.is_symlink():
        raise RuntimeError("mautic_readonly_dropin_already_exists")
    pinned(PRIOR_ENTRY, PRIOR_SHA, owner_root=True)
    proc = run("systemctl", "show", UNIT, "--value", "-p", "ExecStart")
    if proc.returncode or PRIOR_CMD not in proc.stdout or ENTRY[:-3] in proc.stdout:
        raise RuntimeError("original_crm_owner_entrypoint_changed")
    pid = int(run("systemctl", "show", UNIT, "--value", "-p", "MainPID").stdout.strip())
    if pid <= 1 or run("systemctl", "is-active", UNIT).stdout.strip() != "active":
        raise RuntimeError("original_crm_unavailable")
    return proc.stdout, pid


def validate_sources() -> None:
    for src, (dest, digest) in SOURCES.items():
        path = WORKTREE / src
        pinned(path, digest)
        if dest.exists() or dest.is_symlink():
            pinned(dest, digest, owner_root=True)
    for folder in (ROOT, EXTENSION):
        if folder.exists():
            meta = folder.lstat()
            if not stat.S_ISDIR(meta.st_mode) or meta.st_uid != 0 or meta.st_mode & 0o022:
                raise RuntimeError("release_directory_unsafe")


def stage() -> None:
    validate_sources()
    for d in (ROOT, EXTENSION):
        d.mkdir(mode=0o755, exist_ok=True)
        os.chown(d, 0, 0)
        d.chmod(0o755)
    for source, (target, digest) in SOURCES.items():
        src = WORKTREE / source
        if target.exists():
            continue
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
        with os.fdopen(fd, "wb") as out:
            out.write(src.read_bytes())
            out.flush()
            os.fsync(out.fileno())
        os.chown(target, 0, 0)
        target.chmod(0o644)
    validate_sources()


def probe(pid: int) -> dict[str, object]:
    # Child receives the live process's environment; nothing private is
    # printed, persisted or exposed in test receipts.
    private_env = {}
    for chunk in Path(f"/proc/{pid}/environ").read_bytes().split(b"\0"):
        if b"=" in chunk:
            k, v = chunk.split(b"=", 1)
            private_env[k.decode("utf-8", errors="strict")] = v.decode(
                "utf-8", errors="surrogateescape")
    private_env["PYTHONPATH"] = (str(ROOT) + ":" + private_env.get("PYTHONPATH", ""))
    script = (
        "import json,importlib;"
        "from fastapi.testclient import TestClient;"
        "m=importlib.import_module('mautic_readonly_existing_crm_overlay_20261121');"
        "c=TestClient(m.app);"
        "p='/v1/revenue-crm/integrations/mautic/inbox/reviews';"
        "h=c.get('/health');r=c.get(p);"
        "assert h.status_code==200,(h.status_code,h.text[:60]);"
        "assert r.status_code==401,(r.status_code,r.text[:90]);"
        "assert m.app.state.mautic_review_readonly_only is True;"
        "print(json.dumps({'health':h.status_code,'unauthenticated_inbox':r.status_code,"
        "'existing_service':'reused','no_contact_or_sender':True}))"
    )
    # The live CRM is User=ubuntu. Private pilot files validate file owner
    # against process EUID; a root import is not a valid production canary.
    identity = pwd.getpwnam("ubuntu")
    proc = subprocess.run(
        ["/srv/empire_os/.venv/bin/python", "-B", "-c", script],
        env=private_env,
        cwd="/opt/empire-ai/crm-pilot-releases/smart-crm-work-queue-20261104v1",
        user=identity.pw_uid, group=identity.pw_gid, extra_groups=[],
        capture_output=True, text=True, timeout=55)
    if proc.returncode:
        # Emit only a strict non-secret diagnostic class, never stderr or env.
        diagnostics = tuple(proc.stderr.splitlines())
        classes = ("ModuleNotFoundError", "ImportError", "RuntimeError",
                   "AssertionError", "PermissionError", "ValueError",
                   "AttributeError", "KeyError", "OSError", "TypeError",
                   "FileNotFoundError", "SyntaxError")
        found = next((line.split(":", 1)[0].strip() for line in reversed(diagnostics)
                      if line.split(":", 1)[0].strip() in classes), "UNKNOWN")
        frames = re.findall(r'^  File "([^"]+)", line ([0-9]+)', proc.stderr, re.M)
        trace = ",".join(Path(name).name + ":" + line for name, line in frames[-5:])
        raise RuntimeError("additive_crm_probe_failed_" + found + ":" + trace)
    obj = json.loads(proc.stdout.strip())
    if obj["unauthenticated_inbox"] != 401 or obj["health"] != 200:
        raise RuntimeError("unexpected_mautic_review_probe_result")
    return obj


def local_http(path: str) -> int:
    proc = run("curl", "--silent", "--output", "/dev/null",
               "--max-time", "3", "--write-out", "%{http_code}", PORT + path)
    try:
        return int(proc.stdout.strip())
    except ValueError:
        return 0


def activate(pid: int) -> None:
    if local_http("/health") != 200:
        raise RuntimeError("existing_crm_health_not_200")
    if local_http(REVIEW) != 404:
        raise RuntimeError("mautic_review_already_running")
    # Preserve the current protected CRM, predictive and document routes.
    original_codes = {
        "/v1/revenue-crm/prospects": 401,
        "/v1/revenue-crm/predictive-diagnostic": 401,
        "/v1/revenue-crm/documents": 307,
    }
    for route, expected in original_codes.items():
        if local_http(route) != expected:
            raise RuntimeError("existing_crm_route_baseline_changed")
    result = probe(pid)
    receipt = Path("/var/backups/empiredb/mautic-review-crm-additive-20261121")
    receipt.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chown(receipt, 0, 0)
    receipt.chmod(0o700)
    safe = {
        "prior_entrypoint_sha256": PRIOR_SHA,
        "prior_execstart": PRIOR_CMD,
        "new_execstart": RELEASE_CMD,
        "service": UNIT,
        "review_only": True,
        "no_db_migration": True,
        "no_contacts_imported": True,
        "outbound_authorized": False,
        "offline_probe": result,
    }
    (receipt / "release.json").write_text(json.dumps(safe, indent=2) + "\n")
    (receipt / "release.json").chmod(0o600)
    if DROP.parent.stat().st_uid != 0:
        raise RuntimeError("systemd_dropin_parent_not_root_owned")
    drop_text = ("[Service]\n# Existing founder CRM; read-only Mautic inbox only.\n"
                 "# No source, tenant writer, send or customer import.\n"
                 "ExecStart=\nExecStart=" + RELEASE_CMD + "\n")
    fd = os.open(DROP, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    with os.fdopen(fd, "w") as out:
        out.write(drop_text)
        out.flush()
        os.fsync(out.fileno())
    os.chown(DROP, 0, 0)
    DROP.chmod(0o644)
    try:
        if run("systemctl", "daemon-reload", timeout=15).returncode:
            raise RuntimeError("daemon_reload_failed")
        if run("systemctl", "restart", UNIT, timeout=35).returncode:
            raise RuntimeError("crm_restart_failed")
        for _ in range(30):
            if local_http("/health") == 200 and local_http(REVIEW) == 401:
                break
            time.sleep(1)
        else:
            raise RuntimeError("mautic_review_live_http_readback_failed")
        for route, expected in original_codes.items():
            if local_http(route) != expected:
                raise RuntimeError("original_crm_route_regression")
        active = run("systemctl", "show", UNIT, "--value", "-p", "ExecStart").stdout
        if ENTRY[:-3] not in active:
            raise RuntimeError("wrong_live_crm_entrypoint")
        print(json.dumps({"status": "LIVE_PRIVATE_REVIEW_ONLY", "health": 200,
             "unauthenticated_inbox": 401, "no_contact_import": True,
             "no_webhook_ingress": True, "no_outbound_authority": True}))
    except Exception:
        # Roll back our single drop-in and return original untouched service.
        DROP.unlink(missing_ok=True)
        run("systemctl", "daemon-reload", timeout=15)
        run("systemctl", "restart", UNIT, timeout=35)
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--preflight", action="store_true")
    g.add_argument("--stage", action="store_true")
    g.add_argument("--probe", action="store_true")
    g.add_argument("--activate-founder-approved-readonly-inbox-20261121",
                   action="store_true")
    args = parser.parse_args()
    try:
        _, pid = current()
        validate_sources()
        if args.stage:
            stage()
            print("MAUTIC_CRM_READONLY_RELEASE=STAGED_ROOT_OWNED")
        elif args.probe:
            print(json.dumps({"status": "STAGED_IMPORT_READONLY_PROBE_PASS", "evidence": probe(pid)}))
        elif args.preflight:
            print("MAUTIC_CRM_READONLY_RELEASE=PREFLIGHT_PASS")
        else:
            stage()
            activate(pid)
    except Exception as exc:
        print("MAUTIC_CRM_READONLY_RELEASE=HOLD_" + str(exc), file=sys.stderr)
        raise SystemExit(3)
