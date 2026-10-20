"""Build a PRIVATE, non-published complete static release candidate.

Preserve public-only HTML and legacy hashed chunks while replacing the
exact 135 independently pinned stage files. This is NOT website signoff:
mixed-generation RSC/browser navigation still requires original owner QA.
No public files, symlinks, DNS, gateway, customer or payment actions.
"""
from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
from html.parser import HTMLParser
import json
from pathlib import Path, PurePosixPath
import shutil
from typing import Mapping

from scripts.review_combined_flagship_checkout_stage_20261020 import (
    verify as verify_original_stage,
)

LIVE = Path("/srv/empire_os/apps/empire-public-site/out")
STAGE = Path(
    "/home/ubuntu/empire_worktrees/flagship_checkout_source_convergence_20261020"
    "/apps/empire-public-site"
)
STAGE_MANIFEST = Path(
    "/srv/empire_os/docs/website/release_candidates/"
    "FLAGSHIP_CHECKOUT_COMBINED_STAGE_20261020.json"
)
CANDIDATE = Path(
    "/home/ubuntu/empire_releases/flagship_checkout_union_20261020"
)
SCHEMA = "empire.website.flagship_checkout_full_export_union.v1"
MAX_FILES = 2000
MAX_TOTAL_BYTES = 300_000_000
EXPECTED_STAGE_COUNT = 135


class ReleaseHold(ValueError):
    pass


def _file_index(root: Path) -> dict[str, tuple[str, int]]:
    if not root.is_dir() or root.is_symlink():
        raise ReleaseHold("UNTRUSTED_STATIC_ROOT")
    result: dict[str, tuple[str, int]] = {}
    total = 0
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ReleaseHold("UNREVIEWED_STATIC_SYMLINK")
        if path.is_dir():
            continue
        if not path.is_file():
            raise ReleaseHold("NONREGULAR_STATIC_ARTIFACT")
        rel = path.relative_to(root).as_posix()
        if rel.startswith(".") or ".." in PurePosixPath(rel).parts:
            raise ReleaseHold("UNSAFE_STATIC_PATH")
        data = path.read_bytes()
        total += len(data)
        if total > MAX_TOTAL_BYTES or len(result) >= MAX_FILES:
            raise ReleaseHold("STATIC_SIZE_BOUND")
        result[rel] = (sha256(data).hexdigest(), len(data))
    if not result:
        raise ReleaseHold("EMPTY_STATIC_ROOT")
    return result


class _Refs(HTMLParser):
    def __init__(self):
        super().__init__()
        self.required = set()
        self.external_scripts = 0

    def handle_starttag(self, tag, attrs):
        data = dict(attrs)
        if tag == "script" and str(data.get("src", "")).startswith(("https://", "http://")):
            self.external_scripts += 1
        for attr in ("src", "href"):
            val = data.get(attr)
            if not isinstance(val, str) or not val.startswith("/") or val.startswith("//"):
                continue
            resource = val.split("?", 1)[0].split("#", 1)[0].removeprefix("/")
            if resource.startswith("_next/") or resource.endswith((
                ".js", ".css", ".webp", ".png", ".jpg", ".jpeg",
                ".svg", ".woff", ".woff2", ".ico", ".avif",
            )):
                self.required.add(resource)


