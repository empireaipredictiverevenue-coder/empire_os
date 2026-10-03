"""Exact-SKU Solar Opportunity Map pre-market readiness.

This classifies configuration/source/artifact readiness only. It never upgrades
a Solar SKU to campaign-ready without retained exact-product live smoke evidence.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import json
from typing import Any

from empire_os.market_pricing import SOLAR_OPPORTUNITY_MAP_PRICES
from empire_os.source_intelligence import source_plan


_SOLAR_SPECIFIC = {
    "GB": {"gb_recc_solar", "gb_mcs", "gb_trustmark"},
    "AU": {"au_saa_solar"},
    "IE": {"ie_seai_solar"},
    "DE": {"de_mastr"},
    "FR": {"fr_france_renov_rge"},
}


@dataclass(frozen=True)
class SolarSkuPremarketStatus:
    product_code: str
    country_code: str
    source_pack_configured: bool
    solar_specific_source_configured: bool
    selected_source: str | None
    artifact_count: int
    artifact_ready_count: int
    exact_product_artifact_count: int
    retained_source_provenance_verified: bool
    campaign_smoke_ready: bool
    blockers: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _artifact_status(
    *,
    root: Path,
    product_code: str,
    country_code: str,
) -> tuple[int, int, int]:
    total = ready = exact = 0
    for path in sorted((root / "runtime" / "solar_opportunity_maps").glob("*.json")):
        if path.name == "economics_latest.json":
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        offer = payload.get("offer")
        if not isinstance(offer, dict):
            continue
        if str(offer.get("country_code") or "").upper() != country_code:
            continue
        total += 1
        if payload.get("artifact_ready") is True:
            ready += 1
        if (
            str(offer.get("product_code") or "") == product_code
            and payload.get("artifact_ready") is True
        ):
            exact += 1
    return total, ready, exact


def build_solar_sku_premarket_status(
    *,
    repo_root: str | Path = "/srv/empire_os",
    retained_source_provenance: dict[str, bool] | None = None,
) -> tuple[SolarSkuPremarketStatus, ...]:
    root = Path(repo_root)
    provenance = {
        str(k).upper(): bool(v)
        for k, v in dict(retained_source_provenance or {}).items()
    }
    rows: list[SolarSkuPremarketStatus] = []

    for country, price in SOLAR_OPPORTUNITY_MAP_PRICES.items():
        product_code = price.product_code
        blockers: list[str] = []
        selected = None
        source_pack = True
        solar_specific = False
        try:
            plan = source_plan(country, "solar")
            selected = str(plan.get("selected_source") or "").strip() or None
            solar_specific = bool(
                selected
                and selected in _SOLAR_SPECIFIC.get(country, set())
            )
        except KeyError:
            source_pack = False
            blockers.append("source_pack_missing")

        if source_pack and not solar_specific:
            blockers.append("solar_specific_source_missing")

        total, ready, exact = _artifact_status(
            root=root,
            product_code=product_code,
            country_code=country,
        )
        if exact < 1:
            blockers.append("exact_product_artifact_missing")

        provenance_ok = provenance.get(country) is True
        if not provenance_ok:
            blockers.append("retained_source_provenance_missing")

        campaign_ready = not blockers
        rows.append(
            SolarSkuPremarketStatus(
                product_code=product_code,
                country_code=country,
                source_pack_configured=source_pack,
                solar_specific_source_configured=solar_specific,
                selected_source=selected,
                artifact_count=total,
                artifact_ready_count=ready,
                exact_product_artifact_count=exact,
                retained_source_provenance_verified=provenance_ok,
                campaign_smoke_ready=campaign_ready,
                blockers=tuple(dict.fromkeys(blockers)),
            )
        )

    return tuple(rows)
