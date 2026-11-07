"""Guarded addition of the ORIGINAL Data Intelligence candidate routes to EmpireOS.

Does not build an API, create credentials, or enable provider calls.
Only the existing release owner may call this after verifying canonical meter,
live founder membership, source rights and a tested rollback.
"""
from __future__ import annotations
from collections.abc import Callable, Mapping
from fastapi import FastAPI
from fastapi.routing import APIRoute

from empire_os.predictive_cloud_founder_session import (
    DataCloudPublicVerifier, attach_founder_session,
)

CUSTOMER_ROUTES=frozenset({
    ("/v1/data/usage","GET"),
    ("/v1/data/search","POST"),
    ("/v1/data/site-audits","POST"),
})
RELEASE_REQUIREMENTS=frozenset({
    "owner_lease_verified",
    "founder_only_path_verified",
    "signed_data_session_verified",
    "production_meter_role_verified",
    "production_meter_functions_verified",
    "source_egress_and_rights_reviewed",
    "rollback_preflight_verified",
    "fresh_local_restore_receipt_verified",
    "offhost_physical_recovery_verified",
    "dba_sql_and_acl_acceptance_verified",
    "existing_gateway_rollback_verified",
    "founder_only_pilot_verified",
    "billing_and_paid_provider_calls_disabled",
})

def inspect_routes(app:FastAPI)->frozenset[tuple[str,str]]:
    return frozenset((r.path,method) for r in app.routes
                     if isinstance(r,APIRoute) for method in r.methods)

def attach_existing_customer_routes(
    host:FastAPI,original_customer_candidate:FastAPI,
    public_verifier:DataCloudPublicVerifier,
    *, release_evidence:Callable[[],Mapping[str,bool]],
)->tuple[str,...]:
    """Fail closed before mutating the host.

    Attestation, metering, egress and billing controls belong to the existing
    gateway, database and customer API. This function grants none of them.
    """
    if not isinstance(host,FastAPI) or not isinstance(original_customer_candidate,FastAPI):
        raise RuntimeError("existing_gateway_and_candidate_required")
    # Never attach the private signing issuer to the public customer gateway.
    if type(public_verifier) is not DataCloudPublicVerifier:
        raise RuntimeError("public_verifier_only_required")
    if not callable(release_evidence):
        raise RuntimeError("independent_release_evidence_required")
    try:evidence=release_evidence()
    except Exception:
        raise RuntimeError("data_cloud_release_preflight_failed") from None
    if (not isinstance(evidence,Mapping) or not RELEASE_REQUIREMENTS.issubset(evidence)
        or any(evidence.get(k) is not True for k in RELEASE_REQUIREMENTS)):
        raise RuntimeError("data_cloud_release_preflight_failed")
    if getattr(host.state,"data_cloud_routes_attached",False):
        raise RuntimeError("data_cloud_routes_already_attached")
    if getattr(host,"middleware_stack",None) is not None:
        raise RuntimeError("gateway_must_be_assembled_before_startup")
    candidate=inspect_routes(original_customer_candidate)
    if candidate != CUSTOMER_ROUTES:
        raise RuntimeError("unexpected_customer_api_route_contract")
    if inspect_routes(host) & CUSTOMER_ROUTES:
        raise RuntimeError("existing_owner_data_route_collision")
    routes=[r for r in original_customer_candidate.routes if isinstance(r,APIRoute)]
    if len(routes)!=3:
        raise RuntimeError("unexpected_candidate_endpoint_count")
    # The original candidate must independently enforce metering, key binding
    # and safe-site egress. Its FastAPI middleware does not survive route copy.
    # Data session middleware is attached to this EXISTING gateway.
    # Register the trusted verifier before adding endpoints. Starlette rejects
    # middleware mutation after startup; the preflight above prevents a half-
    # mounted customer API on a running gateway.
    attach_founder_session(host,public_verifier,expose_exchange=False)
    host.router.routes.extend(routes)
    host.state.data_cloud_routes_attached=True
    return tuple(sorted(path for path,method in CUSTOMER_ROUTES))