def summarize_indexes(
    live: Mapping[str, tuple[str, int]], stage: Mapping[str, tuple[str, int]],
) -> dict:
    if len(stage) != EXPECTED_STAGE_COUNT:
        raise ReleaseHold("UNEXPECTED_STAGE_FILE_COUNT")
    a, b = set(live), set(stage)
    same = {k for k in a & b if live[k] == stage[k]}
    changed = (a & b) - same
    live_only, stage_only = a-b, b-a
    legacy_html = sorted(k for k in live_only if k.endswith(".html"))
    stage_html = sorted(k for k in stage_only if k.endswith(".html"))
    if not {"index.html", "buy.html", "commercial.html"}.issubset(stage):
        raise ReleaseHold("CRITICAL_STAGE_PAGES_ABSENT")
    return {
        "live_count": len(live),
        "stage_count": len(stage),
        "unchanged_paths": len(same),
        "replaced_paths": len(changed),
        "retained_live_only_paths": len(live_only),
        "added_stage_paths": len(stage_only),
        "combined_file_count": len(a | b),
        "retained_live_only_html": legacy_html,
        "new_stage_html": stage_html,
        "changed_routing_payload_count": sum(
            k.endswith(".txt") for k in changed
        ),
        "retained_old_generation_js_count": sum(
            k.startswith("_next/") and k.endswith(".js") for k in live_only
        ),
        "stage_html_and_assets_verified": True,
    }


def _require_original_stage(source_project: Path, manifest: Path) -> None:
    verdict = verify_original_stage(project=source_project, pinned=manifest)
    if (
        verdict.get("status") != "COMBINED_STAGED_BUILD_HASH_VERIFIED"
        or verdict.get("source_and_build_match_original_pins") is not True
    ):
        raise ReleaseHold("ORIGINAL_STAGE_SOURCE_OR_HASH_HOLD")


