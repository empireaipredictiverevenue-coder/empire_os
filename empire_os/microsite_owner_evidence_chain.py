"""Read-only ASTRA acceptance of the SAME Chicago source -> export -> photo chain.

This proves exact byte lineage and browser evidence, NOT owner consent, rights,
commercial value, or a public deployment. Does not publish or mint approvals.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from empire_os.microsite_original_evidence_photos_v17 import (
    EVIDENCE, SOURCE_IMAGE_SHA256,
)

CANDIDATE_ID = "microsite_c4c5a13b626d293fe15c"
PREVIEW = f"{CANDIDATE_ID}.preview.html"
SOURCE_SHA = "3ee2f8d08d12d306ab3842b3cb5b041d34fb340f2f6a8d8a898821b2200293a0"
METADATA_SHA = "93c9f75a56b93cf4fde40656d177d734bf2814afd39ffe84bfd4d71555b15275"
PHOTO_SHA = "1ed1e468a51db0de0f633d955f86b6283b396924db71219816dd9c379dd25c88"
NATIVE_SHA = "7d7b864877c9a40c49e483f8717d2c121b8afb6d90e54b3e197f1357a41cf916"


def _bytes(path: Path, max_bytes: int) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ValueError("Evidence absent or symlinked: " + path.name)
    value = path.read_bytes()
    if not value or len(value) > max_bytes:
        raise ValueError("Evidence size failed: " + path.name)
    return value


def _json(path: Path) -> dict[str, Any]:
    result = json.loads(_bytes(path, 150000).decode())
    if not isinstance(result, dict):
        raise ValueError("Evidence record must be a mapping")
    return result


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _browser(stage: Path, expected: str) -> None:
    report = _json(stage / "browser_qa" / "puppeteer_browser_review.json")
    if (report.get("status") != "BROWSER_QA_PASS"
        or report.get("input_sha256") != expected
        or report.get("private") is not True
        or report.get("published") is not False
        or report.get("changed_production") is not False
        or report.get("blocked_external_requests") != 0
        or report.get("script_errors") != []):
        raise ValueError("Browser proof invalid or refers to another page")
    checks = report.get("checks")
    if not isinstance(checks, list) or len(checks) != 2:
        raise ValueError("Desktop/mobile proof missing")
    viewports: set[str] = set()
    for row in checks:
        label = row.get("viewport")
        dims = (row.get("width"), row.get("height"))
        if label not in ("desktop", "mobile") or label in viewports:
            raise ValueError("Unexpected browser viewport")
        if dims != ((1440, 900) if label == "desktop" else (390, 844)):
            raise ValueError("Browser dimensions mismatched")
        metrics = row.get("metrics", {})
        if (row.get("passed") is not True or metrics.get("h1") != 1
            or metrics.get("main") != 1 or metrics.get("forms") != 0
            or metrics.get("horizontal_overflow") is not False
            or metrics.get("logo_loaded") is not True
            or metrics.get("robots") != "noindex,nofollow,noarchive"):
            raise ValueError("Page accessibility, layout or noindex QA invalid")
        shot = Path(str(row.get("screenshot", "")))
        # Owner screenshot receipt includes its absolute private original path.
        # Require proof to refer to exactly the supplied private stage.
        if shot != stage / "browser_qa" / f"{PREVIEW[:-5]}.{label}.png":
            raise ValueError("Original owner screenshot is outside stage")
        if _sha(_bytes(shot, 7000000)) != row.get("screenshot_sha256"):
            raise ValueError("Browser screenshot was modified after proof")
        viewports.add(label)


def verify_chain(root: Path) -> dict[str, Any]:
    """No new authority, launch files or writes; validates exactly 3 stages."""
    root = Path(root)
    v10 = root / "predictive_microsite_research_depth_v10_FINAL_20261027"
    v16 = root / "chicago_original_owner_metadata_review_20261027"
    v17 = root / "chicago_original_owner_evidence_final_review_20261027"
    photos = root / "chicago_evidence_image_licence_research_20261027"

    source = _bytes(v10 / PREVIEW, 400000)
    metadata = _bytes(v16 / "chicago_owner_review_export.html", 400000)
    final = _bytes(v17 / PREVIEW, 400000)
    for what, data, expected in [
        ("original source",source,SOURCE_SHA),("HTML metadata export",metadata,METADATA_SHA),
        ("licensed-photo page",final,PHOTO_SHA)
    ]:
        if _sha(data) != expected:
            raise ValueError(what + " sha mismatch")
    original = _json(v10 / "manifest.json")
    proposals = original.get("packets")
    if (original.get("published") is not False or original.get("stage_only") is not True
        or original.get("held") != 1 or not isinstance(proposals, list)
        or len(proposals) != 1 or proposals[0].get("id") != CANDIDATE_ID
        or proposals[0].get("html_sha256") != SOURCE_SHA
        or proposals[0].get("status") != "HOLD_EVIDENCE"):
        raise ValueError("Original held source manifest changed")
    meta = _json(v16 / "owner_export_receipt.json")
    if (meta.get("source_preview_sha256") != SOURCE_SHA
        or meta.get("owner_reviewed_html_sha256") != METADATA_SHA
        or meta.get("owner_reviewed_html_bytes") != len(metadata)
        or meta.get("deterministic_edits") != 3
        or meta.get("owner_approvals_granted") is not False):
        raise ValueError("V16 HTML export no longer matches original source")
    image_receipt = _json(v17 / "five_image_provenance_receipt.json")
    records = image_receipt.get("five_evidence_photos")
    if (image_receipt.get("source_html_sha256") != METADATA_SHA
        or image_receipt.get("output_html_sha256") != PHOTO_SHA
        or image_receipt.get("output_bytes") != len(final)
        or image_receipt.get("live_publication") is not False
        or image_receipt.get("brand_media_owner_signoff") is not False
        or image_receipt.get("seo_owner_signoff") is not False
        or not isinstance(records, list) or len(records) != 5
        or final.count(b'class="evidence-visual"') != 5
        or final.count(b"Read official source") != 5):
        raise ValueError("Photographic page receipt/links do not match")
    for index, record in enumerate(records, 1):
        source_record = EVIDENCE[index-1]
        file = _bytes(photos / f"candidate_{index}.jpg", 3500000)
        if (record.get("evidence_note") != index
            or record.get("source_url") != source_record[4]
            or record.get("license_url") != source_record[5]
            or record.get("original_download_sha256") != SOURCE_IMAGE_SHA256[index-1]
            or _sha(file) != SOURCE_IMAGE_SHA256[index-1]
            or source_record[4].encode() not in final
            or source_record[5].encode() not in final):
            raise ValueError(f"Evidence photo {index} licence or source identity mismatch")
    for stage, expected in ((v10,SOURCE_SHA),(v16,METADATA_SHA),(v17,PHOTO_SHA)):
        _browser(stage, expected)
    native = _json(v17 / "native4k_qa" / "native4k_review.json")
    if (native.get("status") != "NATIVE_4K_QA_PASS"
        or native.get("sourceHtmlSha256") != NATIVE_SHA
        or _sha(_bytes(v17 / "chicago_final_native4k.html", 7500000)) != NATIVE_SHA
        or native.get("networkRequests") != 0
        or native.get("metrics",{}).get("sourceCards") != 5):
        raise ValueError("Actual full 3840px photographic proof does not match")
    return {
        "schema_version":"empire.chicago.original_owner_source_to_export_readback.v1",
        "mode":"READ_ONLY",
        "status":"SOURCE_TO_EXPORT_AND_MEDIA_QA_PASS",
        "candidate_id": CANDIDATE_ID,
        "v10_source_sha256": SOURCE_SHA,
        "v16_metadata_sha256": METADATA_SHA,
        "v17_page_sha256": PHOTO_SHA,
        "v17_page_bytes":len(final),
        "five_source_image_sha256_verified":True,
        "independent_browser_stages_verified":3,
        "native_4k_verified":True,
        "unverified_original_approvals": ["SEO publication","original brand artwork distribution","ASTRA site-owner deploy"],
        "real_live_url":None,
        "paid_media":False,
        "revenue_verified":False,
        "production_writes":0
    }
