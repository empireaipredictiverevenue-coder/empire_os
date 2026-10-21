"""Additive isolated Research Founder Console staging against live release.

Copies the exact current read-only Founder release source into a private
temporary directory, adds only the Research routes and a single nav link.
Never changes the running Next build, release symlink, service, or ingress.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile

CANDIDATE = Path(__file__).resolve().parents[1] / "apps/search-command-centre"
LIVE_RELEASE = Path(
    "/home/ubuntu/empire_releases/founder_agency_private_console_20261020/releases/"
    "65ab711f28ae4eed9227eea2d8803f273b543ce3"
)
NEXT_DEPENDENCIES = Path("/srv/empire_os/apps/search-command-centre/node_modules")
NAV_ANCHOR = '                  <Drill href="/founder/youtube" title="YouTube Growth & Audience" />\n'
NAV_NEW = '                  <Drill href="/founder/research" title="Empire Research & Agent" />\n'
ROUTES = (
    "src/app/founder/research/page.tsx",
    "src/app/founder/research/research-workbench.tsx",
    "src/app/founder/research/research-intake-review.tsx",
    "src/app/founder/research/execute/route.ts",
    "src/lib/founder-research-internal.ts",
)
BASE_FILES = ("package.json", "package-lock.json", "next.config.ts",
              "tsconfig.json", "eslint.config.mjs", "postcss.config.mjs")


def digest(p: Path) -> str:
    return sha256(p.read_bytes()).hexdigest()


def verify_baseline(live: Path = LIVE_RELEASE, candidate: Path = CANDIDATE) -> dict:
    if (live.is_symlink() or candidate.is_symlink()
            or not live.is_dir() or not candidate.is_dir()
            or not NEXT_DEPENDENCIES.is_dir()):
        raise ValueError("PRIVATE_NEXT_BASELINE_UNTRUSTED")
    if live == LIVE_RELEASE:
        result = subprocess.run(
            ["systemctl", "show", "empire-founder-console",
             "-p", "WorkingDirectory", "-p", "ActiveState"],
            capture_output=True, text=True, timeout=6,
        )
        if (result.returncode or "ActiveState=active" not in result.stdout
                or "WorkingDirectory=" + str(LIVE_RELEASE) not in result.stdout):
            raise ValueError("RUNNING_FOUNDER_CONSOLE_RELEASE_OWNER_CHANGED")
    names = [live / f for f in BASE_FILES]
    names += [candidate / f for f in ROUTES]
    main = live / "src/app/founder/page.tsx"
    if (not main.is_file() or main.is_symlink()
            or any(not p.is_file() or p.is_symlink() for p in names)
            or (live / "src/app/founder/research").exists()
            or (live / "src/lib/founder-research-internal.ts").exists()):
        raise ValueError("EXISTING_PRIVATE_NEXT_RESEARCH_ROUTE_COLLISION")
    data = main.read_text()
    if (data.count(NAV_ANCHOR) != 1 or NAV_NEW in data):
        raise ValueError("CURRENT_FOUNDER_NAV_OWNER_CHANGED")
    return {"baseline_founder_navigation_sha256": digest(main),
            "new_research_route_files": len(ROUTES),
            "released_read_only_pages_preserved": True,
            "live_release_modified": False, "source_worktree_modified": False}


def stage_console(*, live: Path = LIVE_RELEASE,
                  candidate: Path = CANDIDATE,
                  stage_parent: Path | None = None) -> dict:
    status = verify_baseline(live, candidate)
    parent = stage_parent or Path(tempfile.gettempdir())
    if not parent.is_dir() or parent.is_symlink():
        raise ValueError("PRIVATE_NEXT_STAGE_PARENT_INVALID")
    stage = Path(tempfile.mkdtemp(prefix="empire-research-next-stage-", dir=parent))
    stage.chmod(stat.S_IRWXU)
    try:
        for rel in BASE_FILES:
            shutil.copy2(live / rel, stage / rel)
        shutil.copytree(live / "src", stage / "src")
        shutil.copytree(live / "public", stage / "public")
        research_dir = stage / "src/app/founder/research"
        research_dir.mkdir()
        (research_dir / "execute").mkdir()
        for rel in ROUTES:
            shutil.copy2(candidate / rel, stage / rel)
        main = stage / "src/app/founder/page.tsx"
        main.write_text(main.read_text().replace(NAV_ANCHOR,
                                                NAV_ANCHOR + NAV_NEW))
        (stage / "node_modules").symlink_to(NEXT_DEPENDENCIES, target_is_directory=True)
        for rel in ("src/app/founder/mail/page.tsx",
                    "src/app/founder/commercial-pipeline/page.tsx",
                    "src/app/founder/agency/page.tsx",
                    "src/app/founder/intent-review/page.tsx"):
            original, copied = live / rel, stage / rel
            if original.is_file() and (not copied.is_file()
                                       or digest(original) != digest(copied)):
                raise ValueError("UNRELATED_FOUNDER_PAGE_CHANGED")
        return {
            "schema_version": "empire.research.additive_next_staging.v1",
            "status": "ISOLATED_ADDITIVE_NEXT_STAGE_READY_NOT_DEPLOYED",
            "stage_root": str(stage),
            "staged_founder_navigation_sha256": digest(main),
            "node_modules": "REUSED_EXISTING_DEPENDENCY_TREE",
            "live_release_modified": False,
            "cloudflare_session_verified": False,
            "production_root_modified": False,
            "systemd_modified": False, "outbound_sent": False,
            **status,
        }
    except Exception:
        shutil.rmtree(stage)
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--read-only", action="store_true", required=True)
    parser.add_argument("--prepare-isolated-stage", action="store_true")
    opt = parser.parse_args(argv)
    try:
        report = (stage_console() if opt.prepare_isolated_stage
                  else {**verify_baseline(),
                        "status": "ADDITIVE_WEB_PREFLIGHT_PASS_NO_RELEASE_CHANGE"})
        print(json.dumps(report, sort_keys=True))
        return 0
    except (OSError, ValueError):
        print(json.dumps({"status": "HOLD_PRIVATE_NEXT_SOURCE_RECONCILIATION",
                          "live_release_modified": False,
                          "production_root_modified": False}))
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