def _build_union(target: Path, *, live: Path, stage: Path, source: Path,
                 stage_manifest: Path) -> dict:
    _require_original_stage(source, stage_manifest)
    live_before = _file_index(live)
    stage_before = _file_index(stage)
    summary = summarize_indexes(live_before, stage_before)
    if target.exists() or target.is_symlink():
        raise ReleaseHold("RELEASE_CANDIDATE_ALREADY_EXISTS")
    if target.resolve().is_relative_to(live.resolve()) or (
        live.resolve().is_relative_to(target.resolve())
    ):
        raise ReleaseHold("CANNOT_OVERWRITE_PUBLIC_SITE")
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        # Existing published extras are copied first to keep their
        # individual JS/CSS and page dependencies intact in the candidate.
        shutil.copytree(live, target)
        for rel in sorted(stage_before):
            original = stage / rel
            destination = target / rel
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(original, destination)
        live_after = _file_index(live)
        stage_after = _file_index(stage)
        if live_before != live_after or stage_before != stage_after:
            raise ReleaseHold("SOURCE_CHANGED_DURING_STAGE")
        expected = dict(live_before)
        expected.update(stage_before)
        actual = _file_index(target)
        if actual != expected:
            raise ReleaseHold("STAGED_UNION_FAILED_CONTENT_ATTESTATION")
        missing = set()
        external_scripts = 0
        for rel in expected:
            if not rel.endswith(".html"):
                continue
            parser = _Refs()
            parser.feed((target / rel).read_text(encoding="utf-8"))
            external_scripts += parser.external_scripts
            missing.update(k for k in parser.required if k not in expected)
        if missing:
            raise ReleaseHold("HTML_REFERENCES_MISSING_STATIC_ASSETS")
        receipt = {
            "schema_version": SCHEMA,
            "status": "PRIVATE_MIXED_GENERATION_STATIC_CANDIDATE_ASSEMBLED",
            "candidate_integrity_verified": True,
            "original_source_stage_sha256": sha256(stage_manifest.read_bytes()).hexdigest(),
            "original_live_source_preserved": live_before == live_after,
            "static_file_sha256": {k: v[0] for k, v in sorted(expected.items())},
            "summary": summary,
            "html_local_asset_references_missing": 0,
            "html_external_script_tags_present": external_scripts,
            "mixed_next_build_routing_navigation_review_required": True,
            "legacy_unreviewed_routes_included": True,
            "legacy_html_and_new_next_chunks_browser_qa_required": True,
            "current_website_owner_release_approval": False,
            "new_public_release_authorized": False,
            "public_files_modified": False,
            "payment_execution": False,
            "buyer_form_or_order_submitted": False,
            "revenue_verified": False,
        }
        (target.parent / "RELEASE_CANDIDATE_RECEIPT.json").write_text(
            json.dumps(receipt, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        return receipt
    except Exception:
        # A failed private candidate stays quarantined for diagnosis.
        # Never remove the public live site and never deploy partial files.
        raise


def _verify_private_candidate(candidate: Path) -> dict:
    receipt_path = candidate.parent / "RELEASE_CANDIDATE_RECEIPT.json"
    if receipt_path.is_symlink() or not receipt_path.is_file():
        raise ReleaseHold("PRIVATE_RECEIPT_MISSING")
    raw = json.loads(receipt_path.read_text(encoding="utf-8"))
    if (
        not isinstance(raw, dict)
        or raw.get("schema_version") != SCHEMA
        or raw.get("status") != "PRIVATE_MIXED_GENERATION_STATIC_CANDIDATE_ASSEMBLED"
        or raw.get("candidate_integrity_verified") is not True
        or raw.get("new_public_release_authorized") is not False
        or raw.get("public_files_modified") is not False
        or raw.get("mixed_next_build_routing_navigation_review_required") is not True
        or type(raw.get("static_file_sha256")) is not dict
    ):
        raise ReleaseHold("PRIVATE_RECEIPT_AUTHORITY_HOLD")
    actual = _file_index(candidate)
    expected = raw["static_file_sha256"]
    if (
        len(expected) != 632
        or set(actual) != set(expected)
        or any(actual[k][0] != expected[k] for k in actual)
    ):
        raise ReleaseHold("PRIVATE_RECEIPT_FILE_INTEGRITY_HOLD")
    return {
        "status": "PRIVATE_UNION_CONTENT_ATTESTED_REVIEW_HELD",
        "verified_file_count": len(actual),
        "mixed_next_build_routing_navigation_review_required": True,
        "new_public_release_authorized": False,
        "public_files_modified": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--read-only", action="store_true")
    parser.add_argument("--prepare-private-candidate", action="store_true")
    parser.add_argument("--verify-private-candidate", action="store_true")
    args = parser.parse_args(argv)
    if sum((args.read_only, args.prepare_private_candidate,
            args.verify_private_candidate)) != 1:
        parser.error("select exactly one non-deploy action")
    try:
        if args.verify_private_candidate:
            report = _verify_private_candidate(CANDIDATE / "out")
            print(json.dumps({"schema_version": SCHEMA, **report}, sort_keys=True))
            return 0
        _require_original_stage(STAGE, STAGE_MANIFEST)
        live_index = _file_index(LIVE)
        staged_index = _file_index(STAGE / "out")
        summary = summarize_indexes(live_index, staged_index)
        if args.prepare_private_candidate:
            result = _build_union(
                CANDIDATE / "out",
                live=LIVE, stage=STAGE / "out", source=STAGE,
                stage_manifest=STAGE_MANIFEST,
            )
            status = result["status"]
            summary = result["summary"]
        else:
            status = "PRIVATE_UNION_PREVIEW_ONLY"
        report = {
            "schema_version": SCHEMA,
            "status": status,
            "summary": summary,
            "public_files_modified": False,
            "new_public_release_authorized": False,
            "mixed_next_build_routing_navigation_review_required": True,
            "buyer_order_or_payment_submitted": False,
        }
        print(json.dumps(report, sort_keys=True))
        return 0
    except (ReleaseHold, OSError, ValueError, UnicodeError) as exc:
        # Do not include unreviewed filesystem paths or copied source data.
        print(json.dumps({
            "schema_version": SCHEMA, "status": "PRIVATE_RELEASE_HOLD",
            "reason": str(exc) if isinstance(exc, ReleaseHold) else "SOURCE_ERROR",
            "public_files_modified": False,
            "new_public_release_authorized": False,
        }, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
