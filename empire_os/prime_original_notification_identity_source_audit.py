"""Original PRIME reminder Identity/source audit: repository evidence, not authority.

Read source files only. Deliberately cannot connect to any service or promote
repository code, tenant membership, prospect consent, or synthetic Ed25519
fixtures to real user/device reminder permission. Missing/unrecognised source
contracts are fail-closed REVIEW_REQUIRED, never CONNECTED.
"""
from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

SCHEMA="empire.prime.original_notification_identity_source_audit.v1"
DEFAULT_ROOT=Path(__file__).resolve().parents[1]


def _ast(root: Path, relative: str) -> ast.Module | None:
    path=root/relative
    try:
        # Guard against reading outside the supplied repo root.
        if not path.resolve().is_relative_to(root.resolve()):
            return None
        if not path.is_file() or path.stat().st_size>160_000:
            return None
        return ast.parse(path.read_text(encoding="utf-8"))
    except (OSError,UnicodeError,SyntaxError,ValueError):
        return None


def _unbound_consent_router_mounted(root: Path) -> bool:
    tree=_ast(root,"empire_os/hub.py")
    if tree is None:
        return False
    for node in ast.walk(tree):
        if not isinstance(node,ast.Call):
            continue
        if not isinstance(node.func,ast.Attribute) or node.func.attr!="include_router":
            continue
        if len(node.args)!=1 or not isinstance(node.args[0],ast.Call):
            continue
        mount=node.args[0]
        if (isinstance(mount.func,ast.Name)
            and mount.func.id=="create_consent_router"
            and not mount.args and not mount.keywords):
            return True
    return False


def _consent_api_contract(root: Path) -> dict[str,bool]:
    tree=_ast(root,"empire_os/consent_api.py")
    answer={
        "consent_endpoint_exists":False,
        "repository_default_none":False,
        "prospect_scoped_current_endpoint":False,
        "repository_absence_returns_503":False,
    }
    if tree is None:
        return answer
    source=(root/"empire_os/consent_api.py").read_text(encoding="utf-8")
    for fn in ast.walk(tree):
        if isinstance(fn,(ast.FunctionDef,ast.AsyncFunctionDef)):
            if fn.name=="create_consent_router":
                answer["consent_endpoint_exists"]=True
                defaults=fn.args.defaults
                answer["repository_default_none"]=any(
                    isinstance(x,ast.Constant) and x.value is None
                    for x in defaults
                )
            if fn.name=="current":
                answer["prospect_scoped_current_endpoint"]='"/prospects/{prospect_id}"' in source
    answer["repository_absence_returns_503"]=(
        "canonical_consent_repository_not_activated" in source
        and "status_code=503" in source
    )
    return answer


def review_original_reminder_identity_source(
    *, repo_root: Path | None=None,
) -> dict[str,Any]:
    """Source-level evidence ONLY, never production activation proof."""
    root=Path(repo_root) if repo_root is not None else DEFAULT_ROOT
    api=_consent_api_contract(root)
    unbound=_unbound_consent_router_mounted(root)
    crm_tree=_ast(root,"empire_os/revenue_crm_signed_auth.py")
    crm_source=(root/"empire_os/revenue_crm_signed_auth.py")
    crm_read_scope=(
        crm_tree is not None
        and crm_source.is_file()
        and 'AUTHORIZATION_SCOPE = "crm:read"' in crm_source.read_text(encoding="utf-8")
    )
    m061=root/"migrations/empiredb/061_flagship_timer_consent_write_gate_held.sql"
    held_default_deny=(
        m061.is_file()
        and "RETURN FALSE;" in m061.read_text(encoding="utf-8")
        and "TIMER061_ORIGINAL_CONSENT_AUTHORITY_UNVERIFIED" in
        m061.read_text(encoding="utf-8")
    )
    recognized=(unbound and all(api.values()) and crm_read_scope and held_default_deny)
    # A source-code audit cannot prove an app's running configuration, a
    # source owner's consent, an authenticated user's device, real delivery,
    # or DBA authority. Treat any changed/unrecognised contract as REVIEW.
    blockers=[
        "original_reminder_device_consent_authority_not_verified",
        "original_tenant_actor_device_binding_not_verified",
        "real_identity_owner_signature_key_custody_not_verified",
        "original_empiredb_057_to_061_owner_approval_not_verified",
        "real_notification_provider_callback_protocol_not_verified",
        "actual_consented_test_device_delivery_not_verified",
    ]
    return {
        "schema_version":SCHEMA,
        "mode":"SOURCE_READ_ONLY",
        "status":(
            "PROSPECT_CONSENT_ROUTER_UNBOUND_DEVICE_CONSENT_MISSING"
            if recognized else "ORIGINAL_IDENTITY_CONTRACT_REVIEW_REQUIRED"
        ),
        "original_hub_consent_router_created_without_repository":unbound,
        "original_consent_repository_default_none":api["repository_default_none"],
        "prospect_scoped_consent_api_present":api["consent_endpoint_exists"] and
            api["prospect_scoped_current_endpoint"],
        "unbound_consent_api_fail_closed_503":api["repository_absence_returns_503"],
        "existing_signed_crm_auth_is_read_only":crm_read_scope,
        "held_empiredb_061_deny_all_default_in_source":held_default_deny,
        "repository_code_is_not_live_configuration_proof":True,
        "verified_reminder_device_consent_authority":False,
        "original_identity_owner_approval_verified":False,
        "real_provider_sandbox_configured":False,
        "canonical_original_empiredb_migrations_approved":False,
        "original_empiredb_writes":False,
        "real_device_alert_sent":False,
        "execution_authority":"none",
        "blockers":blockers,
    }


def founder_reminder_identity_source_audit(
    value: dict[str,Any] | None,
) -> dict[str,Any]:
    """Founder-safe bounded projection. Never claims real user authorisation."""
    if value is None:
        return {
            "schema_version":"empire.prime.founder_reminder_identity_source.v1",
            "mode":"SOURCE_READ_ONLY",
            "status":"NOT_AUDITED",
            "real_device_consent_verified":False,
            "execution_authority":"none",
        }
    expected=review_original_reminder_identity_source(repo_root=DEFAULT_ROOT)
    keys=set(expected)
    if (type(value) is not dict or set(value)!=keys
        or value.get("schema_version")!=SCHEMA
        or value.get("mode")!="SOURCE_READ_ONLY"
        or value.get("status") not in (
            "PROSPECT_CONSENT_ROUTER_UNBOUND_DEVICE_CONSENT_MISSING",
            "ORIGINAL_IDENTITY_CONTRACT_REVIEW_REQUIRED",
        )
        or any(value.get(name) is not False for name in (
            "verified_reminder_device_consent_authority",
            "original_identity_owner_approval_verified",
            "real_provider_sandbox_configured",
            "canonical_original_empiredb_migrations_approved",
            "original_empiredb_writes","real_device_alert_sent",
        ))
        or value.get("repository_code_is_not_live_configuration_proof") is not True
        or value.get("execution_authority")!="none"
        or value.get("blockers")!=expected["blockers"]):
        raise ValueError("untrusted_original_identity_source_authority_claim")
    return {
        "schema_version":"empire.prime.founder_reminder_identity_source.v1",
        "mode":"SOURCE_READ_ONLY",
        "status":value["status"],
        "prospect_consent_is_not_device_permission":True,
        "real_device_consent_verified":False,
        "real_provider_connected":False,
        "execution_authority":"none",
    }
