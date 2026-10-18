"""Non-mutating, byte-exact audit of a deployed organic-sector release.

This is not a revenue meter. Browser observations and unknown buyer outcomes
are NEVER reported as paid conversions. It cannot write files, activate a
campaign, query customer records or grant EmpireDB privileges.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

PAGES = frozenset({
    "commercial.html", "commercial.txt",
    "industries/solar.html", "industries/solar.txt",
    "industries/roofing.html", "industries/roofing.txt",
})
CODE = frozenset({
    "empire_os/first_party_sales_interest.py",
    "empire_os/self_serve_checkout_api.py",
    "empire_os/owned_campaign_http.py",
    "empire_os/owned_campaign_industry_extension.py",
    "empire_os/organic_campaign_touch.py",
    "empire_os/public_gateway.py",
})


def _sha_file(path: Path) -> str:
    h = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _safe_json(path: Path, max_bytes: int = 200_000) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > max_bytes:
        raise ValueError("missing, symlinked, or oversized release evidence")
    value = json.loads(path.read_text("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("invalid release evidence")
    return value


def _inventory(folder: Path) -> dict[str, str]:
    if folder.is_symlink() or not folder.is_dir():
        raise ValueError("release directory missing or symlinked")
    result = {}
    for item in folder.rglob("*"):
        if item.is_symlink():
            raise ValueError("symlinked release asset")
        if item.is_file():
            result[item.relative_to(folder).as_posix()] = _sha_file(item)
    return result


def audit_live_release(
    *, repository: Path, backup: Path, staged_manifest: Path,
    site: Path, rollback_site: Path, released_source: Path,
) -> dict[str, Any]:
    """Compare all site/code bytes, metadata and original-owner custody.

    Return HOLD on a discrepant resource, never pretend counts are 0.
    """
    problems: list[str] = []
    def hold(message: str) -> None:
        if message not in problems:
            problems.append(message)

    try:
        rollback = _safe_json(backup / "rollback_manifest.json")
        receipt = _safe_json(backup / "deployment_receipt.json")
        staged = _safe_json(staged_manifest, 350_000)
        if receipt.get("status") != "DEPLOYED_SMOKE_PASS":
            hold("deployment_receipt_not_verified")
        for flag in ("payment_action", "outbound", "buyer_records_written",
                     "event_release_registered"):
            if receipt.get(flag) is not False:
                hold("unsafe_or_unknown_release_authority_" + flag)
        if staged.get("status") != "PREPARED_NOT_DEPLOYED":
            hold("invalid_static_preparation_provenance")
        if staged.get("production_writes") is not False:
            hold("static_preparation_changed_production")
        expected_pages = staged.get("replaced_existing_pages")
        originals = staged.get("source_live_sha256")
        if (not isinstance(expected_pages, dict) or set(expected_pages) != PAGES
                or not isinstance(originals, dict) or set(originals) != PAGES):
            raise ValueError("invalid exact page replacement set")
        if receipt.get("web_pages_replaced") != len(PAGES):
            hold("page_release_count_mismatch")
        if receipt.get("site_files_verified") != staged.get("staged_file_count"):
            hold("staged_site_file_count_mismatch")
        original_code = rollback.get("code")
        newly_created = rollback.get("new_code")
        listed = receipt.get("source_files_replaced")
        if (not isinstance(original_code, dict)
                or not isinstance(newly_created, list)
                or set(original_code) & set(newly_created)
                or set(original_code) | set(newly_created) != CODE
                or not isinstance(listed, list) or set(listed) != CODE):
            raise ValueError("invalid source rollback inventory")
        if Path(rollback.get("site", "")).resolve() != rollback_site.resolve():
            hold("site_rollback_location_drift")
        if Path(receipt.get("rollback_site", "")).resolve() != rollback_site.resolve():
            hold("deployment_site_rollback_location_drift")
        if Path(receipt.get("rollback_source", "")).resolve() != backup.resolve():
            hold("code_rollback_location_drift")
        published = _inventory(site)
        before = _inventory(rollback_site)
        names = set(published) - set(before)
        if set(before) - set(published):
            hold("previous_website_files_removed")
        if not isinstance(staged.get("additive_immutable_asset_count"), int):
            hold("unverified_new_assets_count")
        elif len(names) != staged["additive_immutable_asset_count"]:
            hold("additive_immutable_asset_count_mismatch")
        if len(published) != receipt.get("site_files_verified"):
            hold("published_site_inventory_count_mismatch")
        for name, hash_before in before.items():
            if name in PAGES:
                if hash_before != originals[name]:
                    hold("rollback_original_page_mismatch:" + name)
                if published.get(name) != expected_pages[name]:
                    hold("published_industry_page_mismatch:" + name)
            elif published.get(name) != hash_before:
                hold("protected_site_asset_changed:" + name)
        for name in names:
            if not name.startswith(("_next/static/", "brand/", "art/", "fonts/")):
                hold("unexpected_added_site_file:" + name)
        for name, expected_prior in original_code.items():
            path = backup / name
            if not path.is_file() or _sha_file(path) != expected_prior:
                hold("source_rollback_mismatch:" + name)
        for name in newly_created:
            if (backup / name).exists():
                hold("new_source_has_conflicting_old_copy:" + name)
        for name in CODE:
            running = repository / name
            source = released_source / name
            if not running.is_file() or not source.is_file():
                hold("source_file_not_available:" + name)
            elif _sha_file(running) != _sha_file(source):
                hold("deployed_source_drift:" + name)

    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        hold("unreadable_or_invalid_release_custody")
    return {
        "schema_version": "empire.organic_live_release_integrity.v1",
        "mode": "READ_ONLY",
        "status": "LIVE_BYTES_VERIFIED" if not problems else "HOLD_INTEGRITY_DRIFT",
        "file_integrity_pass": not problems,
        "issues": sorted(problems),
        "database_writes_performed_by_review": False,
        "outbound_sent_by_review": False,
        "payment_executed_by_review": False,
        "live_campaign_release_verified": None,
        "observed_visits": None,
        "accepted_campaign_events": None,
        "qualified_buyers": None,
        "consented_commercial_enquiries": None,
        "realised_revenue": None,
    }
