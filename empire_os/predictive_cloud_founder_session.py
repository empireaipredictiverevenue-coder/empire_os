"""Audience-bound founder-only Data Cloud session exchange for existing EmpireOS login.

No new account database. Never trust caller headers/tenant identities. No activation on import.
"""
from __future__ import annotations
import base64, json, re, secrets, time
from collections.abc import Callable, Mapping
from uuid import UUID
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from fastapi import APIRouter, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from empire_os.revenue_crm_signed_auth import SignedCrmTenantVerifier, _object, _decode
from empire_os.saas_scale import TenantMembership
from empire_os.predictive_cloud_gateway_attestation import VerifiedPrincipal

ISSUER="empire-os"
AUDIENCE="empire-data-cloud"
SCOPE="data:read"
TOKEN_TTL=300
RE_KID=re.compile(r"^[A-Za-z0-9_-]{1,64}$")
RE_USER=re.compile(r"^[A-Za-z0-9:@._/-]{1,128}$")
RE_JTI=re.compile(r"^[A-Za-z0-9_-]{16,128}$")

def enc(value:bytes)->str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")

def tenant_uuid(value):
    try: normalized=str(UUID(value))
    except (TypeError,AttributeError,ValueError): raise ValueError("bad tenant") from None
    if normalized!=value: raise ValueError("noncanonical tenant")
    return value

class DataCloudPublicVerifier:
    def __init__(self,*,live_membership:Callable,data_entitlement:Callable,
                 pinned_public_keys:Mapping[str,Ed25519PublicKey],now:Callable|None=None):
        if not callable(live_membership) or not callable(data_entitlement):
            raise ValueError("live Data Cloud membership and entitlement required")
        if not isinstance(pinned_public_keys,Mapping) or not pinned_public_keys or any(
            not isinstance(k,str) or not RE_KID.fullmatch(k) or not isinstance(v,Ed25519PublicKey)
            for k,v in pinned_public_keys.items()
        ):raise ValueError("pinned Data Cloud verification keys required")
        self.membership=live_membership;self.entitlement=data_entitlement
        self.keys=dict(pinned_public_keys)
        self.now=now or (lambda:int(time.time()))

    def check(self,subject,tenant):
        if not isinstance(subject,str) or not RE_USER.fullmatch(subject): raise ValueError("invalid signed actor")
        try:
            m=self.membership(subject,tenant)
            ok=(isinstance(m,TenantMembership) and m.user_id==subject and m.tenant_id==tenant
                and m.role=="owner" and m.can("admin") and self.entitlement(subject,tenant) is True)
        except Exception: ok=False
        if not ok: raise PermissionError("current founder/data entitlement not proven")

    def verify(self,token:str)->VerifiedPrincipal:
        if not isinstance(token,str) or not 30<=len(token)<=4096: raise ValueError("invalid session")
        parts=token.split(".")
        if len(parts)!=3: raise ValueError("invalid JWT shape")
        h=_object(parts[0],384)
        if set(h)!={"alg","typ","kid"} or h["alg"]!="EdDSA" or h["typ"]!="JWT": raise ValueError("bad JWT header")
        kid=h["kid"]
        if not isinstance(kid,str) or not RE_KID.fullmatch(kid) or kid not in self.keys:
            raise ValueError("untrusted Data Cloud issuer")
        sig=_decode(parts[2],64)
        if len(sig)!=64: raise ValueError("invalid signature length")
        try:self.keys[kid].verify(sig,(parts[0]+"."+parts[1]).encode("ascii"))
        except InvalidSignature: raise ValueError("bad signature") from None
        c=_object(parts[1],1536)
        if set(c)!={"iss","aud","sub","tenant_id","scope","iat","nbf","exp","jti"}:
            raise ValueError("unexpected signed claims")
        if (c["iss"],c["aud"],c["scope"])!=(ISSUER,AUDIENCE,SCOPE): raise ValueError("wrong token audience")
        tenant=tenant_uuid(c["tenant_id"]);actor=c["sub"]
        if not isinstance(c["jti"],str) or not RE_JTI.fullmatch(c["jti"]): raise ValueError("bad session jti")
        t=[c[x] for x in ("iat","nbf","exp")];now=int(self.now())
        if any(type(x) is not int for x in t) or not (
            t[0]<=now+30 and t[1]<=now+30 and t[2]>now-30 and 0<t[2]-t[0]<=TOKEN_TTL and t[1]<=t[2]
        ):raise ValueError("expired Data Cloud session")
        self.check(actor,tenant)
        return VerifiedPrincipal(tenant_id=tenant,actor_id=actor,issuer=ISSUER,audience=AUDIENCE,
                                 scopes=frozenset({SCOPE}),membership_checked=True)


