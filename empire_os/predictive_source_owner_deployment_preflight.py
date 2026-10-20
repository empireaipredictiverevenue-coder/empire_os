"""Original production writer vs tested Predictive source-custody code.

Read-only source comparison. Never claims that code similarity proves EmpireDB
source authority or tenant policies; no unit changes, DB queries or secrets.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import os
import stat
from typing import Any

SCHEMA = "empire.predictive_revenue.original_source_owner_deployment.v1"
ORIGINAL = Path("/srv/empire_os/empire_os/predictive_intelligence.py")
THIS_SOURCE = Path(__file__).resolve().with_name("predictive_intelligence.py")
UNIT = Path("/etc/systemd/system/empire-predictive-intelligence.service")


class SourceDeploymentHold(ValueError):
    pass


def _digest(path: Path, *, max_bytes: int = 300000) -> tuple[str, bool]:
    if path.is_symlink() or not path.is_file():
        raise SourceDeploymentHold("source missing or symlinked")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    try:
        before = os.fstat(fd)
        if (not stat.S_ISREG(before.st_mode) or before.st_size > max_bytes
                or before.st_size < 100
                or before.st_mode & 0o002):
            raise SourceDeploymentHold("original code source unsafe")
        raw = os.read(fd, max_bytes + 1)
        after = os.fstat(fd)
        if (len(raw) != before.st_size or
                (before.st_mtime_ns, before.st_size, before.st_ino) !=
                (after.st_mtime_ns, after.st_size, after.st_ino)):
            raise SourceDeploymentHold("source changed during inventory")
        return sha256(raw).hexdigest(), bool(before.st_mode & 0o020)
    finally:
        os.close(fd)


def review_original_source_deployment(
    *, original: Path = ORIGINAL, candidate: Path = THIS_SOURCE,
    service_unit: Path = UNIT,
) -> dict[str, Any]:
    """Compare exact read-only source code and static unit path, not deployment."""
    if service_unit.is_symlink() or not service_unit.is_file():
        raise SourceDeploymentHold("production unit declaration missing")
    data = service_unit.read_bytes()
    if len(data) > 15000 or len(data) < 60:
        raise SourceDeploymentHold("unit declaration invalid")
    unit_text = data.decode("utf-8")
    expected = "ExecStart=/srv/empire_os/.venv/bin/python /srv/empire_os/scripts/build_predictive_intelligence.py --repo-root /srv/empire_os"
    if expected not in unit_text:
        raise SourceDeploymentHold("unexpected production unit startup declaration")
    old_hash, original_group_writable = _digest(original)
    new_hash, candidate_group_writable = _digest(candidate)
    exact = old_hash == new_hash
    custody_trusted = not (original_group_writable or candidate_group_writable)
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "status": (
            "ORIGINAL_SOURCE_CODE_MATCHES_PINNED_CANDIDATE_UNVERIFIED_RUNTIME"
            if exact and custody_trusted else
            "ORIGINAL_SOURCE_OWNER_DEPLOYMENT_STILL_REQUIRED"
        ),
        "original_production_code_sha256": old_hash,
        "tested_candidate_code_sha256": new_hash,
        "source_bytes_equal": exact,
        "original_shared_source_group_writable": original_group_writable,
        "candidate_source_group_writable": candidate_group_writable,
        "original_source_code_custody_trusted": custody_trusted,
        "original_service_declares_shared_checkout": True,
        "runtime_service_effective_unit_verified": False,
        "original_tenant_reader_role_verified": False,
        "commercial_outcomes_rls_force_verified": False,
        "original_database_outcome_rows_read": False,
        "original_forecast_registry_readback_authenticated": False,
        "customer_forecast_eligible": False,
        "source_file_mutated": False,
        "unit_modified": False,
        "database_writes": False,
        "execution_authority": "none",
    }
