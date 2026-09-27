"""Migration-wave planning for Empire Data Cloud.

Schema compatibility is handled across the full canonical schema, while data
movement is prioritized by operational criticality and observed production use.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class MigrationWave(str, Enum):
    CONTROL = "control"
    CORE_TRUTH = "core_truth"
    COMMERCIAL = "commercial"
    INTELLIGENCE = "intelligence"
    LEGACY = "legacy"


CONTROL_TABLES = frozenset({
    "organizations",
    "outbound_suppressions",
    "governance_limits",
    "schema_migrations",
    "astra_observer_tokens",
})

CORE_TRUTH_TABLES = frozenset({
    "prospects",
    "business_entities",
    "prospect_entity_links",
    "prospect_identity_claims",
    "prospect_acquisitions",
    "prospect_qualifications",
    "commercial_events",
})

COMMERCIAL_TABLES = frozenset({
    "commercial_products",
    "commercial_product_versions",
    "commercial_product_catalog_events",
    "commercial_evidence_registry",
    "gtm_opportunities",
    "gtm_jobs",
    "buyer_scout_candidates",
    "buyer_candidate_reviews",
    "buyer_candidate_review_events",
    "outbound_intents",
    "outbound_events",
    "outbound_replies",
    "buyer_commercial_evidence",
    "commercial_terms_reviews",
    "commercial_terms_events",
    "fulfilment_orders",
    "bsc_payment_requests",
    "bsc_payment_evidence",
    "bsc_payment_request_events",
    "bsc_escrow_agreements",
    "bsc_escrow_evidence",
})

INTELLIGENCE_TABLES = frozenset({
    "intelligence_sources",
    "intelligence_people",
    "intelligence_employment",
    "intelligence_contact_points",
    "intelligence_facts",
    "intelligence_signals",
    "intelligence_segments",
    "intelligence_segment_membership",
    "intelligence_scores",
    "intelligence_offer_fit",
    "intelligence_outcomes",
})


@dataclass(frozen=True)
class TableMigrationPlan:
    table_name: str
    wave: MigrationWave
    preserve_schema: bool = True
    copy_data: bool = True
    verify_content: bool = True


def classify_table(table_name: str) -> MigrationWave:
    name = table_name.removeprefix("public.")
    if name in CONTROL_TABLES:
        return MigrationWave.CONTROL
    if name in CORE_TRUTH_TABLES:
        return MigrationWave.CORE_TRUTH
    if name in COMMERCIAL_TABLES:
        return MigrationWave.COMMERCIAL
    if name in INTELLIGENCE_TABLES:
        return MigrationWave.INTELLIGENCE
    return MigrationWave.LEGACY


def build_wave_plan(table_names: Iterable[str]) -> tuple[TableMigrationPlan, ...]:
    return tuple(
        TableMigrationPlan(
            table_name=name.removeprefix("public."),
            wave=classify_table(name),
        )
        for name in sorted({str(name) for name in table_names if str(name).strip()})
    )
