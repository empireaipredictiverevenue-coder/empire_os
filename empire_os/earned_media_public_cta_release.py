"""Two-file public CTA release candidate built from the exact live source.

Read-only. Separate from private Founder Console, public gateway, EmpireDB and
all other pending site changes. Produces deterministic source hashes/diffs,
never writes to /srv/empire_os or launches any process.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import Any
import difflib

from empire_os.earned_media_advisory_bridge import _read, SourceHeld

SCHEMA = "empire.earned_media.public_cta_scoped_candidate.v1"
GUIDE = "apps/empire-public-site/src/components/SaaSRevenueLeakageGuide.tsx"
ENTRY = "apps/empire-public-site/src/lib/commercial-entry-review.ts"
BACKEND = "empire_os/first_party_sales_interest.py"
ALLOWLIST_MARKER = '  "/industries/property", "/insights/revenue-opportunity-assessment",'
REPLACED_ALLOWLIST_MARKER = '  "/industries/property",'
GUIDE_IMPORT_AFTER = "// Research concepts: ChartMogul NRR methodology and Amplitude funnel guide.\n"
GUIDE_IMPORT = 'import { ownedRevenueGuideProposalHref } from "@/lib/commercial-entry-review";\n'
OLD_HREF = '<a href="/commercial#commercial-enquiry"'
NEW_HREF = '<a href={ownedRevenueGuideProposalHref()}'
ORIGINAL_HELPER_START = '''/**
 * Existing original buyer guide -> already-built consented commercial intake.
'''
HELPER_END = '''export function claimedEntryForReview(search: string): string | undefined {'''
BASE_HASHES = {
    GUIDE: "a16b40b18312d2c015c054a15c7a6f6a15be2988b03f4f987cc90d66d4a136ff",
    ENTRY: "525f5653024836e27b16237e26e653183330523ce619b933e608a343d679203f",
    BACKEND: "359ea1b4bff6f55f87ee91ceba6325a3b824eb95c085f7e815690e445f90bffa",
}


def _fail(reason: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA, "mode": "OBSERVE", "execution_authority": "none",
        "status": "HELD_PUBLIC_OWNER_BASELINE_OR_PATCH_DRIFT",
        "reason_code": reason,
        "files_proposed": [], "source_patch": None,
        "exact_original_baseline_verified": False,
        "site_owner_release_authorized": False, "deployment_authorized": False,
        "new_private_founder_route_in_scope": False, "gateway_restart_in_scope": False,
        "database_or_outbound_authority": False, "web_deployment_executed": False,
    }


def review_public_cta_candidate(
    repo_root: str | Path,
    *, live_root: str | Path,
    include_patch: bool = False,
) -> dict[str, Any]:
    staging = Path(repo_root)
    live = Path(live_root)
    source: dict[str, str] = {}
    baseline: dict[str, str] = {}
    for rel in (GUIDE, ENTRY, BACKEND):
        try:
            old, old_sha = _read(live, rel, max_bytes=150000)
            new, _ = _read(staging, rel, max_bytes=150000)
            if old_sha != BASE_HASHES[rel]:
                return _fail("PRODUCTION_SOURCE_DRIFT_" + rel.rsplit("/", 1)[-1])
            baseline[rel] = old.decode("utf-8")
            source[rel] = new.decode("utf-8")
        except (SourceHeld, OSError, UnicodeError, ValueError):
            return _fail("MISSING_OR_UNSAFE_BASELINE_SOURCE")

    old_guide = baseline[GUIDE]
    if old_guide.count(GUIDE_IMPORT_AFTER) != 1 or old_guide.count(OLD_HREF) != 1:
        return _fail("ORIGINAL_GUIDE_PATCH_ANCHOR_MISSING")
    candidate_guide = old_guide.replace(
        GUIDE_IMPORT_AFTER, GUIDE_IMPORT_AFTER + GUIDE_IMPORT
    ).replace(OLD_HREF, NEW_HREF)
    if source[GUIDE] != candidate_guide:
        return _fail("STAGED_GUIDE_SCOPE_DRIFT")

    old_entry, staged_entry = baseline[ENTRY], source[ENTRY]
    if (old_entry.count(HELPER_END) != 1
            or staged_entry.count(ORIGINAL_HELPER_START) != 1
            or staged_entry.count(HELPER_END) != 1
            or old_entry.count(ALLOWLIST_MARKER) != 1):
        return _fail("SOURCE_HELPER_PATCH_ANCHOR_MISSING")
    helper_start = staged_entry.index(ORIGINAL_HELPER_START)
    helper_end = staged_entry.index(HELPER_END, helper_start)
    helper = staged_entry[helper_start:helper_end]
    if (helper.count("export function ownedRevenueGuideProposalHref") != 1
            or helper.count('const path = "/predictive-revenue";') != 1
            or helper.count('return "/commercial?entry=" + encodeURIComponent(path) + "#commercial-enquiry";') != 1):
        return _fail("STAGED_SOURCE_HELPER_UNTRUSTED")
    candidate_entry = old_entry.replace(HELPER_END, helper + HELPER_END)
    # The staged branch also removes a dormant phantom entry-page allowlist.
    # Omit that unrelated backend/public-gateway maintenance from this exact
    # public-site-only release candidate; no server restart is required.
    expected_staged_entry = candidate_entry.replace(
        ALLOWLIST_MARKER, REPLACED_ALLOWLIST_MARKER,
    )
    if staged_entry != expected_staged_entry:
        return _fail("STAGED_ENTRY_PATCH_SCOPE_DRIFT")
    if BASE_HASHES[BACKEND] != sha256(baseline[BACKEND].encode()).hexdigest():
        return _fail("BACKEND_BASELINE_DRIFT")

    pairs = ((GUIDE, old_guide, candidate_guide), (ENTRY, old_entry, candidate_entry))
    patches = []
    files = []
    for rel, old, proposed in pairs:
        diff = "".join(difflib.unified_diff(
            old.splitlines(keepends=True), proposed.splitlines(keepends=True),
            fromfile="a/" + rel, tofile="b/" + rel, n=3,
        ))
        changed = [line for line in diff.splitlines() if line.startswith(('+', '-')) and not line.startswith(('+++', '---'))]
        if (not diff or len(diff) > 7500 or
                any('\"/insights/' in line and line.lstrip().startswith(('+\"', '-\"')) for line in changed)):
            return _fail("PUBLIC_CTA_PATCH_NOT_MINIMAL")
        patches.append(diff)
        files.append({
            "path": rel, "base_sha256": sha256(old.encode()).hexdigest(),
            "candidate_sha256": sha256(proposed.encode()).hexdigest(),
            "diff_lines": len(diff.splitlines()),
        })
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE", "execution_authority": "none",
        "status": "EXACT_TWO_FILE_PUBLIC_CTA_CANDIDATE_OWNER_REVIEW_REQUIRED",
        "exact_original_baseline_verified": True,
        "files_proposed": files,
        "changed_file_count": 2,
        "backend_unchanged_sha256": BASE_HASHES[BACKEND],
        "release_lane": "PUBLIC_OWNED_REVENUE_GUIDE_CTA_ONLY",
        "candidate_uses_existing_enquiry": True,
        "browser_entry_hint_unverified": True,
        "first_party_opt_in_and_suppression_unchanged": True,
        "staged_private_founder_page_excluded": True,
        "site_owner_release_authorized": False,
        "deployment_authorized": False,
        "new_private_founder_route_in_scope": False,
        "gateway_restart_in_scope": False,
        "database_or_outbound_authority": False,
        "web_deployment_executed": False,
        "actual_public_clicks_verified": False,
        "real_buyer_enquiry_verified": False,
        "verified_revenue": False,
        "original_source": "/predictive-revenue",
        "intended_same_origin_href": "/commercial?entry=%2Fpredictive-revenue#commercial-enquiry",
        "source_patch": "".join(patches) if include_patch else None,
    }
