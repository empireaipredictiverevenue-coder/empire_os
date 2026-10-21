"""Prepare one non-live immutable, additive SSH-private Founder Research release.

Uses exact staged historical API and current active Next release. Never edits
running services, service units, Cloudflare ingress, source-owner worktrees,
production checkout, user data, credential storage, or live routes.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import uuid

from scripts.stage_founder_research_api_20261021 import (
    _verify_source as verify_api_source, LIVE_API_ROOT, RESEARCH_ROOT
)
from scripts.stage_founder_research_console_20261021 import (
    verify_baseline as verify_console_source, LIVE_RELEASE
)
from scripts.test_founder_research_staged_session_e2e_20261021 import _verify_stage

OUTPUT_BASE = Path("/home/ubuntu/empire_releases/founder_research_ssh_private_20261021")
API_CHECK = (
    "empire_os/founder_dashboard_service.py",
    "empire_os/founder_research_auth.py",
    "empire_os/founder_research_products_api.py",
    "empire_os/research/research_products.py",
    "scripts/run_brokerage_deep_research_20261021.py",
)
NEXT_CHECK = (
    "src/app/founder/page.tsx",
    "src/app/founder/research/page.tsx",
    "src/app/founder/research/execute/route.ts",
    "src/lib/founder-research-internal.ts",
    ".next/BUILD_ID",
)


def digest(p: Path) -> str:
    return sha256(p.read_bytes()).hexdigest()


def _source_commit(repo: Path) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        capture_output=True, text=True, timeout=8, check=True,
    )
    return proc.stdout.strip()


def verify_release(
    api_stage: Path, web_stage: Path,
    *, repo: Path = RESEARCH_ROOT,
) -> dict:
    _verify_stage(api_stage, "empire-research-api-stage-",
                  "empire_os/founder_dashboard_service.py")
    _verify_stage(web_stage, "empire-research-next-stage-", ".next/BUILD_ID")
    if repo == RESEARCH_ROOT:
        verify_api_source(LIVE_API_ROOT, repo)
        verify_console_source(LIVE_RELEASE, repo / "apps/search-command-centre")
    for rel in API_CHECK:
        if not (api_stage / rel).is_file():
            raise ValueError("MISSING_STAGED_API_MODULE")
    for rel in NEXT_CHECK:
        if not (web_stage / rel).is_file():
            raise ValueError("MISSING_STAGED_NEXT_MODULE")
    same = {
        "api/founder_research_auth.py": (
            api_stage / "empire_os/founder_research_auth.py",
            repo / "empire_os/founder_research_auth.py",
        ),
        "api/founder_research_products_api.py": (
            api_stage / "empire_os/founder_research_products_api.py",
            repo / "empire_os/founder_research_products_api.py",
        ),
        "web/founder-research-internal.ts": (
            web_stage / "src/lib/founder-research-internal.ts",
            repo / "apps/search-command-centre/src/lib/founder-research-internal.ts",
        ),
        "web/research/page.tsx": (
            web_stage / "src/app/founder/research/page.tsx",
            repo / "apps/search-command-centre/src/app/founder/research/page.tsx",
        ),
        "web/research/execute/route.ts": (
            web_stage / "src/app/founder/research/execute/route.ts",
            repo / "apps/search-command-centre/src/app/founder/research/execute/route.ts",
        ),
    }
    for left, right in same.values():
        if not right.is_file() or digest(left) != digest(right):
            raise ValueError("STAGED_AUTH_OR_BROWSER_SOURCE_DRIFT")
    original_api = LIVE_API_ROOT / "empire_os/founder_dashboard_service.py"
    original_nav = LIVE_RELEASE / "src/app/founder/page.tsx"
    return {
        "source_commit": _source_commit(repo),
        "baseline_original_api_service_sha256": digest(original_api),
        "baseline_original_web_navigation_sha256": digest(original_nav),
        "api_source_checksums": {rel: digest(api_stage / rel) for rel in API_CHECK},
        "web_source_checksums": {rel: digest(web_stage / rel) for rel in NEXT_CHECK},
        "web_stage_build_present": True,
        "staging_inputs_current": True,
        "live_services_modified": False,
    }


RELEASE_NOTES = """# Empire Research and Empire Agent — SSH-private release candidate

Status: PREPARED; NOT DEPLOYED. All current customer-send, database writes,
editorial signoff, financial and live outbound approvals remain OFF.

The existing Founder Console is reached via **SSH port forwarding**, not through
a Cloudflare Access Founder application. The public Cloudflare tunnel has no
ingress rule for 127.0.0.1:3001. Only a verified server operator can switch the
active services following a separate, exact release approval.

Scoped candidate:
- api/ is the *currently running historical Founder API* plus additive Research
  modules, preserving all existing readers.
- web/ is the *currently running Founder Next release* plus the private Research
  page, execution route and one navigation link. Existing agency, pipeline,
  mailbox, SEO, Analytics, and other routes remain in the bundle.
- No new public origin, browser token or database service.

Protected operator environment to provision independently and never commit:
EMPIRE_FOUNDER_RESEARCH_AUTH_MODE=ssh_loopback
EMPIRE_RESEARCH_SSH_PRIVATE_ENABLED=1
EMPIRE_PRIVATE_FOUNDER_INGRESS_REVIEWED=1
EMPIRE_RESEARCH_SSH_BRIDGE_SECRET=<independently-generated-64+-char-base64url-secret>

Both systemd services need this protected env file. Do not create a secret via
an untrusted web request. Do not use the synthetic staging E2E credentials.

