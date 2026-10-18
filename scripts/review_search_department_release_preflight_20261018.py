#!/usr/bin/env python3
"""Source-bound, non-mutating release audit for the existing SEO evidence UI.

Checks the EXISTING Search Intelligence loopback service and public website.
Does not deploy, restart, authenticate, publish, send or change CRM/database.
An API source-ready result is not permission to publish a dashboard publicly.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]
SERVICE_UNIT = Path("/etc/systemd/system/empire-search-intelligence-api.service")
FEATURE_COMMIT = "3ef78870"
SCOPED_PATHS = (
    "empire_os/search_intelligence/api.py",
    "empire_os/search_intelligence/department_snapshot.py",
    "apps/search-command-centre/src/lib/search-api.ts",
    "apps/search-command-centre/src/app/department/page.tsx",
    "apps/search-command-centre/src/app/page.tsx",
    "tests/search_intelligence/test_department_snapshot_dashboard_20261018.py",
)
LOCAL = {
    "health": "http://127.0.0.1:8771/health",
    "department": "http://127.0.0.1:8771/v1/search/department/review",
}
PUBLIC = {
    "department_api": "https://empire-ai.co.uk/v1/search/department/review",
    "department_page": "https://empire-ai.co.uk/department",
}
SOURCE_SCHEMA = "empire.search_growth.department_integration.v1"
SCHEMA = "empire.search_growth.private_dashboard_release_preflight.v1"


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def status_get(url: str) -> tuple[int | None, dict]:
    """Fixed allowlisted GET with bounded response; no redirects or cookies."""
    if url not in {*LOCAL.values(), *PUBLIC.values()}:
        return None, {}
    opener = build_opener(NoRedirect())
    request = Request(url, headers={
        "Accept": "application/json",
        # Use a normal browser UA so Cloudflare doesn't return a generic
        # bot/WAF 403 unrelated to the actual site route under review.
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131.0 Safari/537.36",
    }, method="GET")
    try:
        with opener.open(request, timeout=8) as response:
            body = response.read(32769)
            if len(body) > 32768:
                return None, {}
            if url == LOCAL["department"] and response.status == 200:
                try:
                    data = json.loads(body)
                except (ValueError, UnicodeError):
                    data = {}
                return response.status, {
                    "schema": data.get("schema_version"),
                    "mode": data.get("mode"),
                    "status": data.get("status"),
                    "rankings_verified": data.get("search_rankings_verified"),
                    "revenue_verified": data.get("realised_revenue_verified"),
                    "content_type": response.headers.get("Content-Type"),
                    "cache_control": response.headers.get("Cache-Control"),
                }
            if url == LOCAL["health"] and response.status == 200:
                try:
                    data = json.loads(body)
                except (ValueError, UnicodeError):
                    data = {}
                return response.status, {
                    "service": data.get("service"), "mode": data.get("mode"),
                    "execution_allowed": data.get("execution_allowed"),
                }
            return response.status, {}
    except HTTPError as error:
        # Never read error response body; it might include private driver data.
        return error.code, {}
    except (URLError, TimeoutError, OSError, ValueError):
        return None, {}


def source_ready(root: Path = ROOT, unit: Path = SERVICE_UNIT) -> bool:
    if root.is_symlink() or not root.is_dir():
        return False
    try:
        ancestor = subprocess.run(
            ["git", "-C", str(root), "merge-base", "--is-ancestor", FEATURE_COMMIT, "HEAD"],
            capture_output=True, timeout=5, check=False,
        )
        if ancestor.returncode != 0:
            return False
        status = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain", "--", *SCOPED_PATHS],
            capture_output=True, timeout=5, check=False,
        )
        if status.returncode != 0 or status.stdout:
            return False
        if any(not (root / relative).is_file() or (root / relative).is_symlink()
               for relative in SCOPED_PATHS):
            return False
        if unit.is_symlink() or not unit.is_file() or unit.stat().st_size > 8192:
            return False
        service = unit.read_text("utf8")
        required = (
            "User=ubuntu",
            "WorkingDirectory=/srv/empire_os",
            "ExecStart=/srv/empire_os/.venv/bin/python -m uvicorn empire_os.search_intelligence.service:app --host 127.0.0.1 --port 8771 --workers 1",
            "NoNewPrivileges=true",
            "PrivateTmp=true",
        )
        if any(line not in service.splitlines() for line in required):
            return False
        return True
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return False


def assess(*, source: bool, health_code: int | None, health: dict,
           department_code: int | None, department: dict,
           public_api: int | None, public_page: int | None) -> dict:
    """Pure bounded response; private dashboard publication remains held."""
    healthy = (health_code == 200
               and health.get("service") == "search-intelligence-api"
               and health.get("mode") == "OBSERVE"
               and health.get("execution_allowed") is False)
    route_live = (
        department_code == 200
        and department.get("schema") == SOURCE_SCHEMA
        and department.get("mode") == "OBSERVE"
        and department.get("status") == "DEPARTMENT_CONNECTED_EVIDENCE_GAPS_OPEN"
        and department.get("rankings_verified") is False
        and department.get("revenue_verified") is False
        and department.get("cache_control") == "no-store"
    )
    private_public_boundary = public_api == 404 and public_page == 404
    api_source_ready = source and healthy and private_public_boundary
    route_pending_restart = api_source_ready and department_code == 404
    api_enabled = api_source_ready and route_live
    return {
        "schema_version": SCHEMA,
        "mode": "READ_ONLY",
        "status": (
            "API_SOURCE_READY_RESTART_REQUIRES_APPROVAL" if route_pending_restart
            else "PRIVATE_API_ACTIVE_DASHBOARD_DEPLOY_HELD" if api_enabled
            else "HELD_RELEASE_PRECONDITIONS_NOT_VERIFIED"
        ),
        "source_feature_ancestor_and_scoped_tree_clean": source,
        "existing_loopback_api_healthy": healthy,
        "new_department_route_active": api_enabled,
        "existing_loopback_api_restart_required": route_pending_restart,
        "current_route_http_code": department_code,
        "public_site_department_api_http_code": public_api,
        "public_site_department_page_http_code": public_page,
        "public_boundary_verified": private_public_boundary,
        "search_command_centre_production_service_observed": False,
        "dashboard_private_identity_gate_verified": False,
        "dashboard_production_publication_authorized": False,
        "owner_visual_signoff_observed": False,
        "search_rankings_verified": False,
        "revenue_verified": False,
        "systemd_restarted": False,
        "public_site_changed": False,
        "database_writes": False,
        "outbound_sent": False,
        "execution_authority": "NONE",
        "next_action": (
            "REQUEST_EXPLICIT_EXISTING_API_RESTART_APPROVAL"
            if route_pending_restart else
            "CONFIGURE_OWNER_AUTHENTICATION_AND_DEPLOYMENT_REVIEW"
            if api_enabled else
            "RECONCILE_SOURCE_SERVICE_AND_PUBLIC_ACCESS_EVIDENCE"
        ),
    }


def inspect() -> dict:
    health_status, health = status_get(LOCAL["health"])
    route_status, route = status_get(LOCAL["department"])
    public_api, _ = status_get(PUBLIC["department_api"])
    public_page, _ = status_get(PUBLIC["department_page"])
    return assess(
        source=source_ready(), health_code=health_status, health=health,
        department_code=route_status, department=route,
        public_api=public_api, public_page=public_page,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--read-only", required=True, action="store_true")
    parser.parse_args(argv)
    result = inspect()
    print(json.dumps(result, sort_keys=True))
    return 2 if result["status"].startswith("HELD") else 0


if __name__ == "__main__":
    raise SystemExit(main())
