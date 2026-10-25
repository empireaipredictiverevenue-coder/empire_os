"""Read-only exact release preflight for SaaS Predictive Revenue page/RSC pair.

This program NEVER publishes. It accepts only the reviewed two-file route
replacement + ten new hashed assets, compares all original site files with the
prior approved hash pin, verifies page resources and rejects concurrent drift.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
from html.parser import HTMLParser
import json
from pathlib import Path, PurePosixPath
import re
from urllib.parse import urlsplit, unquote

LIVE = Path("/srv/empire_os/apps/empire-public-site/out")
CANDIDATE = Path(
    "/home/ubuntu/empire_worktrees/saas_evidence_preview_20261025"
    "/candidate_union_20261025"
)
MANIFEST = Path(
    "/home/ubuntu/empire_worktrees/saas_evidence_preview_20261025"
    "/preview_visual_receipts/saas_evidence_union_manifest.json"
)
LIVE_APPROVED_PIN = Path(
    "/home/ubuntu/empire_releases/seo_saas_20261024_after_v2"
    "/REBASED_CANDIDATE_RECEIPT.json"
)
REPLACE = frozenset({"predictive-revenue.html", "predictive-revenue.txt"})
EXPECTED_ADDITIONS = 10
EXPECTED_LIVE_COUNT = 662
EXPECTED_UNION_COUNT = 672


class SitePreflightHold(ValueError):
    pass


def _root(path: Path) -> None:
    if path.is_symlink() or not path.is_dir():
        raise SitePreflightHold("SITE_DIRECTORY_MISSING_OR_SYMLINK")


def read_index(root: Path) -> dict[str, str]:
    _root(root)
    result: dict[str, str] = {}
    byte_count = 0
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise SitePreflightHold("UNREVIEWED_SYMLINK_IN_RELEASE_TREE")
        if path.is_dir():
            continue
        if not path.is_file():
            raise SitePreflightHold("UNEXPECTED_TREE_ENTRY")
        rel = path.relative_to(root).as_posix()
        parts = PurePosixPath(rel)
        if (not rel or rel.startswith(".") or ".." in parts.parts
                or "\\" in rel):
            raise SitePreflightHold("UNSAFE_RELEASE_PATH")
        if len(result) >= 1000 or path.stat().st_size > 20_000_000:
            raise SitePreflightHold("RELEASE_FILE_LIMIT_EXCEEDED")
        data = path.read_bytes()
        byte_count += len(data)
        if byte_count > 120_000_000:
            raise SitePreflightHold("RELEASE_TOTAL_SIZE_EXCEEDED")
        result[rel] = sha256(data).hexdigest()
    return result


def index_digest(data: dict[str, str]) -> str:
    return sha256("".join(
        f"{key} {value}\n" for key, value in sorted(data.items())
    ).encode()).hexdigest()


def validated_scope(baseline: dict[str, str], candidate: dict[str, str],
                    manifest: dict, *, live_count=EXPECTED_LIVE_COUNT,
                    union_count=EXPECTED_UNION_COUNT,
                    added_count=EXPECTED_ADDITIONS) -> dict:
    if not isinstance(manifest, dict) or manifest.get("schema_version") != (
        "empire.saas.offline_single_route_union.v1"
    ):
        raise SitePreflightHold("MISMATCHED_RELEASE_SCHEMA")
    if manifest.get("status") != (
        "OFFLINE_PAIRED_HTML_RSC_UNION_CANDIDATE_PREPARED_NOT_PUBLISHED"
    ):
        raise SitePreflightHold("RELEASE_PAIR_NOT_VERIFIED")
    for gate in ("release_owner_approved", "site_published", "live_site_mutated",
                 "money_or_outbound_touched", "public_catalogue_fixture_in_candidate"):
        if manifest.get(gate) is not False:
            raise SitePreflightHold("UNTRUSTED_RELEASE_AUTHORITY_OR_SCOPE_" + gate)
    if (manifest.get("replacement_routes") != sorted(REPLACE)
            or manifest.get("previously_retained_stale_rsc_corrected") is not True
            or manifest.get("changed_other_old_files") != 0):
        raise SitePreflightHold("SINGLE_ROUTE_PAIR_NOT_RECONCILED")
    if len(baseline) != live_count or len(candidate) != union_count:
        raise SitePreflightHold("RELEASE_INVENTORY_COUNT_CHANGED")
    if manifest.get("approved_live_file_count") != live_count or (
        manifest.get("candidate_file_count") != union_count
    ):
        raise SitePreflightHold("MANIFEST_FILE_COUNT_MISMATCH")
    if not REPLACE.issubset(baseline) or not REPLACE.issubset(candidate):
        raise SitePreflightHold("EXISTING_ROUTE_PAIR_MISSING")
    if set(baseline) - set(candidate):
        raise SitePreflightHold("CANDIDATE_REMOVED_EXISTING_FILE")
    changed = {name for name in baseline
               if baseline[name] != candidate[name]}
    additions = set(candidate) - set(baseline)
    if changed != REPLACE or len(additions) != added_count:
        raise SitePreflightHold("UNEXPECTED_RELEASE_PAYLOAD_DELTA")
    if any(not x.startswith("_next/static/") or x.startswith("_next/static/.")
           for x in additions):
        raise SitePreflightHold("NEW_ASSETS_OUTSIDE_HASHED_STATIC_SCOPE")
    expected_assets = manifest.get("added_static_assets")
    if (not isinstance(expected_assets, list)
            or len(expected_assets) != added_count
            or set(entry.get("path") for entry in expected_assets
                   if isinstance(entry, dict)) != additions
            or any(not isinstance(entry, dict) or
                   candidate[entry["path"]] != entry.get("sha256")
                   for entry in expected_assets)):
        raise SitePreflightHold("NEW_ASSET_RECEIPT_MISMATCH")
    pairs = {
        "predictive-revenue.html": (
            "prior_html_sha256", "candidate_html_sha256"),
        "predictive-revenue.txt": (
            "original_rsc_sha256", "candidate_rsc_sha256"),
    }
    for name, (previous, new) in pairs.items():
        if (manifest.get(previous) != baseline[name] or
                manifest.get(new) != candidate[name]):
            raise SitePreflightHold("ROUTE_SOURCE_HASH_DRIFT_" + name)
    if manifest.get("candidate_inventory_sha256") != index_digest(candidate):
        raise SitePreflightHold("FULL_CANDIDATE_INDEX_CHANGED")
    return {
        "replacement_files": sorted(changed),
        "added_assets": sorted(additions),
        "unchanged_original_files": len(baseline) - len(changed),
    }


class HTMLRefs(HTMLParser):
    def __init__(self):
        super().__init__()
        self.refs: set[str] = set()

    def handle_starttag(self, tag: str, attrs):
        a = dict(attrs)
        for name in ("href", "src"):
            if not isinstance(a.get(name), str):
                continue
            url = a[name]
            parsed = urlsplit(url)
            if parsed.netloc or (parsed.scheme and parsed.scheme != ""):
                continue
            value = unquote(parsed.path)
            if (value.startswith("/_next/static/")
                    or value.startswith("/fonts/")
                    or value.startswith("/brand/")):
                self.refs.add(value.lstrip("/"))


def paired_resources_valid(candidate_root: Path) -> dict:
    html = (candidate_root / "predictive-revenue.html").read_text(encoding="utf8")
    rsc = (candidate_root / "predictive-revenue.txt").read_text(encoding="utf8")
    for needed in ('id="deployment-request"', 'id="free-evidence-sample"',
                   'Explore a free revenue-evidence example'):
        if needed not in html:
            raise SitePreflightHold("EXPECTED_NEW_SAAS_FUNNEL_MARKUP_MISSING")
    expected = "static/chunks/app/predictive-revenue/page-119dcf00a0b5a51e.js"
    old = "static/chunks/app/predictive-revenue/page-8a641c1798fea86e.js"
    if expected not in rsc or old in rsc:
        raise SitePreflightHold("NAVIGATION_RSC_NOT_MATCHING_NEW_APP_PAGE")
    parser = HTMLRefs()
    parser.feed(html)
    # RSC can load chunks from framework-relative static paths without /_next.
    rsc_urls = re.findall(
        r'(?:/_next/)?static/(?:chunks|css)/[a-zA-Z0-9_./-]+\.(?:js|css)',
        rsc
    )
    wanted = parser.refs | {
        item.lstrip("/") if item.lstrip("/").startswith("_next/")
        else "_next/" + item.lstrip("/")
        for item in rsc_urls
    }
    missing = []
    for ref in sorted(wanted):
        parts = PurePosixPath(ref)
        if ".." in parts.parts or ref.startswith("."):
            raise SitePreflightHold("UNSAFE_EMBEDDED_RESOURCE_PATH")
        if not (candidate_root / ref).is_file():
            missing.append(ref)
    if missing:
        raise SitePreflightHold("OFFLINE_CANDIDATE_RESOURCE_MISSING:" + missing[0])
    return {"paired_navigation_chunk_verified": True,
            "local_browser_assets_checked": len(wanted),
            "local_browser_assets_missing": 0}


def review(live: Path = LIVE, candidate: Path = CANDIDATE,
           manifest_path: Path = MANIFEST, pin_path: Path = LIVE_APPROVED_PIN
           ) -> dict:
    for p in (manifest_path, pin_path):
        if p.is_symlink() or not p.is_file() or p.stat().st_size > 500_000:
            raise SitePreflightHold("MISSING_OR_UNSAFE_RELEASE_RECEIPT")
    manifest = json.loads(manifest_path.read_text(encoding="utf8"))
    pin = json.loads(pin_path.read_text(encoding="utf8"))
    baseline = read_index(live)
    if (not isinstance(pin, dict)
            or baseline != pin.get("private_candidate_sha256")):
        raise SitePreflightHold("LIVE_SITE_NOT_MATCHING_APPROVED_PIN")
    index = read_index(candidate)
    scope = validated_scope(baseline, index, manifest)
    resources = paired_resources_valid(candidate)
    if baseline != read_index(live):
        raise SitePreflightHold("CONCURRENT_SITE_CHANGE_DURING_PREFLIGHT")
    return {
        "schema_version": "empire.saas.paired_route_release_preflight.v1",
        "status": "PRIVATE_REVIEW_PASS_PUBLICATION_HELD",
        "existing_live_file_count": len(baseline),
        "offline_candidate_file_count": len(index),
        "approved_source_inventory_matched": True,
        **scope,
        **resources,
        "founder_visual_approval_for_this_candidate": False,
        "website_release_owner_authority": False,
        "publication_authorized": False,
        "publication_performed": False,
        "database_writes": False,
        "new_outbound_sent": False,
        "payment_action": False,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.parse_args()
    try:
        print(json.dumps(review(), sort_keys=True))
        return 0
    except (OSError, ValueError, TypeError, UnicodeError, json.JSONDecodeError) as exc:
        print(json.dumps({
            "status": "PRIVATE_RELEASE_CANDIDATE_HELD",
            "reason": str(exc) if isinstance(exc, SitePreflightHold) else type(exc).__name__,
            "publication_authorized": False,
            "publication_performed": False,
        }, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
