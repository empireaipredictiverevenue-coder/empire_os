"""Normalized feature extraction for Omega 2.0.

This layer converts messy CRM/lane/inbound records into a stable,
model-friendly feature contract.

It performs no persistence and has no database dependencies.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class LeadFeatures:
    """Normalized, model-independent lead features."""

    has_identity: bool = False
    has_business_name: bool = False
    has_contact_name: bool = False

    has_phone: bool = False
    has_email: bool = False
    has_website: bool = False

    has_location: bool = False
    has_market: bool = False
    has_description: bool = False

    contactability: float = 0.0
    data_completeness: float = 0.0

    legacy_omega_score: float = 0.0
    legacy_omega_tier: str = "bronze"

    status: str = ""
    source: str = ""
    niche: str = ""
    sub_niche: str = ""
    metro: str = ""

    text_length: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _present(value: Any) -> bool:
    return bool(str(value or "").strip())



def _text_length(lead: Mapping[str, Any]) -> int:
    fields = (
        "business_name",
        "contact_name",
        "niche",
        "sub_niche",
        "notes",
        "details",
    )
    return sum(len(str(lead.get(field) or "").strip()) for field in fields)


def _legacy_score(lead: Mapping[str, Any]) -> float:
    try:
        value = float(lead.get("omega_score") or 0)
    except (TypeError, ValueError):
        return 0.0

    return max(0.0, min(100.0, value))


def _legacy_tier(score: float) -> str:
    if score >= 90:
        return "platinum"
    if score >= 70:
        return "gold"
    if score >= 40:
        return "silver"
    return "bronze"


def extract_features(lead: Mapping[str, Any]) -> LeadFeatures:
    """Extract normalized features without mutating the source record."""

    business_name = _present(lead.get("business_name"))
    contact_name = _present(lead.get("contact_name"))
    phone = _present(lead.get("phone"))
    email = _present(lead.get("email"))
    website = _present(lead.get("website"))

    location = any(
        _present(lead.get(field))
        for field in ("city", "state", "zip", "metro", "street")
    )

    market = any(
        _present(lead.get(field))
        for field in ("niche", "sub_niche")
    )

    text_length = _text_length(lead)
    description = text_length >= 25

    identity = business_name or contact_name

    # Contactability is deliberately simple and interpretable.
    contactability = (
        (0.45 if phone else 0.0)
        + (0.35 if email else 0.0)
        + (0.20 if website else 0.0)
    )

    completeness_fields = (
        identity,
        phone,
        email,
        website,
        location,
        market,
        description,
    )

    data_completeness = sum(
        1 for present in completeness_fields if present
    ) / len(completeness_fields)

    legacy_score = _legacy_score(lead)

    return LeadFeatures(
        has_identity=identity,
        has_business_name=business_name,
        has_contact_name=contact_name,
        has_phone=phone,
        has_email=email,
        has_website=website,
        has_location=location,
        has_market=market,
        has_description=description,
        contactability=round(contactability, 4),
        data_completeness=round(data_completeness, 4),
        legacy_omega_score=round(legacy_score, 2),
        legacy_omega_tier=_legacy_tier(legacy_score),
        status=str(lead.get("status") or "").strip().lower(),
        source=str(lead.get("source") or "").strip(),
        niche=str(lead.get("niche") or "").strip(),
        sub_niche=str(lead.get("sub_niche") or "").strip(),
        metro=str(lead.get("metro") or "").strip(),
        text_length=text_length,
    )
