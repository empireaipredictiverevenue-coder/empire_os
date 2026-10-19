#!/usr/bin/env python3
"""Read-only exact frozen Founder Console GSC chart release preflight.

Never restarts a service or modifies source, systemd, public website,
payment, CRM, Gmail, search provider or database.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPRedirectHandler

PRIOR = Path("/opt/empire-ai/founder-console-releases/commercial-ops-v2-49aba1fa")
TARGET = Path("/home/ubuntu/empire_worktrees/empire_founder_gsc_trends_commercial_v2_candidate_20261019")
SOURCE = Path("/srv/empire_os/apps/search-command-centre")
EXPECTED = {
    ".next/BUILD_ID": "1a5c6a9fbfd367e54724ef9291f23ae96a2cb0815aaac19b258420f6f398c973",
    ".next/server/app/department/page.js": "fa23d15eab141df0fdf312f8893ebac4f79df256cb868d7ab33152c652d5f952",
    ".next/server/app/founder/commercial-pipeline/page.js": "3a163a2add9dc960c47e14aa8b0b8322c16dea93ca2b93d48996e22009865abb",
    ".next/server/app/founder/mail/page.js": "2ac7ee38135a8bf8d5a6eac9e18d85ac5d3ba03b4367c6aee187576eba201f32",
    ".next/server/app/page.js": "d7364a015e993294aeea4a5c3fddc4077f3c917b3b48f25eb9fd36bd06ee880c",
}
ROUTES = (
    "/", "/founder", "/founder/mail", "/founder/results",
    "/founder/solar", "/founder/youtube", "/founder/intent-review",
    "/founder/commercial-pipeline", "/revenue", "/department",
)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def _get(url: str) -> tuple[int | None, dict]:
    if url not in {
        "http://127.0.0.1:8771/v1/search/department/review",
        *(f"http://127.0.0.1:3001{p}" for p in ROUTES),
        "https://empire-ai.co.uk/department",
        "https://empire-ai.co.uk/v1/search/department/review",
    }:
        return None, {}
    req = Request(url, method="GET", headers={
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131.0 Safari/537.36",
    })
    try:
        with build_opener(NoRedirect()).open(req, timeout=9) as response:
            if url.endswith("/v1/search/department/review") and url.startswith("http:"):
                data = response.read(65537)
                if len(data)>65536:return None,{}
                try:return response.status,json.loads(data)
                except ValueError:return response.status,{}
            return response.status,{}
    except HTTPError as ex:
        return ex.code,{}
    except (OSError, TimeoutError, URLError):
        return None,{}


def _files(root: Path) -> dict[str, Path]:
    base = root/"src"
    if root.is_symlink() or not base.is_dir():
        raise ValueError("release_source_unavailable")
    entries = {p.relative_to(base).as_posix():p for p in base.rglob("*") if p.is_file()}
    if len(entries)>120 or any(p.is_symlink() or p.stat().st_size>700000 for p in entries.values()):
        raise ValueError("release_source_bound_invalid")
    return entries


def source_frozen() -> bool:
    try:
        before=_files(PRIOR);after=_files(TARGET)
        if set(after)-set(before)!={"app/department/observed-trend.tsx"} or set(before)-set(after):
            return False
        delta={k for k in before if before[k].read_bytes()!=after[k].read_bytes()}
        if delta!={"app/department/page.tsx","lib/search-api.ts"}:
            return False
        for k in delta | {"app/department/observed-trend.tsx"}:
            if after[k].read_bytes() != (SOURCE/"src"/k).read_bytes():
                return False
        if not (TARGET/"node_modules").is_symlink():
            return False
        if (TARGET/"node_modules").readlink() != SOURCE/"node_modules":
            return False
        for path,digest in EXPECTED.items():
            artifact=TARGET/path
            if artifact.is_symlink() or not artifact.is_file() or artifact.stat().st_size>15_000_000:
                return False
            if hashlib.sha256(artifact.read_bytes()).hexdigest()!=digest:
                return False
        return True
    except (ValueError,OSError):
        return False


def current_service_is_prior() -> bool:
    try:
        proc=subprocess.run(
            ["systemctl","show","empire-founder-console.service",
             "-p","WorkingDirectory","-p","ActiveState","-p","DropInPaths",
             "--no-pager"],capture_output=True,text=True,timeout=5)
        if proc.returncode!=0:return False
        items=dict(line.split("=",1) for line in proc.stdout.splitlines() if "=" in line)
        dropins=items.get("DropInPaths","").split()
        return (items.get("ActiveState")=="active"
                and items.get("WorkingDirectory")==str(PRIOR)
                and len(dropins)==6
                and dropins[-1].endswith("/97-commercial-operations-v2.conf")
                and all("/98-private-gsc-trend-release.conf" not in f for f in dropins))
    except (OSError,subprocess.TimeoutExpired):
        return False


def assess(*, source_ok: bool, service_ok: bool,
           old_routes_ok: bool, public_closed: bool,
           backend: dict) -> dict:
    backend=backend if isinstance(backend,dict) else {}
    daily=backend.get("gsc_daily_chart")
    base_ok=(backend.get("schema_version")=="empire.search_growth.department_integration.v1"
             and backend.get("status")=="DEPARTMENT_CONNECTED_EVIDENCE_GAPS_OPEN"
             and backend.get("search_rankings_verified") is False
             and backend.get("realised_revenue_verified") is False)
    chart_ok=(isinstance(daily,dict)
              and daily.get("status")=="DATE_DIMENSION_ROWS_OBSERVED"
              and daily.get("source")=="google_search_console_date_dimension"
              and daily.get("missing_days_treated_as_zero") is False
              and daily.get("independent_google_rank_positions_verified") is False
              and daily.get("realised_revenue_verified") is False
              and isinstance(daily.get("rows"),list)
              and len(daily["rows"])>1)
    safe=source_ok and service_ok and old_routes_ok and public_closed and base_ok
    return {
        "status": ("FROZEN_CANDIDATE_BACKEND_READY_REQUIRES_FOUNDER_RELEASE_APPROVAL"
                   if safe and chart_ok else
                   "FROZEN_CANDIDATE_GSC_BACKEND_ACTIVATION_PENDING"
                   if safe else "HELD_SOURCE_OWNER_OR_PUBLIC_BOUNDARY"),
        "mode":"READ_ONLY",
        "exact_new_build_verified":source_ok,
        "active_prior_console_unchanged":service_ok,
        "ten_current_private_routes_healthy":old_routes_ok,
        "public_website_seo_routes_404":public_closed,
        "daily_api_source_attested":bool(base_ok and chart_ok),
        "seo_rankings_verified":False,
        "realised_revenue_verified":False,
        "no_service_restarted":True,
        "production_changed":False,
        "execution_authority":"NONE",
    }


def inspect() -> dict:
    route_codes = [_get("http://127.0.0.1:3001"+p)[0] for p in ROUTES]
    private_code,backend=_get("http://127.0.0.1:8771/v1/search/department/review")
    public=[_get("https://empire-ai.co.uk"+p)[0]
            for p in ("/department","/v1/search/department/review")]
    return assess(source_ok=source_frozen(),service_ok=current_service_is_prior(),
                  old_routes_ok=all(n==200 for n in route_codes),
                  public_closed=public==[404,404],
                  backend=backend if private_code==200 else {})


def main(argv=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--read-only",action="store_true",required=True)
    parser.parse_args(argv)
    result=inspect()
    print(json.dumps(result,sort_keys=True))
    return 2 if result["status"].startswith("HELD") else 0


if __name__=="__main__":
    raise SystemExit(main())
