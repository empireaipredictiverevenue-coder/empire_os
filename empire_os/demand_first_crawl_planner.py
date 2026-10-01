"""Pure demand-first crawl planning; no crawler imports or execution.

Evidence references are supplied by the caller, not independently verified here.
Dispatch readiness describes a proposal, never a grant of execution authority.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from empire_os.demand_registry import DemandRegistryRecord


# Real registration names in lead_sources._import_sources. Keep this explicit:
# loading source adapters or crawler_runner has runtime side effects.
MAX_CANDIDATES_PER_PLAN = 25


ALLOWED_SOURCES = frozenset({
    "permits", "chicago_311", "courtlistener", "reddit", "nyc_hpd",
    "nws_alerts", "overpass", "recc_solar",
})


def _text(value: str, name: str) -> None:
    if (
        not isinstance(value, str)
        or not value.strip()
        or value != value.strip()
        or any(ord(char) < 32 or ord(char) == 127 for char in value)
    ):
        raise ValueError(f"{name} requires nonblank text without control characters")


def _refs(value: tuple[str, ...], name: str, *, required: bool = True) -> None:
    if not isinstance(value, tuple) or (required and not value):
        raise ValueError(f"{name} requires evidence reference tuple")
    for ref in value:
        _text(ref, name)


@dataclass(frozen=True)
class DemandFirstCrawlPlan:
    plan_id: str
    source: str
    niche: str | None
    metro: str | None
    country: str | None
    max_candidates: int
    demand_evidence_refs: tuple[str, ...]
    source_capability_evidence_refs: tuple[str, ...]
    approval_evidence_refs: tuple[str, ...]

    @property
    def dispatch_ready(self) -> bool:
        return bool(self.approval_evidence_refs)

    @property
    def state(self) -> str:
        return (
            "READY_FOR_CRAWLER_DISPATCH" if self.dispatch_ready
            else "REVIEW_REQUIRED"
        )

    @property
    def execution_authority(self) -> str:
        return "none"

    @property
    def crawler_cli_args(self) -> tuple[str, ...]:
        """Arguments for crawler_runner, never a shell command or invocation."""
        if not self.dispatch_ready:
            return ()
        args = ["--source", self.source]
        for name in ("niche", "metro", "country"):
            value = getattr(self, name)
            if value is not None:
                args.extend((f"--{name}", value))
        args.extend(("--max-candidates", str(self.max_candidates)))
        return tuple(args)

    def __post_init__(self) -> None:
        _text(self.plan_id, "plan_id")
        _text(self.source, "source")
        if self.source not in ALLOWED_SOURCES:
            raise ValueError("unsupported or unknown source")
        if (
            type(self.max_candidates) is not int
            or self.max_candidates < 1
            or self.max_candidates > MAX_CANDIDATES_PER_PLAN
        ):
            raise ValueError(
                "max_candidates must be an explicit integer between 1 and 25"
            )
        if not any(value is not None for value in (self.niche, self.metro, self.country)):
            raise ValueError("explicit niche, metro or country target required")
        if self.metro is not None and self.country is not None:
            raise ValueError("metro and country are mutually exclusive")
        for name in ("niche", "metro", "country"):
            value = getattr(self, name)
            if value is not None:
                _text(value, name)
                if value.startswith("-"):
                    raise ValueError(f"{name} cannot be a CLI option")
        if self.country is not None and (
            len(self.country) != 2 or not self.country.isascii()
            or not self.country.isalpha()
        ):
            raise ValueError("country must be a two-letter country code")
        _refs(self.demand_evidence_refs, "demand_evidence_refs")
        _refs(self.source_capability_evidence_refs, "source_capability_evidence_refs")
        _refs(self.approval_evidence_refs, "approval_evidence_refs", required=False)

    def as_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "state": self.state,
            "dispatch_ready": self.dispatch_ready,
            "execution_authority": self.execution_authority,
            "crawler_cli_args": self.crawler_cli_args,
        }


def plan_demand_first_crawl(
    record: DemandRegistryRecord,
    *,
    source: str,
    max_candidates: int,
    source_capability_evidence_refs: tuple[str, ...],
    niche: str | None = None,
    metro: str | None = None,
    country: str | None = None,
    approval_evidence_refs: tuple[str, ...] = (),
) -> DemandFirstCrawlPlan:
    """Plan from a review-ready record and explicit target/capability evidence.

The caller supplies the candidate bound; there is no unbounded default, target
inference, evidence lookup, provider activation or dispatch here.
"""
    record.validate()
    return DemandFirstCrawlPlan(
        plan_id=record.plan.plan_id,
        source=source,
        niche=niche,
        metro=metro,
        country=country,
        max_candidates=max_candidates,
        demand_evidence_refs=record.plan.evidence_refs,
        source_capability_evidence_refs=source_capability_evidence_refs,
        approval_evidence_refs=approval_evidence_refs,
    )
