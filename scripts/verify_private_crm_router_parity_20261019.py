#!/usr/bin/env python3
"""Verify exact private CRM *Python router* parity without public OpenAPI.

The authenticated CRM pilot intentionally uses FastAPI(openapi_url=None,
docs_url=None, redoc_url=None). This read-only script imports the immutable
active-release router and the isolated candidate in separate clean Python
processes. It never loads live CRM credentials, runs SQL or opens a socket.
"""
from __future__ import annotations

import argparse
import inspect
import json
import os
import subprocess
import sys
from pathlib import Path

BASE = Path("/opt/empire-ai/crm-pilot-releases/founder-queue-20261018v1")
STAGED = Path("/home/ubuntu/empire_worktrees/empire_crm_solar_tenant_name_preview_20261019")
DEPLOYED = Path("/opt/empire-ai/crm-pilot-releases/founder-queue-solar-name-20261019v1")
NEW_PATH = "/v1/revenue-crm/workspace-solar/prospect-name-matches/preview"
EXPECTED_PRIOR_COUNT = 27
EXPECTED_NEW_COUNT = 28


class RouteManifestHeld(ValueError):
    pass


def emit_manifest() -> list[dict]:
    """Only creates API route objects: does not start authenticated service."""
    from fastapi.routing import APIRoute
    from empire_os.revenue_crm_api import create_revenue_crm_router

    result = []
    for route in create_revenue_crm_router().routes:
        if not isinstance(route, APIRoute):
            raise RouteManifestHeld("UNEXPECTED_ROUTER_OBJECT")
        result.append({
            "path": route.path,
            "methods": sorted(route.methods or []),
            "name": route.name,
            "endpoint_qualname": route.endpoint.__qualname__,
            "endpoint_signature": str(inspect.signature(route.endpoint)),
            "status_code": route.status_code,
            "include_in_schema": route.include_in_schema,
            "response_class": getattr(route.response_class, "__name__", None),
            "dependencies": [
                getattr(dep.call, "__qualname__", type(dep.call).__name__)
                for dep in route.dependencies
            ],
        })
    return sorted(result, key=lambda x: x["path"])


def _root_manifest(root: Path) -> list[dict]:
    if root not in (BASE, STAGED, DEPLOYED):
        raise RouteManifestHeld("UNEXPECTED_RELEASE_ROOT")
    if not root.is_dir() or root.is_symlink():
        raise RouteManifestHeld("RELEASE_ROOT_UNAVAILABLE")
    env = {"PATH": "/usr/bin:/bin", "PYTHONPATH": str(root),
           "PYTHONDONTWRITEBYTECODE": "1"}
    try:
        result = subprocess.run(
            [sys.executable, "-B", str(Path(__file__).resolve()), "--emit"],
            cwd="/tmp", env=env, capture_output=True, text=True,
            timeout=15, check=True,
        )
        manifest = json.loads(result.stdout)
    except (OSError, ValueError, subprocess.SubprocessError):
        raise RouteManifestHeld("EXACT_RELEASE_ROUTER_IMPORT_FAILED") from None
    if not isinstance(manifest, list) or any(
        not isinstance(row, dict) or not isinstance(row.get("path"), str)
        or not isinstance(row.get("methods"), list) for row in manifest
    ):
        raise RouteManifestHeld("INVALID_IMPORTED_ROUTE_MANIFEST")
    return manifest


def compare(before: list[dict], after: list[dict]) -> dict:
    if len(before) != EXPECTED_PRIOR_COUNT or len(after) != EXPECTED_NEW_COUNT:
        raise RouteManifestHeld("UNEXPECTED_ROUTE_COUNTS")
    previous = {r["path"]: r for r in before}
    current = {r["path"]: r for r in after}
    if len(previous) != len(before) or len(current) != len(after):
        raise RouteManifestHeld("DUPLICATE_ROUTER_PATH")
    if set(current) != set(previous) | {NEW_PATH} or NEW_PATH in previous:
        raise RouteManifestHeld("EXISTING_ROUTER_PATH_CHANGED")
    if any(current[path] != old for path, old in previous.items()):
        raise RouteManifestHeld("EXISTING_ROUTER_CONTRACT_CHANGED")
    new = current[NEW_PATH]
    if (new.get("methods") != ["GET"]
            or new.get("name") != "workspace_solar_tenant_prospect_name_preview"
            or new.get("include_in_schema") is not True
            or new.get("status_code") not in (None, 200)):
        raise RouteManifestHeld("UNEXPECTED_NEW_ROUTE_CONTRACT")
    for path in (
        "/v1/revenue-crm/health",
        "/v1/revenue-crm/prospects",
        "/v1/revenue-crm/journeys/acquisition-scorecard",
        "/v1/revenue-crm/partner-conversations/review",
        "/v1/revenue-crm/commercial-loop/review",
    ):
        if path not in previous:
            raise RouteManifestHeld("REQUIRED_FOUNDER_CRM_ROUTE_ABSENT")
    return {
        "status": "CRM_PRIOR_ROUTER_CONTRACTS_PRESERVED_ONE_GET_ADDED",
        "prior_routes_verified": len(before),
        "new_routes_verified": len(after),
        "added_route": NEW_PATH,
        "openapi_endpoint_required": False,
        "read_only": True,
        "crm_mutation": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--emit", action="store_true")
    modes.add_argument("--compare-staged", action="store_true")
    modes.add_argument("--compare-deployed", action="store_true")
    args = parser.parse_args()
    try:
        if args.emit:
            print(json.dumps(emit_manifest(), sort_keys=True))
        else:
            candidate = STAGED if args.compare_staged else DEPLOYED
            print(json.dumps(compare(
                _root_manifest(BASE), _root_manifest(candidate)
            ), sort_keys=True))
    except RouteManifestHeld as exc:
        print(json.dumps({"status": "CRM_ROUTE_PARITY_HELD",
                          "reason_code": str(exc)}))
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
