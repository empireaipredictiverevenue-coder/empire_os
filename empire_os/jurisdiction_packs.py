"""Jurisdiction-pack scaffold for global acquisition.

This is governance configuration, not legal advice. It deliberately records
review requirements and known locale facts without granting outreach authority.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class JurisdictionPack:
    country_code: str
    currency: str
    default_language: str
    privacy_review: str
    outreach_review: str
    retention_review: str
    commercial_terms_review: str
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


PACKS: dict[str, JurisdictionPack] = {
    "GB": JurisdictionPack("GB", "GBP", "en-GB", "required", "required", "required", "required"),
    "CA": JurisdictionPack("CA", "CAD", "en-CA", "required", "required", "required", "required"),
    "AU": JurisdictionPack("AU", "AUD", "en-AU", "required", "required", "required", "required"),
    "IE": JurisdictionPack("IE", "EUR", "en-IE", "required", "required", "required", "required"),
    "NZ": JurisdictionPack("NZ", "NZD", "en-NZ", "required", "required", "required", "required"),
    "DE": JurisdictionPack("DE", "EUR", "de-DE", "required", "required", "required", "required"),
    "FR": JurisdictionPack("FR", "EUR", "fr-FR", "required", "required", "required", "required"),
    "ES": JurisdictionPack("ES", "EUR", "es-ES", "required", "required", "required", "required"),
    "IT": JurisdictionPack("IT", "EUR", "it-IT", "required", "required", "required", "required"),
    "NL": JurisdictionPack("NL", "EUR", "nl-NL", "required", "required", "required", "required"),
    "BE": JurisdictionPack("BE", "EUR", "nl-BE", "required", "required", "required", "required"),
    "PT": JurisdictionPack("PT", "EUR", "pt-PT", "required", "required", "required", "required"),
}


def jurisdiction_pack(country_code: str) -> JurisdictionPack:
    code = str(country_code or "").upper()
    if code not in PACKS:
        raise KeyError(f"jurisdiction pack not configured: {code}")
    return PACKS[code]
