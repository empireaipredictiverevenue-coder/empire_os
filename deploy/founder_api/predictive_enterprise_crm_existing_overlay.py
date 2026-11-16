"""Add the existing tenant-bound predictive diagnostic to the current CRM.

Deployment copies this module and its reviewed ``empire_os`` extension into a
new root-owned versioned release directory, then changes only the existing
CRM unit's ExecStart target. All prior CRM imports, credentials and resolver
remain the source of authentication and database access.
"""
from __future__ import annotations

import hashlib
import stat
import sys
from pathlib import Path

RELEASE = Path("/opt/empire-ai/predictive-enterprise-crm-20261116-v1")
CURRENT_BROWSER = Path("/opt/empire-ai/data-cloud-founder-browser-20261113-v1")
MULTI_PIPELINE = Path("/opt/empire-ai/crm-multi-pipeline-20261112")


def _pinned_directory(path: Path) -> bool:
    try:
        info = path.lstat()
    except OSError:
        return False
    return path.is_dir() and not path.is_symlink() and info.st_uid == 0 and not info.st_mode & 0o022


if Path(__file__).resolve() != (RELEASE / Path(__file__).name):
    raise RuntimeError("predictive_crm_release_entrypoint_mismatch")
if not all(_pinned_directory(path) for path in (RELEASE, CURRENT_BROWSER, MULTI_PIPELINE)):
    raise RuntimeError("original_crm_release_not_pinned")

# Preserve and load the exact currently active browser overlay first. Its
# imports the existing CRM app, Data Cloud authority and protected credential.
sys.path.insert(0, str(CURRENT_BROWSER))
import data_cloud_founder_browser_entrypoint_20261113 as browser_release  # noqa: E402

if Path(browser_release.__file__).resolve() != (
    CURRENT_BROWSER / "data_cloud_founder_browser_entrypoint_20261113.py"
).resolve():
    raise RuntimeError("original_crm_browser_source_mismatch")

app = browser_release.app
import empire_os  # noqa: E402

EXTENSION = RELEASE / "empire_os"
if not _pinned_directory(EXTENSION):
    raise RuntimeError("predictive_crm_extension_not_pinned")
REVIEWED_SHA256 = {
    "predictive_revenue_crm_diagnostic_adapter.py": "15ca4264942f0eea70a33ecd6b922f62a169fe5208ff94c654713a3542022ebc",
    "predictive_revenue_crm_diagnostic_api.py": "f51f783df8076c2590232e60395ee05834f3c988948eb93f047d8199de2321f0",
    "predictive_revenue_enterprise_report.py": "cc5b3cd138eecd80628e3b4899247f9c8d300ecd8578a8a1e006cb991cedc721",
    "predictive_revenue_product_workbench.py": "88e9c8260198a2d4f32828e4289768e0b8324bed68227535d4332d11297f213e",
    "predictive_revenue_diagnostic_intelligence.py": "2c65551161ee4b3706d6bcf809e69cd0c501d5bb2f5974ab95eafed1835f5527",
    "predictive_revenue_scientific_readiness.py": "ed8a150f2a99e1a28c89245142d02ec1ccf210651fe1476846d2c341f1980212",
    "predictive_revenue_crm_diagnostic_ui/index.html": "94ef36b115cab8ff75a0b950b826c65ad60dc57e2182489dc5ffb7507b9e6d80",
    "predictive_revenue_crm_diagnostic_ui/app.js": "bc191da86cd5b88d918ae1076f86ec3ece5982266b33a5a4888e7e70b359ff74",
}
for relative, expected_sha256 in REVIEWED_SHA256.items():
    file = EXTENSION / relative
    try:
        info = file.lstat()
        actual_sha256 = hashlib.sha256(file.read_bytes()).hexdigest()
    except OSError:
        raise RuntimeError("predictive_crm_reviewed_source_missing") from None
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0
            or info.st_mode & 0o022 or actual_sha256 != expected_sha256):
        raise RuntimeError("predictive_crm_reviewed_source_mismatch")
# Append only the reviewed diagnostic modules. Earlier CRM package paths stay
# first, so AuthenticatedRevenueCrmRead and the Postgres repository retain
# their original class identities and implementation.
empire_os.__path__.append(str(EXTENSION))

sys.path.insert(0, str(MULTI_PIPELINE))
from crm_search_additive_20261109.entrypoint import resolver  # noqa: E402
from empire_os.predictive_revenue_crm_diagnostic_api import (  # noqa: E402
    create_authenticated_predictive_diagnostic_router,
)

if getattr(app.state, "predictive_crm_diagnostic_mounted", False):
    raise RuntimeError("predictive_crm_diagnostic_already_mounted")
router = create_authenticated_predictive_diagnostic_router(resolver)
app.include_router(router)
app.state.predictive_crm_diagnostic_mounted = True

EXPECTED = {
    ("GET", "/v1/revenue-crm/predictive-diagnostic"),
    ("GET", "/v1/revenue-crm/predictive-diagnostic/preview"),
    ("GET", "/v1/revenue-crm/predictive-diagnostic/markdown"),
    ("GET", "/v1/revenue-crm/predictive-diagnostic/app"),
    ("GET", "/v1/revenue-crm/predictive-diagnostic/app.js"),
}
actual = {
    (method, route.path)
    for route in router.routes
    for method in getattr(route, "methods", set())
}
if actual != EXPECTED:
    raise RuntimeError("predictive_crm_diagnostic_route_set_mismatch")
