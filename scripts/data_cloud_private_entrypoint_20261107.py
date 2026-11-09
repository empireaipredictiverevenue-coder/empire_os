"""Add only the Data Cloud founder-session exchange to existing private CRM.

Existing CRM login stays authoritative, and the Data Cloud signing key is
separately conveyed via systemd LoadCredential (not present in public gateway).
"""
from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import empire_os
from cryptography.hazmat.primitives import serialization

RELEASE = Path("/opt/empire-ai/data-cloud-founder-pilot-20261107")
CONFIG = Path("/var/lib/empire-data-cloud-founder-pilot/runtime.json")
CRM_CONFIG = Path("/var/lib/empire-crm-first-party/pilot-runtime.json")
CRM_BASE = Path("/opt/empire-ai/crm-pilot-releases/smart-crm-work-queue-20261104v1/empire_os")
FLAG = "FOUNDER_APPROVED_READ_ONLY_USAGE_20261107"

if os.environ.get("EMPIRE_DATA_CLOUD_FOUNDER_USAGE_RELEASE") != FLAG:
    raise RuntimeError("data_cloud_founder_issuer_not_approved")
if Path(empire_os.__file__).resolve().parent != CRM_BASE:
    raise RuntimeError("crm_original_private_package_changed")
if RELEASE.is_symlink() or not RELEASE.is_dir() or RELEASE.stat().st_mode & 0o022:
    raise RuntimeError("data_cloud_frozen_release_required")
if CONFIG.is_symlink() or not CONFIG.is_file() or stat.S_IMODE(CONFIG.stat().st_mode) != 0o600:
    raise RuntimeError("private_data_cloud_config_unavailable")
cfg = json.loads(CONFIG.read_text())
if cfg.get("scope") != "FOUNDER_ONLY_USAGE_NO_PROVIDERS" or cfg.get("release_version") != 1:
    raise RuntimeError("data_cloud_issuer_scope_mismatch")

# The original private CRM issuer, including all owner-managed overlays.
from linkedin_oidc_issuer_workqueue_entrypoint import app  # noqa: E402
extension = RELEASE / "empire_os"
if extension.is_symlink() or not extension.is_dir():
    raise RuntimeError("data_cloud_package_missing")
empire_os.__path__.insert(0, str(extension))

from empire_os.revenue_crm_signed_auth import (  # noqa: E402
    EmpireDbCrmMembershipReader, SignedCrmTenantVerifier,
)
from empire_os.revenue_crm_first_party_login import (  # noqa: E402
    PostgresCrmPasswordLogin, build_account_bound_membership_lookup,
)
from empire_os.predictive_cloud_founder_session import (  # noqa: E402
    DataCloudFounderAuthority, attach_founder_session,
)

if CRM_CONFIG.is_symlink() or not CRM_CONFIG.is_file():
    raise RuntimeError("original_crm_configuration_missing")
crm = json.loads(CRM_CONFIG.read_text())
if crm.get("schema_version") != "empire.crm.pilot_runtime.v1":
    raise RuntimeError("original_crm_pilot_configuration_changed")
if crm.get("membership_dsn") != cfg.get("crm_membership_dsn"):
    raise RuntimeError("original_crm_membership_transport_changed")
if cfg.get("owner_tenant_id") not in crm["tenant_dsns"]:
    raise RuntimeError("approved_founder_tenant_not_in_crm")
if any(getattr(r, "path", "") == "/v1/data/auth/exchange" for r in app.routes):
    raise RuntimeError("existing_private_exchange_route_collision")

crm_key_path = Path(crm["signing_private_key_file"])
if crm_key_path.is_symlink() or not crm_key_path.is_file():
    raise RuntimeError("original_crm_signing_key_missing")
crm_signer = serialization.load_pem_private_key(crm_key_path.read_bytes(), password=None)
credentials_directory = os.environ.get("CREDENTIALS_DIRECTORY", "")
if not credentials_directory:
    raise RuntimeError("separate_systemd_issuer_credential_required")
private_key_path = Path(credentials_directory) / "empire-data-cloud-signing.pem"
if private_key_path.is_symlink() or not private_key_path.is_file():
    raise RuntimeError("data_cloud_signing_credential_missing")
signer = serialization.load_pem_private_key(private_key_path.read_bytes(), password=None)
if signer.public_key().public_bytes_raw().hex() != cfg["data_signing_public_key_hex"]:
    raise RuntimeError("data_cloud_pinned_signature_mismatch")

membership = EmpireDbCrmMembershipReader(crm["membership_dsn"])
bound = build_account_bound_membership_lookup(
    PostgresCrmPasswordLogin(crm["auth_dsn"]), membership,
)
crm_verifier = SignedCrmTenantVerifier(
    {crm["key_id"]: crm_signer.public_key()}, load_membership=bound,
)
authority = DataCloudFounderAuthority(
    crm_verifier=crm_verifier,
    live_membership=bound,
    data_entitlement=lambda actor,tenant: (
        actor == cfg["owner_actor_id"] and tenant == cfg["owner_tenant_id"]
    ),
    signing_key=signer,
    pinned_public_keys={cfg["data_signing_key_id"]: signer.public_key()},
    key_id=cfg["data_signing_key_id"],
)
attach_founder_session(
    app, authority, expose_exchange=True,
    customer_paths=frozenset({"/v1/data/usage"}),
)
