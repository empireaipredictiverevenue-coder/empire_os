from __future__ import annotations

from typing import Any


NICHE_FAMILIES: dict[str, set[str]] = {
    "roofing": {
        "roofing",
        "roof repair",
        "roof_repair",
        "residential roofing",
        "residential_roofing",
        "commercial roofing",
        "commercial_roofing",
        "roofing restoration",
        "roofing_restoration",
    },
    "restoration": {
        "restoration",
        "water damage",
        "water_damage",
        "water mitigation",
        "water_mitigation",
        "roofing restoration",
        "roofing_restoration",
    },
    "solar": {
        "solar",
        "commercial solar",
        "commercial_solar",
    },
    "hvac": {
        "hvac",
    },
    "general contractor": {
        "general contractor",
        "general_contractor",
    },
    "weight loss": {
        "weight loss",
        "weight_loss",
    },
    "landscaping": {
        "landscaping",
    },
    "legal": {
        "legal",
    },
    "insurance": {
        "insurance",
        "auto insurance",
        "auto_insurance",
    },
    "debt": {
        "debt",
        "debt relief",
        "debt_relief",
    },
    "cleaning": {
        "cleaning",
    },
    "gutter": {
        "gutter",
    },
    "medical claims": {
        "medical claims",
        "medical_claims",
    },
    "consumer cpa": {
        "consumer cpa",
        "consumer_cpa",
    },
    "medicare": {
        "medicare",
    },
    "mortgage": {
        "mortgage",
    },
    "logistics": {
        "logistics",
    },
    "plumbing": {
        "plumbing",
    },
}


def normalise(value: Any) -> str:
    return " ".join(
        str(value or "").lower().strip().replace("_", " ").split()
    )


def niche_family(value: Any) -> str:
    value_n = normalise(value)

    for family, aliases in NICHE_FAMILIES.items():
        if value_n in {normalise(x) for x in aliases}:
            return family

    return value_n


def metro_key(value: Any) -> str:
    return normalise(value)
