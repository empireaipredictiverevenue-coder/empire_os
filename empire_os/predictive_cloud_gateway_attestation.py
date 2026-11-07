"""Reuse existing typed gateway attestation. Require signed, live membership-bound principal."""
from __future__ import annotations
from dataclasses import dataclass
import re
from fastapi import HTTPException,Request

_TENANT=re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:-]{0,99}$")

@dataclass(frozen=True,slots=True)
class VerifiedPrincipal:
    tenant_id:str
    actor_id:str
    issuer:str
    audience:str
    scopes:frozenset[str]
    membership_checked:bool
    source:str="empireos_trusted_gateway"

def verify_gateway_attestation(request:Request,*,tenant_id:str)->VerifiedPrincipal:
    state=request.scope.get("state")
    principal=state.get("empire_verified_principal") if isinstance(state,dict) else None
    if not isinstance(principal,VerifiedPrincipal):
        raise HTTPException(status_code=401,detail="authenticated_gateway_identity_required")
    if (principal.source!="empireos_trusted_gateway" or principal.issuer!="empire-os"
        or principal.audience!="empire-data-cloud" or not isinstance(principal.scopes,frozenset)
        or "data:read" not in principal.scopes or principal.membership_checked is not True
        or not isinstance(principal.actor_id,str) or not principal.actor_id.strip()
        or not isinstance(principal.tenant_id,str) or not _TENANT.fullmatch(principal.tenant_id)):
        raise HTTPException(status_code=403,detail="data_cloud_gateway_authority_invalid")
    if principal.tenant_id != tenant_id:
        raise HTTPException(status_code=403,detail="gateway_tenant_mismatch")
    return principal
