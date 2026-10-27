"""Opt-in native EmpireOS Revenue CRM pilot wiring; default is INACTIVE.

Only a founder-authorised, private local configuration can bind the already
implemented first-party login, canonical 041 membership reader, signed bearer
verifier, and per-tenant database transport. No DB writes or provisioning occur
on import; no tenant is inferred from the shared EmpireDB runtime login.
"""
from __future__ import annotations

import json
import os
import re
import stat
from pathlib import Path
from uuid import UUID

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import APIRouter
from psycopg.conninfo import conninfo_to_dict

from empire_os.revenue_crm_api import (
    build_authenticated_revenue_crm_resolver, create_revenue_crm_router,
)
from empire_os.revenue_crm_first_party_login import (
    PostgresCrmPasswordLogin, build_account_bound_membership_lookup,
    create_crm_login_router,
)
from empire_os.revenue_crm_signed_auth import (
    EmpireDbCrmMembershipReader, build_signed_crm_tenant_authenticator,
)

ACTIVATION_MODE = "APPROVED_READ_ONLY_PILOT"
CONFIG_SCHEMA = "empire.crm.pilot_runtime.v1"
_ALLOWED_CONFIG_KEYS = {
    "schema_version", "founder_approval_ref", "key_id",
    "signing_private_key_file", "auth_dsn", "membership_dsn",
    "tenant_dsns",
}
_READER_LOGIN = re.compile(r"^empire_crm_tenant_[0-9a-f]{12,32}$")
_KEY_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_APPROVAL = re.compile(r"^[A-Za-z0-9:@._/-]{12,160}$")


def _private_bytes(path: Path, *, limit: int) -> bytes:
    if not path.is_absolute() or path.is_symlink():
        raise ValueError("CRM private configuration must be an absolute regular path")
    meta = path.stat()
    if (not stat.S_ISREG(meta.st_mode)
        or (meta.st_mode & 0o077)
        or meta.st_uid not in (0, os.geteuid())
        or meta.st_size < 1
        or meta.st_size > limit):
        raise ValueError("CRM private file ownership, permissions or size invalid")
    return path.read_bytes()


def _dsn_role(dsn: object, *, expected: str | None = None) -> str:
    if not isinstance(dsn, str) or len(dsn) > 1024 or not dsn.strip():
        raise ValueError("dedicated CRM connection required")
    try:
        parts = conninfo_to_dict(dsn)
    except Exception:
        raise ValueError("invalid dedicated CRM connection") from None
    role = parts.get("user", "")
    if (parts.get("host") != "/var/run/postgresql"
        or str(parts.get("port", "")) != "5432"
        or parts.get("dbname") != "empiredb"
        or "service" in parts
        or "options" in parts
        or "passfile" in parts
        or not role):
        raise ValueError("canonical local EmpireDB connection required")
    if expected is not None and role != expected:
        raise ValueError("wrong dedicated CRM service login")
    return role