class DataCloudFounderAuthority(DataCloudPublicVerifier):
    def __init__(self, *, crm_verifier:SignedCrmTenantVerifier, live_membership:Callable,
                 data_entitlement:Callable, signing_key:Ed25519PrivateKey,
                 pinned_public_keys:Mapping[str,Ed25519PublicKey], key_id:str, now:Callable|None=None):
        if not isinstance(crm_verifier,SignedCrmTenantVerifier) or not callable(live_membership) or not callable(data_entitlement):
            raise ValueError("verified CRM login, membership and separate data entitlement required")
        if not isinstance(signing_key,Ed25519PrivateKey) or not RE_KID.fullmatch(key_id or ""):
            raise ValueError("Data Cloud signing key required")
        if not isinstance(pinned_public_keys,Mapping) or key_id not in pinned_public_keys or any(
            not isinstance(k,str) or not RE_KID.fullmatch(k) or not isinstance(v,Ed25519PublicKey)
            for k,v in pinned_public_keys.items()
        ):
            raise ValueError("pinned Data Cloud public keys required")
        if pinned_public_keys[key_id].public_bytes_raw()!=signing_key.public_key().public_bytes_raw():
            raise ValueError("Data Cloud signing key must match pinned verifier")
        if any(k.public_bytes_raw()==signing_key.public_key().public_bytes_raw()
               for k in crm_verifier._public_keys.values()):
            raise ValueError("Data Cloud and CRM must use separate signing keys")
        self.crm=crm_verifier;self.membership=live_membership;self.entitlement=data_entitlement
        self.signer=signing_key;self.keys=dict(pinned_public_keys);self.key_id=key_id
        self.now=now or (lambda:int(time.time()))

    def exchange(self,crm_bearer:str):
        if not isinstance(crm_bearer,str) or not 30<=len(crm_bearer)<=4096:
            raise ValueError("valid existing CRM token required")
        tenant=tenant_uuid(self.crm.authenticate(crm_bearer)) # signature, CRM audience and live membership
        claims=_object(crm_bearer.split(".")[1],1536)    # only after existing verifier passed
        actor=claims["sub"]
        if claims.get("tenant_id")!=tenant: raise ValueError("unbound CRM tenant")
        self.check(actor,tenant)
        now=int(self.now())
        h={"alg":"EdDSA","typ":"JWT","kid":self.key_id}
        p={"iss":ISSUER,"aud":AUDIENCE,"sub":actor,"tenant_id":tenant,"scope":SCOPE,
           "iat":now,"nbf":now,"exp":now+TOKEN_TTL,"jti":secrets.token_urlsafe(24)}
        signed=enc(json.dumps(h,separators=(",",":")).encode())+"."+enc(json.dumps(p,separators=(",",":")).encode())
        token=signed+"."+enc(self.signer.sign(signed.encode("ascii")))
        return {"access_token":token,"token_type":"Bearer","expires_in":TOKEN_TTL,"scope":SCOPE}


def attach_founder_session(host:FastAPI,authority:DataCloudPublicVerifier,*,
                           expose_exchange:bool=False,customer_paths:frozenset[str]|None=None):
    """Existing gateway attaches verification only; protected issuer may expose exchange."""
    if not isinstance(authority,DataCloudPublicVerifier):raise ValueError("public verifier missing")
    if expose_exchange and not isinstance(authority,DataCloudFounderAuthority):
        raise ValueError("public gateway cannot expose token issuer")
    supported=frozenset({"/v1/data/usage","/v1/data/search","/v1/data/site-audits"})
    allowed=supported if customer_paths is None else customer_paths
    if not isinstance(allowed,frozenset) or not allowed or not allowed.issubset(supported):
        raise ValueError("unexpected_customer_auth_scope")
    router=APIRouter(prefix="/v1/data/auth",tags=["data-cloud-founder-auth"])
    @router.post("/exchange")
    def exchange(authorization:str|None=Header(default=None)):
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(401,"existing_crm_login_required")
        try:body=authority.exchange(authorization[7:])
        except PermissionError:raise HTTPException(403,"founder_data_cloud_entitlement_required") from None
        except (ValueError,TypeError,KeyError):raise HTTPException(401,"invalid_crm_session") from None
        return JSONResponse(body,headers={"Cache-Control":"no-store","Pragma":"no-cache"})
    if expose_exchange:
        host.include_router(router)
    @host.middleware("http")
    async def verified_session(request:Request,call_next):
        path=request.url.path
        if path in allowed:
            state=request.scope.setdefault("state",{})
            if not isinstance(state,dict):return JSONResponse({"detail":"invalid_state"},status_code=401)
            state.pop("empire_verified_principal",None)
            token=request.headers.get("X-Empire-Data-Session")
            if not token:return JSONResponse({"detail":"data_session_required"},status_code=401,
                                             headers={"Cache-Control":"no-store"})
            try:state["empire_verified_principal"]=authority.verify(token)
            except PermissionError:return JSONResponse({"detail":"data_entitlement_revoked"},status_code=403,
                                                       headers={"Cache-Control":"no-store"})
            except (ValueError,TypeError,KeyError):return JSONResponse({"detail":"invalid_data_session"},status_code=401,
                                                                        headers={"Cache-Control":"no-store"})
        response=await call_next(request)
        if path in allowed or path=="/v1/data/auth/exchange":
            response.headers["Cache-Control"]="no-store"
            response.headers["X-Content-Type-Options"]="nosniff"
        return response
