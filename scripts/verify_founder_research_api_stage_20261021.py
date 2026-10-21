"""Independent subprocess smoke of unchanged historical API versus staged merge.

The stage is only a local temporary copy; this cannot deploy or assert a
real Cloudflare Access session, ingress reachability or editorial clearance.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import stat
import subprocess
import sys

from scripts.stage_founder_research_api_20261021 import LIVE_API_ROOT

BASE_SCRIPT = """
import json,sys
sys.path.insert(0,sys.argv[1])
from empire_os import founder_dashboard_service as m
from fastapi.testclient import TestClient
with TestClient(m.app) as client:
    out={'loaded_from':m.__file__,
         'routers':[f.__name__ for f in m.READ_ONLY_ROUTER_FACTORIES],
         'health_http':client.get('/health').status_code,
         'research_catalog_http':client.get('/v1/founder-research-products/catalog').status_code}
print(json.dumps(out,sort_keys=True))
"""

STAGED_SCRIPT = """
import json,sys
sys.path.insert(0,sys.argv[1])
from empire_os import founder_dashboard_service as m
from fastapi.testclient import TestClient
with TestClient(m.app) as client:
    out={'loaded_from':m.__file__,
         'routers':[f.__name__ for f in m.READ_ONLY_ROUTER_FACTORIES],
         'health_http':client.get('/health').status_code,
         'research_catalog_http':client.get('/v1/founder-research-products/catalog').status_code,
         'research_get_preview_http':client.get('/v1/founder-research-products/preview').status_code,
         'research_post_preview_http':client.post('/v1/founder-research-products/preview',json={'product':'empire_agent'}).status_code}
print(json.dumps(out,sort_keys=True))
"""


def _invoke(root: Path, *, script: str, cwd: Path) -> dict:
    env = os.environ.copy()
    for key in (
        "EMPIRE_FOUNDER_CF_TEAM_DOMAIN", "EMPIRE_FOUNDER_CF_ACCESS_AUD",
        "EMPIRE_RESEARCH_ALLOWED_FOUNDER_SUB",
    ):
        env.pop(key, None)
    result = subprocess.run(
        [sys.executable, "-B", "-c", script, str(root)],
        cwd=cwd, env=env, capture_output=True, text=True, timeout=30,
    )
    if result.returncode or len(result.stdout) > 200000:
        raise ValueError("FOUNDER_API_STAGING_IMPORT_SMOKE_FAILED")
    return json.loads(result.stdout)


def evaluate(base: dict, staged: dict) -> dict:
    old = base.get("routers") or []
    updated = staged.get("routers") or []
    expected = "create_founder_research_products_router"
    original = [row for row in updated if row != expected]
    correct = (
        isinstance(old, list) and len(old) >= 20
        and updated.count(expected) == 1
        and original == old
        and base.get("health_http") == 200
        and base.get("research_catalog_http") == 404
        and staged.get("health_http") == 200
        and staged.get("research_catalog_http") == 503
        and staged.get("research_get_preview_http") == 405
        and staged.get("research_post_preview_http") == 503
    )
    return {
        "schema_version": "empire.research.additive_api_stage_smoke.v1",
        "status": ("ISOLATED_FOUNDER_API_ROUTE_PARITY_AND_FAIL_CLOSED_PASS"
                   if correct else "HOLD_FOUNDER_API_STAGE_PARITY_OR_IDENTITY"),
        "baseline_router_count": len(old),
        "staged_router_count": len(updated),
        "preserved_baseline_routers": original == old,
        "baseline_health_http": base.get("health_http"),
        "staged_health_http": staged.get("health_http"),
        "staged_catalog_unconfigured_http": staged.get("research_catalog_http"),
        "staged_post_unconfigured_http": staged.get("research_post_preview_http"),
        "staged_get_execution_http": staged.get("research_get_preview_http"),
        "real_founder_session_tested": False,
        "real_cloudflare_access_policy_tested": False,
        "release_authorized": False,
        "production_modified": False,
        "outbound_sent": False, "money_moved": False,
    }


def verify(stage: Path) -> dict:
    parent = Path("/tmp").resolve()
    if (stage.is_symlink() or stage.parent.resolve() != parent
            or not stage.name.startswith("empire-research-api-stage-")
            or not stage.is_dir() or stage.stat().st_mode & 0o077
            or not (stage / "empire_os/founder_dashboard_service.py").is_file()):
        raise ValueError("UNTRUSTED_ISOLATED_STAGE_LOCATION")
    base = _invoke(LIVE_API_ROOT, script=BASE_SCRIPT,
                   cwd=Path("/srv/empire_os"))
    staged = _invoke(stage, script=STAGED_SCRIPT, cwd=stage)
    if (Path(base["loaded_from"]).resolve() !=
            (LIVE_API_ROOT / "empire_os/founder_dashboard_service.py").resolve()
            or Path(staged["loaded_from"]).resolve() !=
            (stage / "empire_os/founder_dashboard_service.py").resolve()):
        raise ValueError("FOUNDER_MODULE_RESOLVED_FROM_WRONG_ROOT")
    return evaluate(base, staged)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--read-only", required=True, action="store_true")
    ap.add_argument("--stage-root", type=Path, required=True)
    args = ap.parse_args(argv)
    try:
        report = verify(args.stage_root)
    except (OSError, ValueError, subprocess.TimeoutExpired, KeyError):
        report = {"status": "HOLD_UNVERIFIED_ISOLATED_FOUNDER_API_STAGE",
                  "production_modified": False, "execution_authority": "none"}
    print(json.dumps(report, sort_keys=True))
    return 0 if report["status"].endswith("_PASS") else 3


if __name__ == "__main__":
    raise SystemExit(main())
