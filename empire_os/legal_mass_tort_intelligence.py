"""B2B Legal & Mass-Tort intelligence contracts.

The canonical lane observes firms, campaigns, court activity and aggregate
market movement. It deliberately does not target or profile individual
plaintiffs from sensitive medical/legal-distress posts.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class LegalMarketSignal:
    vertical: str
    signal_type: str
    source: str
    source_ref: str
    observed_at: str
    firm_name: str | None = None
    market: str | None = None
    signal_count: int | None = None
    evidence_summary: str | None = None
    individual_consumer_targeting: bool = False
    outreach_authority: str = "none"

    def validate(self) -> None:
        if not self.vertical.strip():
            raise ValueError("vertical required")
        if self.signal_type not in {
            "court_activity",
            "firm_campaign",
            "firm_capacity",
            "search_demand",
            "competitive_visibility",
            "regulatory_case_change",
        }:
            raise ValueError("unsupported legal signal type")
        if self.source not in {
            "courtlistener",
            "state_bar",
            "law_firm_site",
            "search_fabric",
            "public_registry",
        }:
            raise ValueError("unsupported legal signal source")
        if not self.source_ref.strip():
            raise ValueError("source_ref required")
        if not self.observed_at.strip():
            raise ValueError("observed_at required")
        if self.individual_consumer_targeting:
            raise ValueError("individual consumer targeting prohibited")
        if self.signal_count is not None and self.signal_count < 0:
            raise ValueError("signal_count must be nonnegative")

    def as_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)


@dataclass(frozen=True)
class LegalMarketBrief:
    vertical: str
    evidence_count: int
    court_activity_count: int | None
    firm_count: int
    search_signal_count: int
    source_mix: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    opportunity_state: str
    blockers: tuple[str, ...]
    buyer_market: str = "plaintiff_law_firms_and_legal_marketing"
    individual_consumer_targeting: bool = False
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_legal_market_brief(
    vertical: str,
    signals: Iterable[LegalMarketSignal],
) -> LegalMarketBrief:
    rows = tuple(signal for signal in signals if signal.vertical == vertical)
    for row in rows:
        row.validate()

    court_values = [
        row.signal_count
        for row in rows
        if row.signal_type == "court_activity"
        and row.signal_count is not None
    ]
    firms = {
        row.firm_name.strip().lower()
        for row in rows
        if row.firm_name and row.firm_name.strip()
    }
    search_count = sum(
        int(row.signal_count or 1)
        for row in rows
        if row.signal_type in {"search_demand", "competitive_visibility"}
    )
    refs = tuple(dict.fromkeys(
        row.source_ref for row in rows if row.source_ref
    ))
    source_mix = tuple(sorted({row.source for row in rows}))

    blockers: list[str] = []
    if not rows:
        blockers.append("no_market_evidence")
    if not firms:
        blockers.append("no_firm_evidence")
    if not any(row.signal_type == "court_activity" for row in rows):
        blockers.append("no_court_activity_evidence")
    if not any(
        row.signal_type in {"search_demand", "competitive_visibility"}
        for row in rows
    ):
        blockers.append("no_search_market_evidence")

    state = (
        "market_opportunity_observed"
        if len(refs) >= 3 and len(source_mix) >= 2 and not blockers
        else "evidence_incomplete"
    )
    return LegalMarketBrief(
        vertical=vertical,
        evidence_count=len(refs),
        court_activity_count=(
            sum(court_values) if court_values else None
        ),
        firm_count=len(firms),
        search_signal_count=search_count,
        source_mix=source_mix,
        evidence_refs=refs,
        opportunity_state=state,
        blockers=tuple(blockers),
    )


def legacy_mass_tort_agent_status() -> dict[str, Any]:
    return {
        "legacy_agent": "empire_os/agents/mass_tort_agent.py",
        "authoritative": False,
        "retired_reasons": [
            "legacy_root_paths",
            "retired_hub_mutation_endpoint",
            "individual_sensitive_consumer_targeting",
            "count_only_reddit_signal_without_canonical_evidence",
        ],
        "canonical_replacement": "empire_os/legal_mass_tort_intelligence.py",
        "execution_authority": "none",
    }
