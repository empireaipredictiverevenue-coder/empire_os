"""Generate or audit one offline ASTRA website candidate; NEVER deploy it."""
from __future__ import annotations

import argparse
from pathlib import Path
import json

from empire_os.earned_media_saas_rebased_release import (
    prepare_private_candidate, read_index, index_digest, ReleaseHeld, SCHEMA,
    LIVE_DRIFT, REPLACE, LINK, OLD_LINK, route_static_references,
    plan_rebased_delta,
)

ROOT = Path("/home/ubuntu/empire_releases/earned_media_saas_union_20261026")
LIVE = Path("/srv/empire_os/apps/empire-public-site/out")
PIN = Path("/home/ubuntu/empire_releases/seo_saas_20261024_after_v2/REBASED_CANDIDATE_RECEIPT.json")
ORIGINAL_PREVIEW = Path(
    "/home/ubuntu/empire_worktrees/saas_evidence_preview_20261025/candidate_union_20261025"
)
REBUILD = ROOT / "build_source/apps/empire-public-site/out"
OUTPUT = ROOT / "rebased_candidate"
RECEIPT = ROOT / "private_candidate_receipt.json"


def audit() -> dict:
    if RECEIPT.is_symlink() or not RECEIPT.is_file() or RECEIPT.stat().st_size > 40000:
        raise ReleaseHeld("ORIGINAL_PRIVATE_REBASE_RECEIPT_NOT_FOUND")
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    if (not isinstance(receipt, dict) or receipt.get("schema_version") != SCHEMA
            or receipt.get("production_publication_authorized") is not False
            or receipt.get("production_mutated") is not False
            or receipt.get("independent_astra_website_owner_approval_verified") is not False):
        raise ReleaseHeld("PRIVATE_REBASE_RECEIPT_UNTRUSTED")
    orig_index = read_index(LIVE)
    stage_index = read_index(OUTPUT)
    if (index_digest(orig_index) != receipt["source_live_inventory_sha256"]
            or index_digest(stage_index) != receipt["rebased_candidate_inventory_sha256"]
            or len(stage_index) != receipt["rebased_candidate_file_count"]):
        raise ReleaseHeld("LIVE_OR_OFFLINE_CANDIDATE_HAS_CHANGED_SINCE_REBASE")
    old_only = {k for k in orig_index if stage_index[k] != orig_index[k]}
    added = set(stage_index) - set(orig_index)
    if (old_only != REPLACE or sorted(added) != receipt["build"]["new_asset_paths"]
            or any(stage_index[k] != orig_index[k] for k in LIVE_DRIFT)):
        raise ReleaseHeld("REBASED_SITE_SCOPE_CHANGED")
    html = (OUTPUT / "predictive-revenue.html").read_text("utf-8")
    rsc = (OUTPUT / "predictive-revenue.txt").read_text("utf-8")
    refs = route_static_references(html, rsc)
    code = {k: (OUTPUT / k).read_bytes()
            for k in refs if "/app/predictive-revenue/page-" in k}
    _plan, recomputed_assets = plan_rebased_delta(
        orig_index, stage_index, html, rsc, code,
    )
    if recomputed_assets != added:
        raise ReleaseHeld("STATIC_ASSET_RECHECK_MISMATCH")
    return {
        "schema_version": SCHEMA,
        "status": "OFFLINE_AST​RA_REBASED_CANDIDATE_INTEGRITY_PASS_RELEASE_HELD".replace("\u200b", ""),
        "source_live_file_count": len(orig_index),
        "rebased_candidate_file_count": len(stage_index),
        "changed_existing_files": sorted(old_only),
        "retained_newer_industry_pages": sorted(LIVE_DRIFT),
        "new_only_hashed_asset_count": len(added),
        "published_html_changed": False,
        "public_release_authorized": False,
        "independent_astra_owner_approval_verified": False,
        "compiled_hydration_cta_matches_html": True,
        "browser_qa_independently_verified": False,
        "real_buyer_enquiry_verified": False,
        "revenue_verified": False,
        "execution_authority": "none",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    flags = parser.add_mutually_exclusive_group(required=True)
    flags.add_argument("--prepare-private", action="store_true")
    flags.add_argument("--verify-private", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.prepare_private:
            if RECEIPT.exists() or RECEIPT.is_symlink():
                raise ReleaseHeld("PRIVATE_STAGING_RECEIPT_ALREADY_EXISTS")
            report = prepare_private_candidate(
                live_root=LIVE, prior_pin=PIN, prior_preview=ORIGINAL_PREVIEW,
                rebuilt_root=REBUILD, output_root=OUTPUT,
            )
            RECEIPT.parent.mkdir(parents=True, exist_ok=True)
            with RECEIPT.open("x", encoding="utf-8") as file:
                json.dump(report, file, sort_keys=True, indent=2)
                file.write("\n")
            result = audit()
        else:
            result = audit()
        print(json.dumps(result, sort_keys=True))
        return 0
    except (OSError, ValueError, TypeError, KeyError, UnicodeError) as exc:
        print(json.dumps({
            "schema_version": SCHEMA, "status": "HELD_SOURCE_OR_ASSET_INTEGRITY",
            "reason": str(exc) if isinstance(exc, ReleaseHeld) else type(exc).__name__,
            "site_published": False,
        }, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
