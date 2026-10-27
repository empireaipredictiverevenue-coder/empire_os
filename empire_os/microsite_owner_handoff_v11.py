"""Original-owner Chicago preview acceptance reader — read only.

This only checks existing, immutable evidence. It cannot create an approval,
public URL, deployment receipt, production file, or payment/intake authority.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Callable, Any

from empire_os.owned_campaign_release import load_release, released_paths

CANDIDATE_ID = "microsite_c4c5a13b626d293fe15c"
PREVIEW_NAME = CANDIDATE_ID + ".preview.html"
EXPECTED_BRAND_CONTRACT = "ead735b5e223a3b179a23965c1ff11dc67efb78b4cd4e71df9b60550872bc518"
EXPECTED_OWNER_LOGO = "55e98ad2ae182991d95908738135779102beb81818cd7c3607a3a49e1f2aa596"
SOURCE_URLS_REQUIRED = 5
_READBACK_QA = "empire.microsite.browser_review.puppeteer_v1"


def _read_json_regular(path: Path) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"missing or symlinked owner evidence: {path.name}")
    data = json.loads(path.read_text("utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"invalid owner evidence: {path.name}")
    return data


def _digest_regular(path: Path, *, max_bytes: int) -> tuple[str, int]:
    if not path.is_file() or path.is_symlink():
        raise ValueError("preview or screenshot is missing or is a symlink")
    data = path.read_bytes()
    if not 1 <= len(data) <= max_bytes:
        raise ValueError("preview or screenshot exceeds expected bounded length")
    return sha256(data).hexdigest(), len(data)


def check_original_owner_handoff(
    staged: Path, *,
    original_release_reader: Callable[[], Any],
    original_paths_reader: Callable[[], list[str]],
) -> dict[str, Any]:
    """Verify SHA-locked V10 candidate without interpreting staged QA as launch."""
    staged = Path(staged)
    packet = _read_json_regular(staged / "manifest.json")
    browser = _read_json_regular(staged / "browser_qa/puppeteer_browser_review.json")
    if packet.get("schema_version") != "empire.microsite_factory_draft_batch.v2":
        raise ValueError("wrong candidate manifest contract")
    if (packet.get("published") is not False or packet.get("stage_only") is not True
            or packet.get("publishable_candidates") != 0
            or packet.get("held") != 1 or packet.get("candidates_reviewed") != 1
            or packet.get("previews") != [PREVIEW_NAME]):
        raise ValueError("candidate cannot be misrepresented as published")
    proposals = packet.get("packets")
    if not isinstance(proposals, list) or len(proposals) != 1:
        raise ValueError("exactly one source-backed microsite required")
    proposal = proposals[0]
    if (not isinstance(proposal, dict)
            or proposal.get("id") != CANDIDATE_ID
            or proposal.get("status") != "HOLD_EVIDENCE"
            or proposal.get("publishing_enabled") is not False
            or proposal.get("indexation_enabled") is not False
            or proposal.get("payments_enabled") is not False
            or proposal.get("outbound_enabled") is not False
            or proposal.get("linked_official_source_count") != SOURCE_URLS_REQUIRED
            or proposal.get("locally_useful_research_steps") != 5
            or proposal.get("copy_audit", {}).get("score") != 5):
        raise ValueError("candidate research, copy or safe-mode contract failed")

    visual = proposal.get("visual_qa", {})
    if (not isinstance(visual, dict)
            or visual.get("canonical_brand_reference_used") is not True
            or visual.get("canonical_brand_contract_sha256") != EXPECTED_BRAND_CONTRACT
            or visual.get("original_brand_logo_sha256") != EXPECTED_OWNER_LOGO
            or visual.get("brand_public_distribution_approved_by_owner") is not False):
        raise ValueError("canonical existing brand ownership conditions not upheld")

    preview = staged / PREVIEW_NAME
    preview_hash, preview_size = _digest_regular(preview, max_bytes=400000)
    if preview_hash != proposal.get("html_sha256"):
        raise ValueError("candidate preview SHA does not match authored snapshot")
    source = preview.read_text("utf-8")
    if (not re.search(r'<meta name="robots" content="noindex,nofollow,noarchive"', source)
            or "<form" in source.casefold() or "<script" in source.casefold()
            or "data:image/png;base64," not in source
            or "research-signal-strip" not in source
            or "research-visual-grid" not in source):
        raise ValueError("actual branded V10 HTML content is not as reviewed")

    if (browser.get("schema_version") != _READBACK_QA
            or browser.get("status") != "BROWSER_QA_PASS"
            or browser.get("input_sha256") != preview_hash
            or browser.get("private") is not True
            or browser.get("published") is not False
            or browser.get("changed_production") is not False
            or browser.get("browser_visual_review_complete") is not True
            or browser.get("blocked_external_requests") != 0
            or browser.get("script_errors") != []):
        raise ValueError("original website-brand owner Chromium evidence mismatch")
    checks = browser.get("checks")
    if not isinstance(checks, list) or len(checks) != 2:
        raise ValueError("desktop/mobile readback missing")
    browsers = {}
    for row in checks:
        if not isinstance(row, dict) or row.get("passed") is not True:
            raise ValueError("browser QA failed")
        label = row.get("viewport")
        if label not in ("desktop", "mobile") or label in browsers:
            raise ValueError("browser QA lacks exact two viewports")
        dims = (row.get("width"), row.get("height"))
        expected_dimensions = (1440, 900) if label == "desktop" else (390, 844)
        if dims != expected_dimensions:
            raise ValueError("viewport dimensions do not match original owner")
        metrics = row.get("metrics")
        if (not isinstance(metrics, dict) or metrics.get("forms") != 0
                or metrics.get("horizontal_overflow") is not False
                or metrics.get("h1") != 1 or metrics.get("main") != 1
                or metrics.get("logo_loaded") is not True
                or metrics.get("robots") != "noindex,nofollow,noarchive"):
            raise ValueError("visual/readability/safety measurements invalid")
        shot = Path(str(row.get("screenshot", "")))
        if shot.parent != staged / "browser_qa" or not shot.name.endswith(".png"):
            raise ValueError("screenshot outside original QA custody")
        shot_hash, _ = _digest_regular(shot, max_bytes=4000000)
        if shot_hash != row.get("screenshot_sha256"):
            raise ValueError("browser screenshot evidence altered after QA")
        browsers[label] = {"passed": True, "screenshot_sha256": shot_hash}

    old_release = original_release_reader()
    old_paths = original_paths_reader()
    original_5_preserved = (
        isinstance(old_release, dict)
        and isinstance(old_release.get("campaigns"), list)
        and len(old_release["campaigns"]) == 5
        and isinstance(old_paths, list)
        and len(old_paths) == 5
        and len(set(old_paths)) == 5
        and all(re.fullmatch(r"/research/campaign_[0-9a-f]{16,32}", x)
                for x in old_paths)
    )
    if not original_5_preserved:
        raise ValueError("original five independently released routes failed their source readback")

    return {
        "schema_version": "empire.microsite.owner_handoff_readiness_v11",
        "mode": "READ_ONLY",
        "status": "OWNER_SIGNOFF_AND_RELEASE_PENDING",
        "candidate_id": CANDIDATE_ID,
        "source_preview_sha256": preview_hash,
        "source_preview_bytes": preview_size,
        "original_brand_contract_sha256": EXPECTED_BRAND_CONTRACT,
        "original_brand_raster_sha256": EXPECTED_OWNER_LOGO,
        "original_browser_qa": "PASS",
        "original_browser_viewports": browsers,
        "original_five_released_routes_preserved": True,
        "original_five_route_count": 5,
        "original_five_route_ids": old_paths,
        "seo_publication_approved": False,
        "brand_public_artwork_distribution_approved": False,
        "original_website_release_readback": False,
        "chicago_public_url": None,
        "indexation_enabled": False,
        "outbound_authorized": False,
        "buyer_capacity_verified": None,
        "attributed_revenue_verified": False,
        "outstanding_owner_decisions": [
            "SEO: approve page accuracy, helpfulness, jurisdiction and indexation rationale",
            "BRAND: original-custody permission for live orbital-A artwork use",
            "WEBSITE: owner authorises single route extension, exact deployed SHA and production readback",
            "MEASUREMENT: connect authentic page outcomes only after original live release"
        ],
        "production_writes": 0,
        "new_site_routes": 0,
        "new_services": 0
    }


def check_live_original_owner(stage: Path, root: Path) -> dict[str, Any]:
    """Original 5-release code is reused; never a caller-fabricated proof."""
    return check_original_owner_handoff(
        stage,
        original_release_reader=lambda: load_release(root),
        original_paths_reader=lambda: released_paths(root),
    )
