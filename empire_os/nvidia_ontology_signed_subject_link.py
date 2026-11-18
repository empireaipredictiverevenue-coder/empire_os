"""Read-only verified NVIDIA OAuth subject to canonical EmpireOS subject link.

Trust is from the existing EmpireOS Ed25519 issuer's pinned public key,
not self-reported email, a bearer claim, request header, or a second identity
registry. Separate signed purpose prevents CRM JWT reuse as link consent.
Original canonical CRM membership is *still checked per request* by the
existing NvidiaTenantAccessPolicy; this link alone grants nothing.
"""
from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping
from uuid import UUID

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from empire_os.nvidia_ontology_tenant_policy import NvidiaTenantDenied, TenantDeployment

PURPOSE="empire-os/nvidia-ontology-tenant-link/v1"
ISSUER="empire-os"
MAX_DOC_BYTES=16384
MAX_LIFETIME_SECONDS=86400
FIELDS=frozenset({
    "purpose","iss","kid","nvidia_issuer","nvidia_sub","empire_sub",
    "tenant_id","deployment_id","issued_at","expires_at","founder_approval_ref",
})


def _strict_object(pairs):
    values={}
    for k,v in pairs:
        if k in values:raise NvidiaTenantDenied("DUPLICATE_LINK_PROPERTY")
        values[k]=v
    return values


def _b64url(value:str)->bytes:
    if not isinstance(value,str) or len(value)!=86 or "=" in value:
        raise NvidiaTenantDenied("INVALID_LINK_SIGNATURE")
    try:
        raw=base64.urlsafe_b64decode(value+"==")
    except Exception as exc:
        raise NvidiaTenantDenied("INVALID_LINK_SIGNATURE") from exc
    if len(raw)!=64 or base64.urlsafe_b64encode(raw).rstrip(b"=").decode()!=value:
        raise NvidiaTenantDenied("INVALID_LINK_SIGNATURE")
    return raw


def _time(value):
    if type(value) is not int or value < 1_700_000_000 or value > 4_000_000_000:
        raise NvidiaTenantDenied("INVALID_LINK_TIME")
    return datetime.fromtimestamp(value,timezone.utc)


def canonical_bytes(payload:dict)->bytes:
    return json.dumps(payload,sort_keys=True,separators=(",",":"),
                      ensure_ascii=True,allow_nan=False).encode()


class ApprovedNvidiaSubjectLink:
    """Verified purpose-limited link, not a primary user credential.

    The existing EmpireOS issuer signs the *exact* payload as a separate
    administrative approval event; the loaded public key is pre-pinned.
    No private key exists in the NVIDIA integration.
    """

    def __init__(
        self,
        artifact_path:Path,
        *,
        pinned_public_keys:Mapping[str,Ed25519PublicKey|bytes],
        deployment:TenantDeployment,
        nvidia_issuer:str,
        now=None,
    ):
        self._resolved=None
        if not isinstance(artifact_path,Path):
            raise NvidiaTenantDenied("VERIFIED_LINK_FILE_REQUIRED")
        if artifact_path.is_symlink() or not artifact_path.is_file():
            raise NvidiaTenantDenied("VERIFIED_LINK_FILE_REQUIRED")
        if artifact_path.stat().st_size>MAX_DOC_BYTES:
            raise NvidiaTenantDenied("LINK_ARTIFACT_TOO_LARGE")
        if artifact_path.stat().st_mode & 0o077:
            raise NvidiaTenantDenied("LINK_ARTIFACT_NOT_PRIVATE")
        try:
            doc=json.loads(artifact_path.read_text(),
                           object_pairs_hook=_strict_object)
        except (ValueError,UnicodeError) as exc:
            raise NvidiaTenantDenied("LINK_ARTIFACT_INVALID") from exc
        if not isinstance(doc,dict) or set(doc)!={"payload","signature"}:
            raise NvidiaTenantDenied("LINK_ARTIFACT_INVALID")
        payload=doc["payload"]
        if not isinstance(payload,dict) or set(payload)!=FIELDS:
            raise NvidiaTenantDenied("LINK_FIELDS_INVALID")
        kid=payload["kid"]
        if not isinstance(kid,str) or len(kid)>64:
            raise NvidiaTenantDenied("UNTRUSTED_LINK_KEY")
        key=pinned_public_keys.get(kid)
        if isinstance(key,bytes):
            if len(key)!=32:raise NvidiaTenantDenied("UNTRUSTED_LINK_KEY")
            key=Ed25519PublicKey.from_public_bytes(key)
        if not isinstance(key,Ed25519PublicKey):
            raise NvidiaTenantDenied("UNTRUSTED_LINK_KEY")
        try:
            key.verify(_b64url(doc["signature"]),
                       PURPOSE.encode()+b"\0"+canonical_bytes(payload))
        except InvalidSignature as exc:
            raise NvidiaTenantDenied("LINK_SIGNATURE_INVALID") from exc
        if (payload["purpose"]!=PURPOSE or payload["iss"]!=ISSUER
            or payload["nvidia_issuer"]!=nvidia_issuer
            or payload["tenant_id"]!=deployment.tenant_id
            or payload["deployment_id"]!=deployment.deployment_id):
            raise NvidiaTenantDenied("LINK_TENANT_OR_ISSUER_MISMATCH")
        if str(UUID(payload["tenant_id"]))!=payload["tenant_id"]:
            raise NvidiaTenantDenied("LINK_TENANT_ID_NOT_CANONICAL")
        for name in ("nvidia_sub","empire_sub","founder_approval_ref"):
            v=payload[name]
            if not isinstance(v,str) or not v or len(v)>256 or v.strip()!=v:
                raise NvidiaTenantDenied("LINK_SUBJECT_OR_APPROVAL_INVALID")
        issued=_time(payload["issued_at"])
        expires=_time(payload["expires_at"])
        if expires<=issued or (expires-issued).total_seconds()>MAX_LIFETIME_SECONDS:
            raise NvidiaTenantDenied("LINK_LIFETIME_INVALID")
        current=(now or (lambda:datetime.now(timezone.utc)))()
        if not isinstance(current,datetime) or current.tzinfo is None:
            raise NvidiaTenantDenied("LINK_CLOCK_INVALID")
        if current<issued or current>=expires:
            raise NvidiaTenantDenied("LINK_NOT_CURRENT")
        self._nvidia_sub=payload["nvidia_sub"]
        self._empire_sub=payload["empire_sub"]
        self._expires=expires
        self._now=now or (lambda:datetime.now(timezone.utc))

    def __call__(self,nvidia_sub:str)->str|None:
        current=self._now()
        if (not isinstance(nvidia_sub,str) or nvidia_sub!=self._nvidia_sub
            or not isinstance(current,datetime) or current.tzinfo is None
            or current>=self._expires):
            return None
        return self._empire_sub
