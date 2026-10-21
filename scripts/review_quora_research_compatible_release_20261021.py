"""Read-only verification of the Quora overlay on active Empire Research.

Never restarts Founder services, changes immutable releases, posts to Quora or
alters EmpireDB. Release scope is exactly three SEO/Quora source changes.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

from scripts.review_quora_founder_release_20261021 import (
    _get_json, _public_code, _unit_property,
)

BASE_RELEASE = Path("/home/ubuntu/empire_releases/founder_research_ssh_private_20261021/candidate-39d028058bcd")
CANDIDATE = Path("/home/ubuntu/empire_releases/founder_quora_research_compatible_20261021/candidate-from-39d028058")
SOURCE_COMMIT = "39d028058bcdea57637ddc5ad2a12b28b1c8abf9"
QUORA_COMMIT = "b0958a16a"
EXPECTED = {"src/app/department/page.tsx", "src/app/department/quora/page.tsx", "src/lib/search-api.ts"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sources(root: Path) -> dict[str, str]:
    output = {}
    for p in root.rglob("*"):
        if not p.is_file() or p.is_symlink():
            continue
        rel = p.relative_to(root)
        if ".next" in rel.parts or ".next.original-research-preserved" in rel.parts:
            continue
        output[rel.as_posix()] = sha(p)
    return output


def verify_staged_release(base: Path = BASE_RELEASE, candidate: Path = CANDIDATE) -> dict:
    if (base.is_symlink() or candidate.is_symlink()
            or not base.is_dir() or not candidate.is_dir()):
        raise ValueError("UNTRUSTED_RELEASE_ROOT")
    original = json.loads((base / "release-manifest.json").read_text())
    p = candidate / "quora-research-compatible-manifest.json"
    if p.is_symlink() or not p.is_file():
        raise ValueError("UNTRUSTED_RELEASE_MANIFEST")
    manifest = json.loads(p.read_text())
    if (original.get("source_commit") != SOURCE_COMMIT
            or manifest.get("schema_version")
                != "empire.search.quora.research_compatible_founder_release.v1"
            or manifest.get("state") != "STAGED_ONLY_NOT_DEPLOYED"
            or manifest.get("base_source_commit") != SOURCE_COMMIT
            or manifest.get("quora_source_commit") != QUORA_COMMIT
            or manifest.get("base_frozen_root") != str(base / "web")
            or manifest.get("candidate_root") != str(candidate / "web")
            or manifest.get("original_research_release_manifest_sha256")
                != sha(base / "release-manifest.json")
            or set(manifest.get("only_source_changes") or ()) != EXPECTED
            or manifest.get("founder_console_restart_approved") is not False
            or manifest.get("new_public_ingress_authorized") is not False
            or manifest.get("outbound_payments_or_db_writes_authorized") is not False
            or manifest.get("app_level_identity_verified_in_this_preflight") is not False
            or manifest.get("candidate_build_id")
                != (candidate / "web/.next/BUILD_ID").read_text().strip()
            or manifest.get("base_research_build_id")
                != (base / "web/.next/BUILD_ID").read_text().strip()):
        raise ValueError("RELEASE_CUSTODY_MISMATCH")
    for name, digest in original["web_source_checksums"].items():
        if sha(base / "web" / name) != digest:
            raise ValueError("ORIGINAL_RESEARCH_RELEASE_TAMPERED")
    original_files, staged_files = sources(base / "web"), sources(candidate / "web")
    actual = {name for name in original_files.keys() | staged_files.keys()
              if original_files.get(name) != staged_files.get(name)}
    if actual != EXPECTED:
        raise ValueError("ADDITIVE_SOURCE_SCOPE_BROKEN")
    artifacts = manifest.get("file_sha256")
    if not isinstance(artifacts, dict) or len(artifacts) < 9:
        raise ValueError("RELEASE_FILE_INVENTORY_INCOMPLETE")
    for name, checksum in artifacts.items():
        if (not isinstance(name, str) or name.startswith("/")
                or ".." in Path(name).parts
                or sha(candidate / "web" / name) != checksum):
            raise ValueError("RELEASE_FILE_SHA256_MISMATCH")
    return {
        "manifest_sha256": sha(p),
        "build_id": manifest["candidate_build_id"],
        "preserved_research_sources": True,
        "three_additive_source_paths": sorted(actual),
    }


def review() -> dict:
    pinned = verify_staged_release()
    root = _unit_property("WorkingDirectory")
    state = _unit_property("ActiveState")
    ingress = _unit_property("Environment").split()
    try:
        doc = _get_json("http://127.0.0.1:8771/v1/search/quora/review")
    except (ValueError, OSError, TypeError, json.JSONDecodeError):
        doc = {}
    correct_api = (
        doc.get("schema_version") == "empire.search_intelligence.quora_research.v1"
        and doc.get("topic_count") == 56
        and doc.get("mode") == "OBSERVE"
        and doc.get("execution_authority") == "NONE"
        and doc.get("verified_quora_questions") == 0
    )
    private = (
        _public_code("https://empire-ai.co.uk/department/quora") == 404
        and _public_code("https://empire-ai.co.uk/v1/search/quora/review") == 404
        and _public_code("http://127.0.0.1:3001/department/quora") == 404
    )
    active_ok = state == "active" and root == str(BASE_RELEASE / "web")
    ready = (active_ok and correct_api and private
             and "EMPIRE_PRIVATE_FOUNDER_INGRESS_REVIEWED=1" in ingress)
    return {
        "schema_version": "empire.search.quora.research_compatible_preflight.v1",
        "status": ("RESEARCH_COMPATIBLE_CANDIDATE_STAGED_APPROVAL_REQUIRED"
                   if ready else "HELD_RELEASE_OR_PRIVATE_BOUNDARY_CHANGED"),
        "candidate_manifest_sha256": pinned["manifest_sha256"],
        "candidate_build_id": pinned["build_id"],
        "original_research_source_preserved": pinned["preserved_research_sources"],
        "active_research_founder_root_verified": active_ok,
        "live_56_topic_private_search_verified": correct_api,
        "public_negative_checks_passed": private,
        "founder_app_identity_independently_verified": False,
        "founder_restart_performed": False,
        "execution_authority": "NONE",
    }


if __name__ == "__main__":
    print(json.dumps(review(), sort_keys=True))
