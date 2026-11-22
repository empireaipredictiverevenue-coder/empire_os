"""Guarded ADDITIVE original private-CRM browser search release (13 Nov 2026).

No new service, SQL, roles, tenants, keys, paid providers or outbound.
Only freezes existing reviewed branch files and adds one private CRM drop-in.
Rollback removes only this drop-in and restores the existing multi-pipeline
CRM owner. An actual founder browser login remains necessary for the final
signed-CRM positive search UX verification.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path("/home/ubuntu/empire_worktrees/data_cloud_source_provenance_review_20261109")
RELEASE = Path("/opt/empire-ai/data-cloud-founder-browser-20261113-v1")
BASE = Path("/opt/empire-ai/crm-multi-pipeline-20261112")
BASE_FILE = BASE / "empire_crm_multi_pipeline_20261112/entrypoint.py"
BASE_SHA = "e7fc29a14df78c04bd23bb47ead795a8b0cbfa627a82238f5d03aed8ee7bf978"
UNIT = "empire-revenue-crm-pilot.service"
GW_UNIT = "empire-public-gateway.service"
OVERLAY = Path("/etc/systemd/system/empire-revenue-crm-pilot.service.d/zzzzzzzzzzzzzzzz-data-cloud-founder-browser-20261113.conf")
STATE = Path("/var/lib/empire-data-cloud-founder-browser-20261113-v1")
JOURNAL = STATE / "RELEASE.json"
KEY = Path("/etc/empire-data-cloud-founder-20261107/founder-api-key.secret")
ENTRY = "data_cloud_founder_browser_entrypoint_20261113:app"
FILES = {
    "scripts/data_cloud_founder_browser_entrypoint_20261113.py":
        "data_cloud_founder_browser_entrypoint_20261113.py",
    "empire_os/predictive_cloud_customer_api/__init__.py":
        "empire_os/predictive_cloud_customer_api/__init__.py",
    "empire_os/predictive_cloud_customer_api/founder_browser_proxy.py":
        "empire_os/predictive_cloud_customer_api/founder_browser_proxy.py",
    "empire_os/predictive_cloud_customer_api/founder_browser_ui.py":
        "empire_os/predictive_cloud_customer_api/founder_browser_ui.py",
}
HTML_SHA = "17903e07c92278f00033d654b03e6afe2438d656bbd84f28da5c77d76b9a283a"
JS_SHA = "a9d62c2d03715e33e328f7fff55c1155bd3c80c895d3a2913e98c9c41bc0f42e"


def fail(message):
    raise RuntimeError(message)


def call(argv, *, text=True):
    result = subprocess.run(argv, capture_output=True, timeout=30, text=text,
                            env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LC_ALL": "C"})
    if result.returncode:
        fail("original_service_command_failed")
    return result.stdout.strip() if text else result.stdout


def source_git(*args):
    return call(["git", "-c", "safe.directory=" + str(ROOT), "-C", str(ROOT), *args])


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read_source_commit(commit):
    if not isinstance(commit, str) or len(commit) != 40 or any(c not in "0123456789abcdef" for c in commit):
        fail("exact_founder_release_commit_required")
    if source_git("rev-parse", "HEAD") != commit or source_git("status", "--porcelain"):
        fail("original_data_cloud_branch_changed_or_dirty")
    if not BASE_FILE.is_file() or sha(BASE_FILE.read_bytes()) != BASE_SHA:
        fail("current_original_crm_overlay_changed")
    hashes = {}
    for source in FILES:
        path = ROOT / source
        if not path.is_file() or path.is_symlink():
            fail("original_data_cloud_source_missing")
        data = path.read_bytes()
        if data != call(["git", "-c", "safe.directory=" + str(ROOT),
                         "-C", str(ROOT), "show", commit + ":" + source], text=False):
            fail("data_cloud_source_not_committed_as_pinned")
        hashes[source] = sha(data)
    return hashes


def status(url, *, method="GET", body=None):
    request = urllib.request.Request(url, method=method, data=body,
                                     headers={"Content-Type": "application/json"})
    try:
        # Keep release health checks on the original loopback interfaces;
        # never inherit HTTP_PROXY or route a private check off-host.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(request, timeout=4) as response:
            return response.status, response.read(), dict(response.headers)
    except urllib.error.HTTPError as exc:
        return exc.code, b"", {}
    except (TimeoutError, urllib.error.URLError):
        return 0, b"", {}


def live_baseline():
    if call(["systemctl", "is-active", UNIT]) != "active" or call(["systemctl", "is-active", GW_UNIT]) != "active":
        fail("original_public_gateway_or_crm_not_healthy")
    exec_line = call(["systemctl", "show", UNIT, "-p", "ExecStart", "--value"])
    if (
        "empire_crm_multi_pipeline_20261112.entrypoint:app" not in exec_line
        or str(BASE) not in exec_line
        or "--host 127.0.0.1 --port 8783 --no-proxy-headers" not in exec_line
    ):
        fail("original_multi_pipeline_crm_owner_changed")
    dropins = call(["systemctl", "show", UNIT, "-p", "DropInPaths", "--value"])
    if "zzzzzzzzzzzzzz-crm-multi-pipeline-20261112.conf" not in dropins:
        fail("original_multi_pipeline_crm_owner_not_in_unit")
    if str(OVERLAY) in dropins or OVERLAY.exists() or RELEASE.exists() or STATE.exists():
        fail("data_cloud_browser_release_already_present")
    if KEY.is_symlink() or not KEY.is_file():
        fail("existing_data_cloud_api_key_missing")
    key_stat = KEY.stat()
    if key_stat.st_uid != 0 or stat.S_IMODE(key_stat.st_mode) != 0o400 or key_stat.st_nlink != 1:
        fail("existing_sealed_api_key_custody_changed")
    private = "http://127.0.0.1:8783"
    for path in ("/health", "/v1/revenue-crm/journeys/entry", "/v1/revenue-crm/journeys/entry.js"):
        code, _, _ = status(private + path)
        if code != 200:
            fail("original_private_crm_route_unhealthy")
    orig_html = status(private + "/v1/revenue-crm/journeys/entry")[1]
    orig_js = status(private + "/v1/revenue-crm/journeys/entry.js")[1]
    if sha(orig_html) != HTML_SHA or sha(orig_js) != JS_SHA:
        fail("original_crm_browser_ui_changed")
    if status(private + "/v1/data/founder/search", method="POST", body=b'{"query":"python programming language","limit":2}')[0] != 404:
        fail("founder_search_private_route_collision")
    if status("http://127.0.0.1/v1/data/search", method="POST", body=b'{"query":"python programming language","limit":2}')[0] != 401:
        fail("existing_metered_public_search_not_protected")
    return {"exec": exec_line, "dropins": dropins, "html_sha": sha(orig_html),
            "js_sha": sha(orig_js)}


def dropin_contents():
    return (
        "[Service]\n"
        "# Existing CRM issuer, additive Data Cloud browser-to-original-search.\n"
        "LoadCredential=empire-data-cloud-founder-api-key:" + str(KEY) + "\n"
        "Environment=\"PYTHONDONTWRITEBYTECODE=1\"\n"
        "ExecStart=\n"
        "ExecStart=/srv/empire_os/.venv/bin/uvicorn " + ENTRY
        + " --app-dir " + str(RELEASE)
        + " --host 127.0.0.1 --port 8783 --no-proxy-headers\n"
    ).encode()


def receipt(value):
    STATE.mkdir(mode=0o700, exist_ok=True)
    STATE.chmod(0o700)
    tmp = STATE / (".release-" + str(os.getpid()) + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(json.dumps(value, sort_keys=True, separators=(",", ":")).encode())
            out.flush()
            os.fsync(out.fileno())
        os.replace(tmp, JOURNAL)
    finally:
        if tmp.exists():
            tmp.unlink()


def install_files(hashes):
    RELEASE.mkdir(mode=0o755)
    for source, destination in FILES.items():
        final = RELEASE / destination
        final.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        shutil.copyfile(ROOT / source, final, follow_symlinks=False)
        final.chmod(0o444)
        if final.is_symlink() or final.stat().st_uid != 0 or sha(final.read_bytes()) != hashes[source]:
            fail("frozen_data_cloud_browser_source_mismatch")
    fd = os.open(OVERLAY, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    with os.fdopen(fd, "wb") as out:
        out.write(dropin_contents())
        out.flush()
        os.fsync(out.fileno())
    if sha(OVERLAY.read_bytes()) != sha(dropin_contents()):
        fail("new_private_crm_overlay_changed")


def readback():
    for _ in range(18):
        if call(["systemctl", "is-active", UNIT]) == "active" and status("http://127.0.0.1:8783/health")[0] == 200:
            break
        time.sleep(1)
    else:
        fail("private_crm_failed_after_additive_mount")
    current = call(["systemctl", "show", UNIT, "-p", "ExecStart", "--value"])
    if ENTRY not in current or str(RELEASE) not in current:
        fail("founder_data_cloud_browser_entrypoint_not_running")
    page, html, _ = status("http://127.0.0.1:8783/v1/revenue-crm/journeys/entry")
    script, js, _ = status("http://127.0.0.1:8783/v1/revenue-crm/journeys/entry.js")
    if page != 200 or script != 200 or b"data-cloud-search-button" not in html or b'searchOriginalDataCloud' not in js:
        fail("founder_data_cloud_browser_render_not_mounted")
    if status("http://127.0.0.1:8783/v1/data/founder/search", method="POST",
              body=b'{"query":"python programming language","limit":2}')[0] != 401:
        fail("private_founder_browser_search_not_protected")
    if status("http://127.0.0.1:8783/v1/data/auth/exchange", method="POST")[0] != 401:
        fail("original_signed_crm_exchange_changed")
    if status("http://127.0.0.1/v1/data/search", method="POST",
              body=b'{"query":"python programming language","limit":2}')[0] != 401:
        fail("original_public_data_cloud_auth_changed")
    if status("http://127.0.0.1/")[0] != 200 or call(["systemctl", "is-active", GW_UNIT]) != "active":
        fail("original_public_gateway_not_preserved")
    return {"private_browser": page, "private_proxy_unauthenticated": 401,
            "original_exchange_unauthenticated": 401, "public_gateway": 200}


def rollback():
    if OVERLAY.is_file() and not OVERLAY.is_symlink():
        OVERLAY.unlink()
        call(["systemctl", "daemon-reload"])
        call(["systemctl", "restart", UNIT])
    for _ in range(12):
        if status("http://127.0.0.1:8783/health")[0] == 200:
            break
        time.sleep(1)
    if STATE.is_dir():
        receipt({"phase": "rolled_back", "observed_utc": int(time.time())})


def main():
    parser = argparse.ArgumentParser()
    m = parser.add_mutually_exclusive_group(required=True)
    m.add_argument("--preflight", action="store_true")
    m.add_argument("--apply-founder-approved", action="store_true")
    m.add_argument("--rollback", action="store_true")
    parser.add_argument("--source-commit", required=False)
    args = parser.parse_args()
    if os.geteuid() != 0:
        fail("founder_browser_owner_release_requires_privileged_operator")
    if args.rollback:
        rollback()
        print("FOUNDER_BROWSER_RELEASE_ROLLED_BACK")
        return
    hashes = read_source_commit(args.source_commit)
    base = live_baseline()
    if args.preflight:
        print("FOUNDER_BROWSER_RELEASE_PREFLIGHT_PASS")
        print("EXISTING_MULTI_PIPELINE_OWNER_AND_UNMODIFIED_GATEWAY_VERIFIED")
        return
    manifest = {"phase": "staging", "source_commit": args.source_commit,
                "source_sha256": hashes, "old_unit": base, "utc": int(time.time())}
    try:
        receipt(manifest)
        install_files(hashes)
        call(["systemctl", "daemon-reload"])
        call(["systemctl", "restart", UNIT])
        checks = readback()
        manifest["phase"] = "active"
        manifest["live_readback"] = checks
        receipt(manifest)
        print("FOUNDER_BROWSER_SEARCH_LIVE_GUARDED_RELEASE_PASS")
        print(json.dumps(checks, sort_keys=True))
    except Exception:
        rollback()
        fail("founder_browser_release_failed_and_rollback_attempted")


if __name__ == "__main__":
    main()