def build_pilot_routers(config_path: Path) -> tuple[APIRouter, APIRouter]:
    """Validate private configuration and construct opted-in routers.

    This function does not connect to the DB or mint accounts/tokens.
    Any invalid metadata raises rather than activating unsafe access.
    """
    raw = _private_bytes(config_path, limit=65536)
    try:
        configuration = json.loads(raw)
    except Exception:
        raise ValueError("invalid private CRM configuration") from None
    if (not isinstance(configuration, dict)
        or set(configuration) != _ALLOWED_CONFIG_KEYS
        or configuration.get("schema_version") != CONFIG_SCHEMA
        or not isinstance(configuration.get("founder_approval_ref"), str)
        or not _APPROVAL.fullmatch(configuration["founder_approval_ref"])):
        raise ValueError("explicitly approved complete CRM pilot configuration required")
    key_id = configuration["key_id"]
    if not isinstance(key_id, str) or not _KEY_ID.fullmatch(key_id):
        raise ValueError("canonical pinned CRM signing-key ID required")

    auth_dsn = configuration["auth_dsn"]
    membership_dsn = configuration["membership_dsn"]
    _dsn_role(auth_dsn, expected="empire_crm_auth_login")
    _dsn_role(membership_dsn, expected="empire_crm_membership_login")
    readers = configuration["tenant_dsns"]
    if not isinstance(readers, dict) or not 1 <= len(readers) <= 10:
        raise ValueError("bounded pilot tenant reader inventory required")
    seen_roles = set()
    for tenant, dsn in readers.items():
        if not isinstance(tenant, str) or str(UUID(tenant)) != tenant:
            raise ValueError("canonical approved CRM tenant UUID required")
        role = _dsn_role(dsn)
        if not _READER_LOGIN.fullmatch(role) or role in seen_roles:
            raise ValueError("unique dedicated CRM tenant reader login required")
        seen_roles.add(role)

    signing_key_path = configuration["signing_private_key_file"]
    if not isinstance(signing_key_path, str):
        raise ValueError("private signing key file path required")
    key_bytes = _private_bytes(Path(signing_key_path), limit=16384)
    try:
        private_key = serialization.load_pem_private_key(key_bytes, password=None)
    except Exception:
        raise ValueError("invalid pinned CRM signing key") from None
    if not isinstance(private_key, Ed25519PrivateKey):
        raise ValueError("Ed25519 CRM signing authority required")

    password_login = PostgresCrmPasswordLogin(auth_dsn)
    membership = EmpireDbCrmMembershipReader(membership_dsn)
    verified_membership = build_account_bound_membership_lookup(
        password_login, membership,
    )
    verifier = build_signed_crm_tenant_authenticator(
        {key_id: private_key.public_key()},
        load_membership=verified_membership,
    )
    resolver = build_authenticated_revenue_crm_resolver(verifier, readers)
    login_router = create_crm_login_router(
        password_login=password_login,
        load_membership=verified_membership,
        load_invitation_membership=membership,
        signing_key=private_key,
        key_id=key_id,
    )
    read_router = create_revenue_crm_router(
        resolve_authenticated_read=resolver,
    )
    # CRM owner-controlled private opt-in only. No second service/router, and
    # no order access if the original HELD security RPC is still unavailable.
    if os.environ.get("EMPIRE_CRM_V11_ORDER_READ_ENABLED") == "1":
        from empire_os.crm_revenue_case_private_api import (
            create_private_revenue_case_router,
        )
        from empire_os.revenue_crm_signed_auth import SignedCrmTenantVerifier
        case_verifier = SignedCrmTenantVerifier(
            {key_id: private_key.public_key()},
            load_membership=verified_membership,
        )
        case_router = create_private_revenue_case_router(
            resolve_authenticated_read=resolver,
            signed_crm_verifier=case_verifier,
            dedicated_tenant_dsns=readers,
            load_original_membership=verified_membership,
        )
        # The original private service inspects direct route paths. Avoid a
        # nested router: preserve the original single-router contract.
        if len(case_router.routes) != 1:
            raise ValueError("exactly one private V11 CRM read route required")
        case_route = case_router.routes[0]
        read_router.add_api_route(
            case_route.path, case_route.endpoint,
            methods=["GET"],
        )
    return read_router, login_router


def create_crm_routers_for_hub() -> tuple[APIRouter, ...]:
    """Existing hub is always OBSERVE unless intentionally configured."""
    mode = os.environ.get("EMPIRE_CRM_PILOT_MODE", "")
    if not mode:
        return (create_revenue_crm_router(),)
    if mode != ACTIVATION_MODE:
        raise ValueError("unrecognised CRM activation mode; refusing to start")
    file_path = os.environ.get("EMPIRE_CRM_PILOT_CONFIG_FILE", "")
    if not file_path:
        raise ValueError("CRM pilot configuration missing; refusing activation")
    return build_pilot_routers(Path(file_path))