On explicit approved activation, deploy from the immutable api/ and web/
directories through dedicated additive systemd drop-ins:
- API: preserve 127.0.0.1:8766 and all existing reader service settings;
  only change the uvicorn --app-dir to this candidate's api/ path.
- Console: preserve 127.0.0.1:3001 and Node/Next ExecStart;
  only change WorkingDirectory to this candidate's web/ path.
- Both services: add the protected env file without printing secret values.

Preflight / verify: original services active, ingress isolated, current legacy
root checksums still identical to release-manifest.json, identity secret
length/permissions valid, 170+ regression tests, 14/14 local SSH E2E and
17/17 default JWT E2E. Stop if any gate fails or another owner has advanced
the active API or Next release.

Before cutover, retain exact current systemd unit/drop-in references for both
services and release paths as rollback anchors. After cutover:
- unauthorised direct API catalog request -> 401
- /founder/research over SSH-forwarded localhost:3001 -> private workbench
- /founder/research/execute accepts only local same-origin POST
- existing /founder and /founder/intent-review still -> HTTP 200
- https://empire-ai.co.uk/founder/research still -> HTTP 404
- production API and Next listen on loopback only

If any check fails, restore original API app-dir, Console WorkingDirectory and
environment overrides, daemon-reload and restart exactly these two services;
do not revert unrelated Git changes or overwrite any other drop-in.

Private SSH access from an operator-controlled computer:
  ssh -L 3001:127.0.0.1:3001 ubuntu@62.210.95.205
Then open http://127.0.0.1:3001/founder/research in the local browser.
This command is illustrative; existing SSH authorisation still applies.

This is an exact read-only implementation handoff, not an authorisation to
change binding security policies, invite additional users, send outbound,
write canonical EmpireDB, or move money.
"""


def prepare(
    api_stage: Path,
    web_stage: Path,
    *, output_base: Path = OUTPUT_BASE,
) -> dict:
    receipt = verify_release(api_stage, web_stage)
    current_changes = subprocess.run(
        ["git", "-C", str(RESEARCH_ROOT), "status", "--porcelain"],
        capture_output=True, text=True, check=True, timeout=12,
    ).stdout.strip()
    if current_changes:
        raise ValueError("RESEARCH_RELEASE_REQUIRES_CLEAN_COMMITTED_WORKTREE")
    if output_base.is_symlink():
        raise ValueError("RELEASE_OUTPUT_PATH_SYMLINK_FORBIDDEN")
    output_base.mkdir(mode=0o700, parents=True, exist_ok=True)
    output_base.chmod(0o700)
    name = "candidate-" + receipt["source_commit"][:12]
    destination = output_base / name
    if destination.exists():
        raise ValueError("EXISTING_RELEASE_CANDIDATE_DO_NOT_OVERWRITE")
    draft = output_base / (".building-" + uuid.uuid4().hex)
    draft.mkdir(mode=0o700)
    try:
        shutil.copytree(api_stage, draft / "api", symlinks=True)
        shutil.copytree(web_stage, draft / "web", symlinks=True)
        manifest = {
            "schema_version": "empire.research.ssh_private_release_candidate.v1",
            "status": "IMMUTABLE_SSH_PRIVATE_RELEASE_PREPARED_NOT_ACTIVATED",
            "release_name": name,
            "historical_api_original_path": str(LIVE_API_ROOT),
            "existing_next_original_path": str(LIVE_RELEASE),
            "private_api_port": 8766,
            "private_console_port": 3001,
            "auth_mode": "SSH_AUTHENTICATED_LOOPBACK_PLUS_PRIVATE_SERVER_BRIDGE",
            "cloudflare_access_claimed_verified": False,
            "real_ssh_operator_forward_test_completed": False,
            "production_modified": False,
            "systemd_modified": False,
            "secret_generated_or_persisted": False,
            "customer_messages_sent": False,
            "database_writes": False,
            "money_moved": False,
            **receipt,
        }
        (draft / "release-manifest.json").write_text(
            json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf8",
        )
        (draft / "RELEASE_README.md").write_text(RELEASE_NOTES, encoding="utf8")
        draft.rename(destination)
    except Exception:
        shutil.rmtree(draft, ignore_errors=True)
        raise
    return {
        "status": manifest["status"],
        "release_path": str(destination),
        "source_commit": manifest["source_commit"],
        "api_expected_hash": manifest["baseline_original_api_service_sha256"],
        "web_expected_hash": manifest["baseline_original_web_navigation_sha256"],
        "production_modified": False,
        "systemd_modified": False,
        "secret_persisted": False,
        "rollback_documented": True,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--read-only", required=True, action="store_true")
    parser.add_argument("--api-stage-root", type=Path, required=True)
    parser.add_argument("--web-stage-root", type=Path, required=True)
    parser.add_argument("--prepare-additive-release", action="store_true")
    args = parser.parse_args(argv)
    try:
        receipt = (prepare(args.api_stage_root, args.web_stage_root)
                   if args.prepare_additive_release
                   else {
                       **verify_release(args.api_stage_root, args.web_stage_root),
                       "status": "RELEASE_PREFLIGHT_PASS_NO_RELEASE_WRITTEN",
                   })
        print(json.dumps(receipt, sort_keys=True))
        return 0
    except (OSError, ValueError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        print(json.dumps({
            "status": "HOLD_SSH_PRIVATE_RELEASE_SOURCE_OR_AUTHORITY",
            "production_modified": False, "systemd_modified": False,
        }))
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
