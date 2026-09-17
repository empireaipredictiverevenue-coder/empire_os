from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Callable

from empire_os.niche_taxonomy import (
    metro_key,
    niche_family,
    normalise,
)

MIN_QUALIFICATION_SCORE = 50.0
ALLOCATABLE_TIERS = frozenset({"hot", "warm"})
INACTIVE_BUYER_STATUSES = frozenset({"inactive", "disabled"})
BUYER_PAGE_SIZE = 1000
MAX_RPC_CANDIDATES = 20
ALLOCATION_VERSION = "v1"
ALLOCATION_ACTOR = "empire_os.buyer_allocation_v1"


class BuyerAllocationError(RuntimeError):
    pass


@dataclass(frozen=True)
class BuyerMatch:
    buyer_id: str
    buyer_name: str
    niche_family: str
    metro: str
    remaining_capacity: int
    priority: float
    observed_rate: float | None
    exact_niche: bool
    exact_metro: bool
    match_score: float
    def to_rpc_candidate(self) -> dict[str, Any]:
        return asdict(self)


def _nonnegative_int(value: Any) -> int:
    try:
        return max(int(value or 0), 0)
    except (TypeError, ValueError):
        return 0


def _float_or_none(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _priority(value: Any) -> float:
    try:
        return max(float(value or 0), 0.0)
    except (TypeError, ValueError):
        return 0.0


def _buyer_rate(row: dict[str, Any]) -> float | None:
    value = row.get("per_lead_rate")
    if value in (None, ""):
        value = row.get("base_payout")
    return _float_or_none(value)

def qualification_decision(
    qualification: dict[str, Any] | None,
) -> tuple[bool, str]:
    if not isinstance(qualification, dict):
        return False, "missing_qualification"

    status = normalise(qualification.get("status"))
    tier = normalise(qualification.get("tier"))

    try:
        score = float(qualification.get("score") or 0)
    except (TypeError, ValueError):
        score = 0.0

    if status != "scored":
        return False, "qualification_not_scored"

    if tier not in ALLOCATABLE_TIERS:
        return False, "qualification_tier_not_allocatable"

    if score < MIN_QUALIFICATION_SCORE:
        return False, "qualification_score_below_floor"

    return True, "qualified"


def allocation_key(prospect_id: str) -> str:
    prospect_id = str(prospect_id or "").strip()
    if not prospect_id:
        raise BuyerAllocationError("prospect id is required")
    return f"exclusive:{ALLOCATION_VERSION}:{prospect_id}"

def _prospect_market(
    prospect: dict[str, Any],
) -> tuple[str, str, str]:
    prospect_id = str(prospect.get("id") or "").strip()
    family = niche_family(prospect.get("niche"))
    metro = metro_key(prospect.get("metro"))

    if not prospect_id:
        raise BuyerAllocationError("prospect id is required")
    if not family:
        raise BuyerAllocationError("prospect niche is required")
    if not metro:
        raise BuyerAllocationError("prospect metro is required")

    return prospect_id, family, metro


def _buyer_match(
    prospect_family: str,
    prospect_metro: str,
    row: dict[str, Any],
) -> BuyerMatch | None:
    buyer_id = str(row.get("id") or "").strip()
    if not buyer_id:
        return None

    status = normalise(row.get("status"))
    if not bool(row.get("is_active")):
        return None
    if status in INACTIVE_BUYER_STATUSES:
        return None

    buyer_niche = normalise(row.get("niche"))
    buyer_family = niche_family(buyer_niche) if buyer_niche else ""
    buyer_metro = metro_key(row.get("metro"))

    niche_match = (
        not buyer_niche
        or buyer_family == prospect_family
    )
    metro_match = (
        not buyer_metro
        or buyer_metro == prospect_metro
    )

    if not niche_match or not metro_match:
        return None

    daily_cap = _nonnegative_int(row.get("daily_cap"))
    calls_today = _nonnegative_int(row.get("calls_today"))
    remaining = max(daily_cap - calls_today, 0)

    if remaining <= 0:
        return None

    exact_niche = bool(buyer_niche) and buyer_family == prospect_family
    exact_metro = bool(buyer_metro) and buyer_metro == prospect_metro
    priority = _priority(row.get("priority"))

    score = 0.0
    score += 40.0 if exact_niche else 20.0
    score += 30.0 if exact_metro else 15.0
    score += min(priority, 100.0) * 0.20
    score += min(remaining, 10) * 1.0

    return BuyerMatch(
        buyer_id=buyer_id,
        buyer_name=str(row.get("buyer_name") or "").strip(),
        niche_family=buyer_family,
        metro=buyer_metro,
        remaining_capacity=remaining,
        priority=priority,
        observed_rate=_buyer_rate(row),
        exact_niche=exact_niche,
        exact_metro=exact_metro,
        match_score=round(min(score, 100.0), 4),
    )

def rank_buyers(
    prospect: dict[str, Any],
    qualification: dict[str, Any] | None,
    buyers: list[dict[str, Any]],
    *,
    limit: int = MAX_RPC_CANDIDATES,
) -> list[BuyerMatch]:
    _, family, metro = _prospect_market(prospect)

    allowed, _ = qualification_decision(qualification)
    if not allowed:
        return []

    if limit < 1:
        raise BuyerAllocationError("candidate limit must be positive")

    matches: list[BuyerMatch] = []
    seen: set[str] = set()

    for row in buyers:
        if not isinstance(row, dict):
            continue

        match = _buyer_match(family, metro, row)
        if match is None or match.buyer_id in seen:
            continue

        seen.add(match.buyer_id)
        matches.append(match)

    matches.sort(
        key=lambda item: (
            -item.match_score,
            -item.priority,
            -item.remaining_capacity,
            -(item.observed_rate or 0.0),
            item.buyer_id,
        )
    )

    return matches[:limit]

def plan_allocation(
    prospect: dict[str, Any],
    qualification: dict[str, Any] | None,
    buyers: list[dict[str, Any]],
) -> dict[str, Any]:
    prospect_id, family, metro = _prospect_market(prospect)
    allowed, reason = qualification_decision(qualification)

    if not allowed:
        return {
            "decision": "not_qualified",
            "reason": reason,
            "prospect_id": prospect_id,
            "niche_family": family,
            "metro": metro,
            "candidates": [],
        }

    matches = rank_buyers(prospect, qualification, buyers)

    if not matches:
        return {
            "decision": "overflow_no_capacity",
            "reason": "no_eligible_buyer_capacity",
            "prospect_id": prospect_id,
            "niche_family": family,
            "metro": metro,
            "candidates": [],
        }

    return {
        "decision": "ready",
        "prospect_id": prospect_id,
        "niche_family": family,
        "metro": metro,
        "allocation_key": allocation_key(prospect_id),
        "candidates": [item.to_rpc_candidate() for item in matches],
    }

Reader = Callable[[str, dict[str, str]], Any]
Allocator = Callable[[dict[str, Any]], Any]


def fetch_latest_qualification(
    reader: Reader,
    prospect_id: str,
) -> dict[str, Any] | None:
    rows = reader(
        "/rest/v1/prospect_qualifications",
        {
            "select": "prospect_id,score,tier,status,scoring_engine,scoring_version,scored_at",
            "prospect_id": f"eq.{prospect_id}",
            "scoring_engine": "eq.empire_os.lead_scoring",
            "scoring_version": "eq.v1",
            "order": "scored_at.desc",
            "limit": "1",
        },
    )

    if not isinstance(rows, list):
        raise BuyerAllocationError("qualification reader returned invalid payload")

    if not rows:
        return None

    row = rows[0]
    if not isinstance(row, dict):
        raise BuyerAllocationError("qualification reader returned invalid row")
    return row


def fetch_buyer_rows(
    reader: Reader,
    *,
    page_size: int = BUYER_PAGE_SIZE,
) -> list[dict[str, Any]]:
    if page_size < 1:
        raise BuyerAllocationError("buyer page size must be positive")

    buyers: list[dict[str, Any]] = []
    offset = 0
    while True:
        batch = reader(
            "/rest/v1/buyers",
            {
                "select": (
                    "id,buyer_name,niche,metro,is_active,status,"
                    "daily_cap,calls_today,base_payout,per_lead_rate,priority"
                ),
                "limit": str(page_size),
                "offset": str(offset),
            },
        )

        if not isinstance(batch, list):
            raise BuyerAllocationError("buyer reader returned invalid payload")

        buyers.extend(
            row for row in batch
            if isinstance(row, dict)
        )

        if len(batch) < page_size:
            break

        offset += page_size

    return buyers


def allocate_owned_prospect(
    prospect: dict[str, Any],
    reader: Reader,
    allocator: Allocator,
) -> dict[str, Any]:
    prospect_id, _, _ = _prospect_market(prospect)
    qualification = fetch_latest_qualification(reader, prospect_id)
    buyers = fetch_buyer_rows(reader)
    plan = plan_allocation(prospect, qualification, buyers)

    if plan["decision"] != "ready":
        return plan

    result = allocator(
        {
            "p_prospect_id": plan["prospect_id"],
            "p_allocation_key": plan["allocation_key"],
            "p_candidates": plan["candidates"],
            "p_actor": ALLOCATION_ACTOR,
        }
    )

    if not isinstance(result, dict):
        raise BuyerAllocationError("allocator returned invalid payload")

    decision = str(result.get("decision") or "")
    if decision not in {
        "allocated",
        "existing_allocation",
        "overflow_no_capacity",
    }:
        raise BuyerAllocationError(
            f"allocator returned invalid decision: {decision or '<empty>'}"
        )

    return {
        **result,
        "planned_candidate_count": len(plan["candidates"]),
        "allocation_key": plan["allocation_key"],
    }
