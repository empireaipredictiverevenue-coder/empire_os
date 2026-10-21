"""Read-only preflight for the SSH-private Quora Founder Console release.

The candidate is copied from the currently deployed immutable Agency release.
No restart, systemd mutation, public publishing, outbound or session bypass.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BASE = Path("/home/ubuntu/empire_releases/founder_agency_private_console_20261020/releases/65ab711f28ae4eed9227eea2d8803f273b543ce3")
CANDIDATE = Path("/home/ubuntu/empire_releases/founder_quora_private_console_20261021/candidate-from-65ab711f")
EXPECTED = {"src/app/department/page.tsx", "src/app/department/quora/page.tsx", "src/lib/search-api.ts"}
COMMIT = "c18b44e55"
UNIT = "empire-founder-console.service"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _other_source(root: Path) -> dict[str, str]:
    result = {}
    for candidate in root.rglob("*"):
        if not candidate.is_file() or candidate.is_symlink():
            continue
        relative = candidate.relative_to(root)
        if ".next" in relative.parts or relative.name in (
            "agency-release-manifest.json", "quora-release-manifest.json"
        ):
            continue
        result[relative.as_posix()] = _sha(candidate)
    return result


def verify_manifest(base: Path = BASE, candidate: Path = CANDIDATE) -> dict:
    if any(p.is_symlink() or not p.is_dir() for p in (base, candidate)):
        raise ValueError("RELEASE_ROOT_SYMLINK_OR_MISSING")
    manifest_path = candidate / "quora-release-manifest.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise ValueError("RELEASE_MANIFEST_MISSING")
    doc = json.loads(manifest_path.read_text())
    previous = json.loads((base / "agency-release-manifest.json").read_text())
    if (doc.get("schema_version") != "empire.search.quora.private_ssh_founder_release.v1"
            or doc.get("release_mode") != "STAGED_ONLY_NOT_ACTIVE"
            or doc.get("quora_source_commit") != COMMIT
            or doc.get("base_frozen_release") != str(base)
            or doc.get("private_candidate_root") != str(candidate)
            or doc.get("original_agency_source_commit") != previous.get("source_commit")
            or doc.get("original_agency_build_id") != previous.get("build_id")
            or doc.get("candidate_build_id") != (candidate / ".next/BUILD_ID").read_text().strip()
            or set(doc.get("changed_source_paths") or ()) != EXPECTED
            or doc.get("founder_app_level_identity_independently_verified") is not False
            or doc.get("founder_service_restart_authorized") is not False
            or doc.get("customer_email_outbound_financial_or_public_site_authority") is not False):
        raise ValueError("FROZEN_QUORA_RELEASE_CONTRACT_DRIFT")
    for file, digest in previous.get("files_sha256", {}).items():
        if _sha(base / file) != digest:
            raise ValueError("ORIGINAL_AGENCY_RELEASE_HASH_DRIFT")
    if (candidate / "agency-release-manifest.json").read_bytes() != (
            base / "agency-release-manifest.json").read_bytes():
        raise ValueError("PRIOR_MANIFEST_MODIFIED")
    a, b = _other_source(base), _other_source(candidate)
    differences = {p for p in a.keys() | b.keys() if a.get(p) != b.get(p)}
    if differences != EXPECTED:
        raise ValueError("UNEXPECTED_FOUNDER_SOURCE_CHANGE")
    for file, digest in doc.get("file_sha256", {}).items():
        if file.startswith("/") or ".." in Path(file).parts or _sha(candidate / file) != digest:
            raise ValueError("QUORA_STAGE_ARTIFACT_HASH_DRIFT")
    return {
        "candidate_build_id": doc["candidate_build_id"],
        "candidate_manifest_sha256": _sha(manifest_path),
        "scoped_source_changes": sorted(differences),
        "active_agency_source_preserved": True,
    }


def _get_json(url: str) -> dict:
    with urlopen(Request(url, headers={"Accept": "application/json"}), timeout=7) as response:
        if response.status != 200:
            raise ValueError("PRIVATE_SEARCH_API_HTTP_UNEXPECTED")
        raw = response.read(200001)
    if len(raw) > 200000:
        raise ValueError("UNBOUNDED_PRIVATE_SEO_EVIDENCE")
    return json.loads(raw)


def _public_code(url: str) -> int | None:
    try:
        with urlopen(Request(url, headers={
            "User-Agent": "Mozilla/5.0 (compatible; EmpireReleasePreflight/1.0)"
        }), timeout=8) as response:
            return response.status
    except HTTPError as exc:
        return exc.code
    except (URLError, TimeoutError, OSError):
        return None


def _unit_property(name: str) -> str:
    result = subprocess.run(
        ["systemctl", "show", UNIT, "-p", name, "--value"],
        capture_output=True, text=True, timeout=8, check=False
    )
    if result.returncode:
        raise ValueError("FOUNDER_UNIT_NOT_READABLE")
    return result.stdout.strip()


def review() -> dict:
    manifest = verify_manifest()
    active = _unit_property("ActiveState")
    root = _unit_property("WorkingDirectory")
    ingress = _unit_property("Environment")
    try:
        source = _get_json("http://127.0.0.1:8771/v1/search/quora/review")
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        source = {}
    valid_source = (
        source.get("schema_version") == "empire.search_intelligence.quora_research.v1"
        and source.get("mode") == "OBSERVE"
        and source.get("topic_count") == 56
        and source.get("verified_quora_questions") == 0
        and source.get("execution_authority") == "NONE"
    )
    boundary = (
        _public_code("https://empire-ai.co.uk/department/quora") == 404
        and _public_code("https://empire-ai.co.uk/v1/search/quora/review") == 404
        and _public_code("http://127.0.0.1:3001/department/quora") == 404
    )
    ready = (
        active == "active" and root == str(BASE)
        and "EMPIRE_PRIVATE_FOUNDER_INGRESS_REVIEWED=1" in ingress.split()
        and valid_source and boundary
    )
    return {
        "schema_version": "empire.search.quora.founder_release_preflight.v1",
        "mode": "READ_ONLY",
        "status": (
            "IMMUTABLE_PRIVATE_CANDIDATE_VERIFIED_RESTART_APPROVAL_REQUIRED"
            if ready else "HELD_ACTIVE_RELEASE_OR_PRIVACY_GATE_DRIFT"
        ),
        "manifest_digest": manifest["candidate_manifest_sha256"],
        "candidate_build_id": manifest["candidate_build_id"],
        "source_paths_only": manifest["scoped_source_changes"],
        "agency_release_source_byte_preserved": True,
        "existing_founder_service_active": active == "active",
        "active_original_root_verified": root == str(BASE),
        "private_ingress_configuration_present": "EMPIRE_PRIVATE_FOUNDER_INGRESS_REVIEWED=1" in ingress.split(),
        "live_quora_56_topics_verified": valid_source,
        "negative_public_and_active_pre_activation_checks": boundary,
        "founder_app_level_identity_independently_verified": False,
        "founder_service_restart_performed": False,
        "public_page_published": False,
        "outbound_or_financial_action": False,
        "execution_authority": "NONE",
    }


if __name__ == "__main__":
    print(json.dumps(review(), sort_keys=True))
