"""Stage exact live Founder API + additive Research modules; NEVER deploy.

Rebases the Research router onto the running historical Founder API files in
a private temporary staging directory. No writes to /srv/empire_os, the
source owner worktree, deployed Next release, systemd or EmpireDB.
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

RESEARCH_ROOT = Path(__file__).resolve().parents[1]
LIVE_API_ROOT = Path(
    "/home/ubuntu/empire_worktrees/empire_founder_api_hist052_bridge_additive_20261018"
)
BASELINE_SCRIPTS = Path("/srv/empire_os/scripts")
MODULES = (
    "empire_os/founder_research_auth.py",
    "empire_os/founder_research_products_api.py",
    "scripts/run_brokerage_deep_research_20261021.py",
)
IMPORT_ANCHOR = "from empire_os.founder_vertical_intelligence_api import create_founder_vertical_intelligence_router\n"
ROUTER_ANCHOR = "    create_founder_vertical_intelligence_router,\n"
NEW_IMPORT = "from empire_os.founder_research_products_api import create_founder_research_products_router\n"
NEW_ROUTER = "    create_founder_research_products_router,\n"


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _verify_source(live_root: Path, research_root: Path) -> dict:
    api = live_root / "empire_os"
    candidate = research_root / "empire_os"
    required = [api / "founder_dashboard_service.py", api / "__init__.py"]
    required += [research_root / p for p in MODULES]
    required += list((candidate / "research").glob("*.py"))
    if (live_root.is_symlink() or research_root.is_symlink()
            or not BASELINE_SCRIPTS.is_dir() or BASELINE_SCRIPTS.is_symlink()
            or not api.is_dir() or api.is_symlink()
            or not candidate.is_dir() or not (candidate / "research").is_dir()
            or any(not p.is_file() or p.is_symlink() for p in required)):
        raise ValueError("STAGING_SOURCE_CUSTODY_MISSING_OR_SYMLINK")
    if live_root == LIVE_API_ROOT:
        result = subprocess.run(
            ["systemctl", "show", "empire-founder-dashboard-api",
             "-p", "ExecStart", "-p", "ActiveState"],
            capture_output=True, text=True, timeout=6,
        )
        if (result.returncode or "ActiveState=active" not in result.stdout
                or "--app-dir " + str(LIVE_API_ROOT) not in result.stdout
                or "--host 127.0.0.1 --port 8766" not in result.stdout):
            raise ValueError("RUNNING_FOUNDER_API_SOURCE_OWNER_CHANGED")
    service_file = api / "founder_dashboard_service.py"
    source = service_file.read_text(encoding="utf8")
    if (source.count(IMPORT_ANCHOR) != 1 or source.count(ROUTER_ANCHOR) != 1
            or NEW_IMPORT in source or NEW_ROUTER in source
            or "docs_url=None" not in source or "openapi_url=None" not in source):
        raise ValueError("HISTORICAL_API_ROUTER_BASELINE_CHANGED")
    research_paths = sorted((candidate / "research").glob("*.py"))
    if len(research_paths) < 9:
        raise ValueError("RESEARCH_PACKAGE_INCOMPLETE")
    for relative in MODULES[:2]:
        if (api / Path(relative).name).exists():
            raise ValueError("EXISTING_LIVE_RESEARCH_ROUTER_MUST_NOT_OVERWRITE")
    if (api / "research").exists() or (live_root / "scripts").exists():
        raise ValueError("LIVE_API_PACKAGE_CONFLICT")
    return {
        "live_service_sha256": _sha(service_file),
        "source_file_count": len(required),
        "research_package_files": len(research_paths),
        "additional_module_count": len(MODULES) + len(research_paths),
        "affected_original_router_files": 1,
        "production_modified": False,
    }


def _no_bytecode(directory, children):
    return {name for name in children if (
        name == "__pycache__" or name.endswith((".pyc", ".pyo"))
    )}


def stage_additive_api(
    *, live_root: Path = LIVE_API_ROOT,
    research_root: Path = RESEARCH_ROOT,
    stage_parent: Path | None = None,
) -> dict:
    check = _verify_source(live_root, research_root)
    parent = stage_parent or Path(tempfile.gettempdir())
    if not parent.is_dir() or parent.is_symlink():
        raise ValueError("PRIVATE_STAGE_PARENT_NOT_ALLOWED")
    stage = Path(tempfile.mkdtemp(prefix="empire-research-api-stage-", dir=parent))
    stage.chmod(stat.S_IRWXU)
    try:
        shutil.copytree(live_root / "empire_os", stage / "empire_os",
                        ignore=_no_bytecode)
        package = stage / "empire_os"
        for rel in MODULES[:2]:
            src = research_root / rel
            shutil.copy2(src, package / src.name)
        shutil.copytree(research_root / "empire_os/research",
                        package / "research", ignore=_no_bytecode)
        scripts = stage / "scripts"
        shutil.copytree(BASELINE_SCRIPTS, scripts, ignore=_no_bytecode)
        (scripts / "__init__.py").write_text("", encoding="utf8")
        if (scripts / "run_brokerage_deep_research_20261021.py").exists():
            raise ValueError("BASELINE_RESEARCH_SCRIPT_COLLISION")
        shutil.copy2(research_root / MODULES[2],
                     scripts / "run_brokerage_deep_research_20261021.py")
        service = package / "founder_dashboard_service.py"
        content = service.read_text(encoding="utf8")
        content = content.replace(IMPORT_ANCHOR, NEW_IMPORT + IMPORT_ANCHOR)
        content = content.replace(ROUTER_ANCHOR, NEW_ROUTER + ROUTER_ANCHOR)
        service.write_text(content, encoding="utf8")
        unchanged = (live_root / "empire_os/first_revenue_api.py")
        if unchanged.is_file() and (
            _sha(unchanged) != _sha(package / "first_revenue_api.py")
        ):
            raise ValueError("UNRELATED_FOUNDER_MODULE_MUTATED")
        receipt = {
            "schema_version": "empire.research.additive_founder_api_stage.v1",
            "status": "ISOLATED_ADDITIVE_API_STAGE_CREATED_NOT_DEPLOYED",
            "stage_root": str(stage),
            "original_api_service_sha256": check["live_service_sha256"],
            "staged_api_service_sha256": _sha(service),
            "scoped_module_sha256": {
                p.relative_to(stage).as_posix(): _sha(p)
                for p in sorted([service, *[package / Path(r).name for r in MODULES[:2]],
                                 *sorted((package / "research").glob("*.py")),
                                 scripts / "run_brokerage_deep_research_20261021.py"])
            },
            "existing_api_source_preserved": True,
            "existing_api_root_modified": False,
            "production_root_modified": False,
            "systemd_modified": False,
            "next_release_modified": False,
            "cloudflare_access_verified": False,
            "founder_session_verified": False,
            "commercial_authority": "none",
            **check,
        }
        return receipt
    except Exception:
        shutil.rmtree(stage)
        raise


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--read-only", action="store_true", required=True)
    parser.add_argument("--prepare-isolated-stage", action="store_true")
    options = parser.parse_args(argv)
    try:
        report = (_verify_source(LIVE_API_ROOT, RESEARCH_ROOT)
                  if not options.prepare_isolated_stage else stage_additive_api())
        if not options.prepare_isolated_stage:
            report = {
                **report, "status": "ADDITIVE_STAGING_PREFLIGHT_PASSED_NO_STAGE_WRITTEN",
                "execution_authority": "none",
            }
        print(json.dumps(report, sort_keys=True))
        return 0
    except (OSError, ValueError):
        print(json.dumps({"status": "HOLD_ADDITIVE_API_STAGING_SOURCE_CUSTODY",
                          "original_service_modified": False,
                          "production_root_modified": False, "execution_authority": "none"}))
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
