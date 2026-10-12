"""One-hit, privacy-safe operational evidence check for public website review.

Never reads journal entries, individual visitor data, credentials or submitted
form bodies. GET only against local gateway; no traffic or publication authority.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

ROOT = Path("/srv/empire_os")
ROUTES = ("/", "/roofing", "/predictive-revenue", "/buy", "/commercial", "/privacy", "/terms")
SOURCE_TOKENS = {
    "localstorage": re.compile(r"\blocalStorage\b"),
    "sessionstorage": re.compile(r"\bsessionStorage\b"),
    "cookie_api": re.compile(r"\bdocument\.cookie\b"),
    "analytics_script": re.compile(r"\b(?:gtag|fbq|dataLayer|clarity)\s*\("),
}
SCHEMA = "empire.public_site_privacy_operational_observation.v1"


def active_journal_retention(config_text: str) -> dict:
    """Only non-commented effective assignments can prove explicit retention."""
    active = {}
    for line in config_text.splitlines():
        line = line.strip()
        if line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key in ("Storage", "MaxRetentionSec", "MaxFileSec", "SystemMaxUse",
                   "RuntimeMaxUse"):
            active[key] = value.strip()
    return {
        "explicit_retention_seconds": active.get("MaxRetentionSec"),
        "explicit_system_max_use": active.get("SystemMaxUse"),
        "explicit_runtime_max_use": active.get("RuntimeMaxUse"),
        "max_file_age_config": active.get("MaxFileSec"),
        "configured_no_retention_limit_unverified": (
            active.get("MaxRetentionSec") in (None, "", "0")
        ),
        "actual_journal_record_lifetime_verified": False,
    }


def static_browser_source_inventory(root: Path) -> dict:
    src = root / "apps/empire-public-site/src"
    result = {"scanned_source_files": 0, "source_signal_file_counts": {
        k: 0 for k in SOURCE_TOKENS
    }, "compiled_js_or_cloudflare_exhaustively_reviewed": False}
    if not src.is_dir() or src.is_symlink():
        result["status"] = "SOURCE_UNAVAILABLE"
        return result
    allowed = {".tsx", ".ts", ".jsx", ".js"}
    for p in src.rglob("*"):
        if (p.suffix not in allowed or p.is_symlink() or not p.is_file()):
            continue
        if p.stat().st_size > 1_000_000:
            result["status"] = "OVERSIZE_SOURCE_NOT_REVIEWED"
            return result
        source = p.read_text(encoding="utf-8")
        result["scanned_source_files"] += 1
        for key, pattern in SOURCE_TOKENS.items():
            result["source_signal_file_counts"][key] += bool(pattern.search(source))
    result["status"] = "SOURCE_PATTERN_REVIEW_ONLY"
    return result


def read_origin(path: str, opener=urlopen) -> dict:
    """No query string, credentials, cookies, POST or visitor record inspection."""
    url = "http://127.0.0.1" + path
    status = None
    headers = None
    try:
        with opener(url, timeout=4) as response:
            status, headers = response.status, response.headers
    except HTTPError as error:
        status, headers = error.code, error.headers
    except (OSError, ValueError):
        return {"route": path, "origin_http_status": None,
                "result": "LOCAL_ORIGIN_NOT_VERIFIED"}
    return {"route": path, "origin_http_status": status,
            "set_cookie_header_observed": bool(headers.get_all("Set-Cookie", [])),
            "no_store_header_observed": "no-store" in
                (headers.get("Cache-Control") or "").lower(),
            "noindex_header_observed": "noindex" in
                (headers.get("X-Robots-Tag") or "").lower(),
            "browser_cookie_absence_globally_proven": False}


def read_command(args: list[str]) -> str | None:
    try:
        p = subprocess.run(args, capture_output=True, text=True,
                           timeout=6, check=False)
        return p.stdout if p.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def observe(root: Path = ROOT, *, origin_probe=read_origin,
            command=read_command) -> dict:
    journal_config = command(["systemd-analyze", "cat-config", "systemd/journald.conf"])
    retention = (active_journal_retention(journal_config)
                 if journal_config is not None else {
                     "status": "CONFIG_UNAVAILABLE",
                     "actual_journal_record_lifetime_verified": False,
                 })
    journal_disk = command(["journalctl", "--disk-usage", "--no-pager"])
    # Do not report raw journal output: it may differ by host or contain text.
    journal_reported = bool(journal_disk and
                            "journal" in journal_disk.lower() and
                            "take up" in journal_disk.lower())
    pages = [origin_probe(p) for p in ROUTES]
    legal_unpublished = {
        r["route"]: r.get("origin_http_status") == 404
        for r in pages if r["route"] in ("/privacy", "/terms")
    }
    return {
        "schema_version": SCHEMA, "mode": "OBSERVE",
        "execution_authority": "NONE", "outbound_sent": False,
        "network_scope": "LOCAL_ORIGIN_GET_ONLY",
        "journal_records_read": False,
        "personal_data_extracted": False,
        "service_configuration_changed": False,
        "site_pages": pages,
        "browser_source": static_browser_source_inventory(root),
        "journal_config": retention,
        "journal_disk_use_metadata_available": journal_reported,
        "legal_routes_unpublished": legal_unpublished,
        "legal_release_verified": False,
        "cloudflare_or_full_browser_storage_audit_complete": False,
        "data_retention_and_subject_request_controls_verified": False,
        "recording_notice_consent_access_retention_verified": False,
        "traffic_authorized": False,
    }


def main() -> None:
    print(json.dumps(observe(), sort_keys=True))


if __name__ == "__main__":
    main()
