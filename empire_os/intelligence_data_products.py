"""Generic sellable Intelligence Fabric data-product contracts.

Contracts describe evidence-backed outputs and metering compatibility. They do
not create pricing, entitlements, invoices, payment requests or revenue.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from empire_os.commercial_usage_metering import UsageMode


@dataclass(frozen=True)
class IntelligenceDataProduct:
    key: str
    name: str
    category: str
    source_nodes: tuple[str, ...]
    deliverables: tuple[str, ...]
    delivery_modes: tuple[str, ...]
    required_evidence: tuple[str, ...]
    compatible_usage_modes: tuple[UsageMode, ...]
    commercial_model: str = "terms_required"
    pricing_cents: int | None = None
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["compatible_usage_modes"] = [
            mode.value for mode in self.compatible_usage_modes
        ]
        return data


DATA_PRODUCTS = (
    IntelligenceDataProduct(
        key="opportunity_feed",
        name="Empire Opportunity Feed",
        category="opportunity_intelligence",
        source_nodes=("*",),
        deliverables=(
            "evidence_backed_opportunities",
            "why_now_evidence",
            "entity_provenance",
        ),
        delivery_modes=("api", "export", "dashboard"),
        required_evidence=(
            "canonical_entity",
            "source_provenance",
            "observed_trigger_or_intent",
        ),
        compatible_usage_modes=(
            UsageMode.EVALUATION_SCORE,
            UsageMode.PAY_PER_LEAD,
        ),
    ),
    IntelligenceDataProduct(
        key="market_signal_feed",
        name="Empire Market Signal Feed",
        category="market_intelligence",
        source_nodes=("market_intent", "corporate", "property", "private_capital"),
        deliverables=(
            "observed_signals",
            "source_provenance",
            "freshness_metadata",
        ),
        delivery_modes=("api", "webhook", "export"),
        required_evidence=("observed_signal", "source_provenance", "observed_at"),
        compatible_usage_modes=(UsageMode.HOURLY_INTELLIGENCE,),
    ),
    IntelligenceDataProduct(
        key="spatial_physical_intelligence",
        name="Empire Spatial & Physical Intelligence",
        category="spatial_physical_intelligence",
        source_nodes=("volumetric", "natural_physical", "property", "home_services", "solar_energy", "hvac_climate"),
        deliverables=(
            "evidence_backed_3d_observations",
            "physical_condition_observations",
            "modeled_physical_opportunities",
            "spatial_change_evidence",
        ),
        delivery_modes=("api", "export", "dashboard", "digital_twin"),
        required_evidence=(
            "canonical_subject",
            "source_provenance",
            "observed_at",
            "spatial_or_physical_evidence_ref",
        ),
        compatible_usage_modes=(
            UsageMode.EVALUATION_SCORE,
            UsageMode.HOURLY_INTELLIGENCE,
        ),
    ),
    IntelligenceDataProduct(
        key="forecast_snapshot",
        name="Empire Forecast Snapshot",
        category="predictive_intelligence",
        source_nodes=("*",),
        deliverables=(
            "directional_forecast",
            "trend_regime",
            "evidence_confidence",
            "observation_count",
        ),
        delivery_modes=("api", "dashboard", "report"),
        required_evidence=(
            "canonical_observed_time_series",
            "minimum_forecast_samples",
            "model_version",
        ),
        compatible_usage_modes=(
            UsageMode.EVALUATION_SCORE,
            UsageMode.HOURLY_INTELLIGENCE,
        ),
    ),
    IntelligenceDataProduct(
        key="entity_graph_export",
        name="Empire Entity Graph Export",
        category="entity_intelligence",
        source_nodes=("*",),
        deliverables=(
            "canonical_entities",
            "relationships",
            "provenance",
            "temporal_evidence",
        ),
        delivery_modes=("api", "export"),
        required_evidence=("canonical_entity", "provenance"),
        compatible_usage_modes=(UsageMode.HOURLY_INTELLIGENCE,),
    ),
)


def data_product_catalog() -> list[dict[str, Any]]:
    return [product.as_dict() for product in DATA_PRODUCTS]


def get_data_product(key: str) -> IntelligenceDataProduct | None:
    normalized = str(key or "").strip().lower()
    return next((p for p in DATA_PRODUCTS if p.key == normalized), None)
