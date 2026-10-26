"""Fail-closed bounded release authority for public AEO pages."""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Iterable

DEFAULT_AEO_ROOT = Path("/srv/empire_os/runtime/aeo")
DEFAULT_RECOVERY = Path("/srv/empire_os/runtime/search_intelligence/aeo_recovery/latest.json")
DEFAULT_RELEASE = Path("/srv/empire_os/runtime/search_intelligence/aeo_release.json")
PART = re.compile(r"^[A-Za-z0-9_-]{1,80}$")
MAX_RELEASE_PAGES = 10


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _content_sha(path: Path) -> str:
    html = path.read_text(encoding="utf-8")
    normalized = re.sub(r"\s+", " ", html).strip().encode("utf-8")
    return hashlib.sha256(normalized).hexdigest()


def _read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("JSON object required")
    return value


def build_release_manifest(
    pages: Iterable[tuple[str, str]],
    *,
    aeo_root: Path = DEFAULT_AEO_ROOT,
    recovery_path: Path = DEFAULT_RECOVERY,
    evidence_refs: Iterable[str],
) -> dict:
    requested = list(dict.fromkeys((str(n), str(m)) for n, m in pages))
    refs = [str(ref).strip() for ref in evidence_refs if str(ref).strip()]
    if not requested or len(requested) > MAX_RELEASE_PAGES:
        raise ValueError("bounded AEO cohort required")
    if not refs:
        raise ValueError("deployment evidence required")

    recovery = _read_json(recovery_path)
    assets = [row for row in recovery.get("assets", []) if isinstance(row, dict)]
    released = []
    for niche, metro in requested:
        if not PART.fullmatch(niche) or not PART.fullmatch(metro):
            raise ValueError("invalid AEO release path")
        matches = [
            row for row in assets
            if row.get("niche") == niche and row.get("metro") == metro
        ]
        if len(matches) != 1:
            raise ValueError("AEO recovery asset missing or ambiguous")
        asset = matches[0]
        if asset.get("status") != "structure_ready_for_evidence_review":
            raise ValueError("AEO asset not review-ready")
        if asset.get("risk_flags"):
            raise ValueError("AEO asset has risk flags")
        for flag in (
            "title_present", "h1_present", "canonical_present",
            "json_ld_present", "meta_description_present",
        ):
            if asset.get(flag) is not True:
                raise ValueError(f"AEO asset missing {flag}")
        path = aeo_root / niche / metro / "index.html"
        if not path.is_file():
            raise ValueError("AEO page file missing")
        digest = _content_sha(path)
        if asset.get("content_hash") != digest:
            raise ValueError("AEO recovery hash mismatch")
        released.append({
            "niche": niche,
            "metro": metro,
            "path": f"{niche}/{metro}/index.html",
            "sha256": digest,
        })

    return {
        "schema_version": "empire.aeo-release.v1",
        "release_verified": True,
        "deployment_evidence_refs": refs,
        "recovery_sha256": _sha(recovery_path),
        "zero_paid_media": True,
        "pages": released,
        "execution_authority": "none",
    }


def load_release(
    *,
    aeo_root: Path = DEFAULT_AEO_ROOT,
    recovery_path: Path = DEFAULT_RECOVERY,
    release_path: Path = DEFAULT_RELEASE,
) -> dict | None:
    try:
        release = _read_json(release_path)
        if (
            release.get("schema_version") != "empire.aeo-release.v1"
            or release.get("release_verified") is not True
            or release.get("zero_paid_media") is not True
            or release.get("execution_authority") != "none"
        ):
            return None
        refs = release.get("deployment_evidence_refs")
        if (
            not isinstance(refs, list) or not refs
            or any(not isinstance(ref, str) or not ref.strip() for ref in refs)
        ):
            return None
        pages = release.get("pages")
        if (
            not isinstance(pages, list)
            or not 1 <= len(pages) <= MAX_RELEASE_PAGES
            or any(
                not isinstance(page, dict)
                or set(page) != {"niche", "metro", "path", "sha256"}
                for page in pages
            )
        ):
            return None
        requested = [(p["niche"], p["metro"]) for p in pages]
        if len(set(requested)) != len(requested):
            return None
        # Snapshot-wide hashes are deliberately NOT a publishing dependency:
        # each periodic SEO recovery refresh can change 200+ unrelated pages.
        # Re-check EVERY previously approved page against the *current*
        # recovery's individual content hash, structure and risk flags.
        # The immutable approved path and content digest must still match.
        before = _sha(recovery_path)
        verified = build_release_manifest(
            requested,
            aeo_root=aeo_root,
            recovery_path=recovery_path,
            evidence_refs=refs,
        )
        after = _sha(recovery_path)
        if before != after or verified["recovery_sha256"] != before:
            return None
        if pages != verified["pages"]:
            return None
        return release
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        return None


def released_file(
    niche: str,
    metro: str,
    *,
    aeo_root: Path = DEFAULT_AEO_ROOT,
    recovery_path: Path = DEFAULT_RECOVERY,
    release_path: Path = DEFAULT_RELEASE,
) -> Path | None:
    release = load_release(
        aeo_root=aeo_root,
        recovery_path=recovery_path,
        release_path=release_path,
    )
    if release is None:
        return None
    for row in release["pages"]:
        if row["niche"] == niche and row["metro"] == metro:
            return aeo_root / row["path"]
    return None


def released_paths(**kwargs) -> list[str]:
    release = load_release(**kwargs)
    if release is None:
        return []
    # The published page canonical is slashless. Emitting the same route in
    # sitemap.xml avoids duplicate slash-vs-canonical signals. Published
    # content, SHA custody and route lookup remain completely unchanged.
    return [f"/aeo/{row['niche']}/{row['metro']}" for row in release["pages"]]


def release_status(
    *,
    aeo_root: Path = DEFAULT_AEO_ROOT,
    recovery_path: Path = DEFAULT_RECOVERY,
    release_path: Path = DEFAULT_RELEASE,
) -> dict:
    """Evidence-only AEO release status; no crawler, publisher or mutations."""
    result: dict = {
        "schema_version": "empire.aeo-release-status.v1",
        "mode": "OBSERVE",
        "source": "existing_bounded_release_manifest",
        "execution_authority": "none",
        "published_or_indexed_verified": False,
        "organic_traffic_verified": False,
        "revenue_verified": False,
        "release_valid": False,
        "snapshot_refresh_detected": False,
        "approved_page_count": 0,
        "released_paths": [],
        "reason": "RELEASE_UNAVAILABLE_OR_EVIDENCE_INVALID",
    }
    try:
        manifest = _read_json(release_path)
        old_digest = manifest.get("recovery_sha256")
        current_digest = _sha(recovery_path)
        result["snapshot_refresh_detected"] = (
            isinstance(old_digest, str) and old_digest != current_digest
        )
        valid = load_release(
            aeo_root=aeo_root,
            recovery_path=recovery_path,
            release_path=release_path,
        )
        if valid is None:
            return result
        result["release_valid"] = True
        result["approved_page_count"] = len(valid["pages"])
        result["released_paths"] = [
            f"/aeo/{page['niche']}/{page['metro']}/"
            for page in valid["pages"]
        ]
        result["reason"] = (
            "APPROVED_PAGE_EVIDENCE_VALID_AFTER_REFRESH"
            if result["snapshot_refresh_detected"]
            else "APPROVED_PAGE_EVIDENCE_VALID"
        )
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        pass
    return result
