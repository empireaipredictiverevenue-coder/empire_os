"""V18 actual downstream sink guard for known restricted partner sources.

Called by existing typed dataset freezing and Economic Memory construction.
Denies known programme-sourced data using structured URL/source provenance.
This is NOT a general-purpose consent validator or authenticated licence
issuer. Missing/stripped provenance cannot be independently recovered; the
upstream first-party source custodian must preserve source identity.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from urllib.parse import urlsplit

# V18 production-scoped release: frozen known-domain deny set.
# Deliberately independent of the broader V17/V19 research modules.
# No data-use grant can be inferred from this constant.
DOMAINS=frozenset({
    "astoriacompany.com", "buythecalls.com", "rvnu.com",
})

PURPOSES=frozenset({
    "MODEL_TRAINING_OR_BENCHMARK",
    "ECONOMIC_MEMORY_PARTNER_DATA",
})
IDENTITY_KEYS=frozenset({
    "source_ref","source_refs","source_url","source_urls",
    "source_domain","partner_domain","data_origin_domain",
    "data_origin_url","evidence_refs","evidence_ref",
    "result_evidence_refs","input_evidence_refs",
    "verified_public_page_urls","origin_url",
})
MAX_NODES=100000
MAX_DEPTH=22
MAX_IDENTITIES=10000


class PartnerSinkRightsError(ValueError):
    """No source data is copied into exception text or logs."""


def _domain_for_reference(value: str) -> str | None:
    """Match exact known partner host (or subdomain), never mere substring."""
    raw=value.strip()
    if not raw or len(raw)>1200:
        return None
    if raw.lower().startswith("partner:"):
        raw=raw.split(":",1)[1]
    if "://" not in raw:
        raw="https://"+raw
    try:
        uri=urlsplit(raw)
        if uri.scheme not in ("http","https") or uri.username or uri.password:
            return None
        host=(uri.hostname or "").lower().rstrip(".")
    except ValueError:
        return None
    for domain in DOMAINS:
        if host==domain or host.endswith("."+domain):
            return domain
    return None


def _partner_origins(payload: object)->tuple[str,...]:
    """Bounded traversal of typed origin-bearing fields, never free text.

    Unknown input shape, recursion or malformed provenance causes a HOLD,
    rather than silently waiving rights. Dataset case content is not logged.
    """
    seen=set()
    domains=set()
    stack=[(payload,0,False)]
    nodes=identities=0
    while stack:
        value,depth,is_identity=stack.pop()
        nodes+=1
        if nodes>MAX_NODES or depth>MAX_DEPTH:
            raise PartnerSinkRightsError("BOUNDED_RIGHTS_PROVENANCE_SCAN_REQUIRED")
        if isinstance(value,Mapping):
            marker=(id(value),is_identity)
            if marker in seen:
                continue  # bounded cycle/share; subtree already checked in this context
            seen.add(marker)
            if len(value)>MAX_NODES:
                raise PartnerSinkRightsError("BOUNDED_RIGHTS_PROVENANCE_SCAN_REQUIRED")
            for key,part in value.items():
                if not isinstance(key,str):
                    raise PartnerSinkRightsError("TYPED_PROVENANCE_KEYS_REQUIRED")
                stack.append((part,depth+1,is_identity or key.lower() in IDENTITY_KEYS))
        elif isinstance(value,(list,tuple)):
            marker=(id(value),is_identity)
            if marker in seen:
                continue  # bounded cycle/share; subtree already checked in this context
            seen.add(marker)
            if len(value)>MAX_NODES:
                raise PartnerSinkRightsError("BOUNDED_RIGHTS_PROVENANCE_SCAN_REQUIRED")
            for part in value:
                stack.append((part,depth+1,is_identity))
        elif is_identity:
            identities+=1
            if identities>MAX_IDENTITIES:
                raise PartnerSinkRightsError("BOUNDED_RIGHTS_PROVENANCE_SCAN_REQUIRED")
            if value is not None and not isinstance(value,str):
                raise PartnerSinkRightsError("SOURCE_REFERENCE_MUST_BE_TYPED")
            if isinstance(value,str):
                if len(value)>1200:
                    raise PartnerSinkRightsError("BOUNDED_SOURCE_REFERENCE_REQUIRED")
                domain=_domain_for_reference(value)
                if domain is not None:
                    domains.add(domain)
    return tuple(sorted(domains))


def assert_partner_rights_at_sink(
    payload: object, *, purpose: str,
)->None:
    """Raise BEFORE dataset serialization or memory candidate creation."""
    if purpose not in PURPOSES:
        raise PartnerSinkRightsError("SUPPORTED_PURPOSE_REQUIRED")
    origins=_partner_origins(payload)
    if origins:
        # Restriction cannot be disabled by a caller's self-declared consent
        # boolean or unofficial partner contract. Future grant handling must
        # use independently verified scoped receipts at the source custodian.
        raise PartnerSinkRightsError("KNOWN_PARTNER_DATA_USE_RIGHTS_NOT_GRANTED")
