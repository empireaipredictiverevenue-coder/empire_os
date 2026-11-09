"""Owner receipt validation for the original gateway's first-party pilot.

No runtime writes, credentials, grants, service control or network operations.
"""
from __future__ import annotations

import hashlib
import importlib
import json
import re
from pathlib import Path

from empire_os.predictive_cloud_customer_api.gateway_candidate_entrypoint import FIRST_PARTY_SEARCH_SOURCE
from empire_os.predictive_cloud_route_assembly import SEARCH_PILOT_REQUIREMENTS

FLAG = "FOUNDER_APPROVED_FIRST_PARTY_SEARCH_20261109"
SCOPE = "FOUNDER_ONLY_FIRST_PARTY_SEARCH_NO_PAID_API"
# All executable extension sources are pinned, including the original collector.
REQUIRED_FILES = frozenset({
    "data_cloud_public_entrypoint_20261107.py",
    "empire_os/predictive_cloud_search_release.py",
    "empire_os/predictive_cloud_route_assembly.py",
    "empire_os/predictive_cloud_founder_session.py",
    "empire_os/predictive_cloud_gateway_attestation.py",
    "empire_os/predictive_cloud_customer_api/gateway_candidate_entrypoint.py",
    "empire_os/predictive_cloud_customer_api/durable_api.py",
    "empire_os/predictive_cloud_customer_api/durable_store.py",
    "empire_os/predictive_cloud_customer_api/empiredb_metering_adapter.py",
    "empire_os/search_fabric/public_fallback.py",
    "empire_os/search_fabric/search.py",
})


def _imported_module_path(module_name: str) -> Path:
    """Prove the loaded Python module is the exact pinned release file."""
    loaded = importlib.import_module(module_name)
    source = getattr(loaded, "__file__", None)
    if not isinstance(source, str):
        raise RuntimeError("loaded_release_source_unavailable")
    return Path(source).resolve()


def load_search_release(path: Path, *, expected_sha256: str, release: Path,
                        owner: str, tenant: str):
    """Verify a separately approved nonsecret receipt before enabling fetching.

    Digest must be pinned by the release owner outside the receipt itself.
    File list may include additional transitive dependencies, never escapes.
    """
    def fail():
        raise RuntimeError("first_party_search_release_not_verified")

    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256 or ""):
        fail()
    if path.is_symlink() or not path.is_file() or path.stat().st_mode & 0o022:
        fail()
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        fail()
    receipt = json.loads(raw)
    if (receipt.get("scope") != SCOPE or receipt.get("owner_actor_id") != owner
            or receipt.get("owner_tenant_id") != tenant
            or receipt.get("source_id") != FIRST_PARTY_SEARCH_SOURCE):
        fail()
    evidence = receipt.get("verified_requirements", {})
    if any(evidence.get(k) is not True for k in SEARCH_PILOT_REQUIREMENTS):
        fail()
    files = receipt.get("files", {})
    if not REQUIRED_FILES.issubset(files):
        fail()
    for name, digest in files.items():
        relative = Path(name)
        target = release / relative
        if (relative.is_absolute() or ".." in relative.parts
                or any(p.is_symlink() for p in [target, *target.parents])
                or not target.is_file() or target.stat().st_mode & 0o022
                or hashlib.sha256(target.read_bytes()).hexdigest() != digest):
            fail()
        if name.startswith("empire_os/") and name.endswith(".py"):
            # Source bytes on disk alone are not provenance if a different
            # copy was already loaded into sys.modules by another overlay.
            module_name = name[:-3].replace("/", ".")
            try:
                running_path = _imported_module_path(module_name)
            except Exception:
                fail()
            if running_path != target.resolve():
                fail()

    def request_allowed(tenant_id, source_id, query, limit):
        return (tenant_id == tenant and source_id == FIRST_PARTY_SEARCH_SOURCE
                and type(query) is str and 3 <= len(query) <= 180
                and type(limit) is int and 1 <= limit <= 20)

    def output_allowed(tenant_id, source_id, payload):
        return (tenant_id == tenant and source_id == FIRST_PARTY_SEARCH_SOURCE
                and payload.get("source_id") == FIRST_PARTY_SEARCH_SOURCE)

    return evidence, request_allowed, output_allowed
