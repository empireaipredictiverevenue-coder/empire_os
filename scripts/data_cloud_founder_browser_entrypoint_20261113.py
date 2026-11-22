"""Standalone original CRM import chain, ADDITIVE founder Data Cloud search.

Release owner copies these reviewed files to a pinned, root-owned versioned
release and supplies the existing unit's protected API-key LoadCredential.
No independent app, key store, CRM login or new tenant.
"""
from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

RELEASE = Path("/opt/empire-ai/data-cloud-founder-browser-20261113-v1")
PREVIOUS = Path("/opt/empire-ai/crm-multi-pipeline-20261112")
APP_PATH = PREVIOUS / "empire_crm_multi_pipeline_20261112" / "entrypoint.py"

if (
    RELEASE.is_symlink()
    or not RELEASE.is_dir()
    or RELEASE.stat().st_uid != 0
    or RELEASE.stat().st_mode & 0o022
    or not APP_PATH.is_file()
    or PREVIOUS.is_symlink()
):
    raise RuntimeError("original_crm_data_cloud_release_not_pinned")

# The current original multi-pipeline owner remains the host. Import it FIRST.
sys.path.insert(0, str(PREVIOUS))
from empire_crm_multi_pipeline_20261112.entrypoint import app  # noqa: E402
from data_cloud_private_entrypoint_20261107 import authority  # noqa: E402
import empire_os  # noqa: E402

# Then extend the existing package search path with only our reviewed addition.
extension = RELEASE / "empire_os"
if extension.is_symlink() or not extension.is_dir():
    raise RuntimeError("original_data_cloud_browser_extension_missing")
empire_os.__path__.insert(0, str(extension))
import empire_os.predictive_cloud_customer_api as data_cloud_package  # noqa: E402
data_cloud_package.__path__.insert(
    0, str(extension / "predictive_cloud_customer_api"),
)

from empire_os.predictive_cloud_customer_api.founder_browser_proxy import (  # noqa: E402
    install_founder_crm_search,
)
from empire_os.predictive_cloud_customer_api.founder_browser_ui import (  # noqa: E402
    install_founder_search_ui,
)

# Verify Python is actually executing reviewed frozen bytes, not another
# concurrently deployed owner module from sys.modules.
for module_name in ("founder_browser_proxy", "founder_browser_ui"):
    imported = sys.modules[
        "empire_os.predictive_cloud_customer_api." + module_name
    ]
    expected = extension / "predictive_cloud_customer_api" / (module_name + ".py")
    if Path(imported.__file__).resolve() != expected.resolve():
        raise RuntimeError("founder_browser_loaded_source_mismatch")

# Fail closed before adding any route unless the existing original service has
# been explicitly given the API key through its own systemd credentials.
credential_dir = os.environ.get("CREDENTIALS_DIRECTORY", "")
if not credential_dir or not Path(credential_dir, "empire-data-cloud-founder-api-key").is_file():
    raise RuntimeError("original_crm_search_systemd_credential_missing")

install_founder_search_ui(app)
install_founder_crm_search(app, authority)
