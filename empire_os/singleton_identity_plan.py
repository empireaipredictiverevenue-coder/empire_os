"""Fail-closed identity planning for evidence-backed singleton prospects.

Planning only. This module never reads credentials, performs network calls, or
writes to canonical storage. It exists for singleton prospects that cannot be
resolved by the bulk duplicate-cluster resolver but have strong direct
acquisition evidence corroborated by a verified first-party site.
"""
from __future__ import annotations

import re
import urllib.parse
import uuid
from typing import Any, Mapping


SINGLETON_ENTITY_NAMESPACE = uuid.UUID(
    "7e54100e-2be1-4ba9-9829-5c019d10fbe8"
)


class SingletonIdentityPlanError(RuntimeError):
    """Evidence cannot support a safe singleton identity proposal."""


def _text(value: Any) -> str:
    return str(value or "").strip()


def _norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", _text(value).lower()).strip()


def _phone(value: Any) -> str:
    digits = re.sub(r"\D", "", _text(value))
    return digits[-10:] if len(digits) >= 10 else digits


def _domain(value: Any) -> str:
    text = _text(value)
    if not text:
        return ""
    if "://" not in text:
        text = "https://" + text
    try:
        host = (urllib.parse.urlparse(text).hostname or "").lower().strip(".")
    except Exception:
        return ""
    return host[4:] if host.startswith("www.") else host


def _evidence_item(
    enrichment: Mapping[str, Any],
    source: str,
) -> Mapping[str, Any] | None:
    evidence = enrichment.get("evidence")
    if not isinstance(evidence, list):
        return None
    for item in evidence:
        if isinstance(item, Mapping) and item.get("source") == source:
            return item
    return None


def _raw_acquisition(
    acquisition: Mapping[str, Any],
) -> Mapping[str, Any]:
    evidence = acquisition.get("evidence")
    if not isinstance(evidence, Mapping):
        raise SingletonIdentityPlanError("acquisition evidence missing")
    raw = evidence.get("raw")
    if not isinstance(raw, Mapping):
        raise SingletonIdentityPlanError("acquisition raw evidence missing")
    return raw


def _quality(acquisition: Mapping[str, Any]) -> Mapping[str, Any]:
    evidence = acquisition.get("evidence")
    if not isinstance(evidence, Mapping):
        raise SingletonIdentityPlanError("acquisition evidence missing")
    quality = evidence.get("quality")
    if not isinstance(quality, Mapping):
        raise SingletonIdentityPlanError("acquisition quality missing")
    return quality


def build_singleton_identity_plan(
    *,
    prospect: Mapping[str, Any],
    acquisition: Mapping[str, Any],
    enrichment: Mapping[str, Any],
) -> dict[str, Any]:
    """Return a deterministic proposal only when hard identity evidence agrees."""
    prospect_id = _text(prospect.get("id"))
    if not prospect_id:
        raise SingletonIdentityPlanError("prospect id missing")
    try:
        uuid.UUID(prospect_id)
    except ValueError as exc:
        raise SingletonIdentityPlanError("prospect id invalid") from exc

    acquisition_pid = _text(acquisition.get("prospect_id"))
    if acquisition_pid and acquisition_pid != prospect_id:
        raise SingletonIdentityPlanError("acquisition prospect mismatch")

    quality = _quality(acquisition)
    if quality.get("accepted") is not True:
        raise SingletonIdentityPlanError("acquisition quality not accepted")
    if _text(quality.get("source_role")) != "identity_or_direct":
        raise SingletonIdentityPlanError(
            "acquisition source is not identity_or_direct"
        )
    try:
        source_confidence = float(quality.get("confidence"))
    except (TypeError, ValueError) as exc:
        raise SingletonIdentityPlanError(
            "acquisition confidence invalid"
        ) from exc
    if source_confidence < 90.0:
        raise SingletonIdentityPlanError(
            "acquisition confidence below singleton floor"
        )

    raw = _raw_acquisition(acquisition)
    tags = raw.get("osm_tags")
    if not isinstance(tags, Mapping):
        tags = {}

    source_name = _text(tags.get("name") or raw.get("name"))
    prospect_name = _text(prospect.get("business_name"))
    if not source_name or _norm(source_name) != _norm(prospect_name):
        raise SingletonIdentityPlanError("business name mismatch")

    source_phone = _phone(tags.get("phone") or raw.get("phone"))
    prospect_phone = _phone(prospect.get("phone"))
    if not source_phone or not prospect_phone or source_phone != prospect_phone:
        raise SingletonIdentityPlanError("phone mismatch")

    acquisition_website = _text(
        raw.get("business_website")
        or tags.get("website")
    )
    verified_website = _text(
        (enrichment.get("fields") or {}).get("website")
        if isinstance(enrichment.get("fields"), Mapping)
        else ""
    )
    if (
        not acquisition_website
        or not verified_website
        or _domain(acquisition_website) != _domain(verified_website)
    ):
        raise SingletonIdentityPlanError("verified website mismatch")

    identity = _evidence_item(enrichment, "identity_guard")
    if not identity or identity.get("accepted") is not True:
        raise SingletonIdentityPlanError("identity guard did not accept site")
    if identity.get("source_phone_match") is not True:
        raise SingletonIdentityPlanError(
            "verified site did not corroborate source phone"
        )

    acquisition_site = _evidence_item(
        enrichment,
        "acquisition_evidence",
    )
    if (
        not acquisition_site
        or acquisition_site.get("accepted") is not True
    ):
        raise SingletonIdentityPlanError(
            "acquisition website was not verifier accepted"
        )

    entity_key = "|".join(
        (
            _norm(prospect_name),
            _domain(verified_website),
            prospect_phone,
        )
    )
    entity_id = str(
        uuid.uuid5(SINGLETON_ENTITY_NAMESPACE, entity_key)
    )

    return {
        "schema_version": "singleton_identity_plan.v1",
        "dry_run": True,
        "writes_performed": 0,
        "prospect_id": prospect_id,
        "entity_id_candidate": entity_id,
        "resolution_state": "evidence_resolved_candidate",
        "promotion_ready": False,
        "requires_explicit_production_approval": True,
        "canonical_name_candidate": prospect_name,
        "canonical_niche_candidate": _text(prospect.get("niche")),
        "canonical_metro_candidate": _text(prospect.get("metro")),
        "canonical_phone_candidate": _text(prospect.get("phone")),
        "canonical_website_candidate": verified_website,
        "association_confidence": 1.0,
        "confidence_basis": (
            "exact acquisition name + exact phone + verified first-party "
            "domain + identity-guard phone corroboration"
        ),
        "evidence_assertions": [
            "accepted_identity_or_direct_acquisition",
            "acquisition_confidence_gte_90",
            "exact_normalized_business_name",
            "exact_normalized_phone",
            "acquisition_domain_equals_verified_domain",
            "identity_guard_accepted",
            "verified_site_phone_matches_source_phone",
        ],
        "source": {
            "acquisition_source": _text(acquisition.get("source")),
            "acquisition_source_url": _text(acquisition.get("source_url")),
            "verified_domain": _domain(verified_website),
        },
    }
