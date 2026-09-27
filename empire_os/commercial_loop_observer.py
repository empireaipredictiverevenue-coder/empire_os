"""OBSERVE-only commercial loop blocker detection.

Modern recovery of the useful North Mini / loop-closure concept. The observer
never sends, allocates, charges, recognizes revenue, or fabricates missing
commercial evidence.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


STAGE_ORDER = (
    "real_acquisition",
    "qualification_v2",
    "omega_projection",
    "buyer_candidate_approved",
    "outbound_authorized",
    "outbound_sent",
    "buyer_conversation",
    "commercial_terms",
    "verified_buyer_capacity",
    "inventory_allocation",
    "bsc_payment_request",
    "bsc_usdt_payment",
    "fulfilment",
    "commercial_outcome",
    "recognized_revenue",
    "realized_gross_profit",
    "learning_feedback",
)


@dataclass(frozen=True)
class CommercialLoopObservation:
    stage: str
    observed: bool | None
    evidence_ref: str | None = None
    detail: str | None = None


@dataclass(frozen=True)
class CommercialLoopStatus:
    stages: tuple[CommercialLoopObservation, ...]
    highest_priority_blocker: str | None
    blocker_state: str | None
    loop_complete: bool
    mode: str = "OBSERVE"
    execution_authority: str = "none"
    side_effects: str = "none"
    allocation_execution: bool = False
    outbound_execution: bool = False
    payment_execution: bool = False
    revenue_mutation: bool = False
    model_weight_mutation: bool = False

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["stages"] = [asdict(item) for item in self.stages]
        return data


def assess_commercial_loop(
    observations: dict[str, CommercialLoopObservation],
) -> CommercialLoopStatus:
    unknown_names = set(observations) - set(STAGE_ORDER)
    if unknown_names:
        raise ValueError(
            "unsupported commercial loop stage(s): "
            + ", ".join(sorted(unknown_names))
        )

    ordered: list[CommercialLoopObservation] = []
    blocker = None
    blocker_state = None
    for stage in STAGE_ORDER:
        item = observations.get(stage)
        if item is None:
            item = CommercialLoopObservation(
                stage=stage,
                observed=None,
                detail="stage evidence not loaded",
            )
        if item.stage != stage:
            raise ValueError(
                f"commercial loop observation stage mismatch: {stage}"
            )
        ordered.append(item)
        if blocker is None and item.observed is not True:
            blocker = stage
            blocker_state = (
                "blocked" if item.observed is False else "unknown"
            )

    return CommercialLoopStatus(
        stages=tuple(ordered),
        highest_priority_blocker=blocker,
        blocker_state=blocker_state,
        loop_complete=blocker is None,
    )



Reader = Callable[[str, dict[str, str]], Any]


def _reader_rows(
    reader: Reader,
    path: str,
    params: dict[str, str],
) -> list[dict[str, Any]]:
    rows = reader(path, params)
    if not isinstance(rows, list):
        raise ValueError(f"canonical reader returned invalid rows for {path}")
    return [row for row in rows if isinstance(row, dict)]


def fetch_canonical_commercial_observations(
    reader: Reader,
    *,
    now: datetime,
) -> dict[str, CommercialLoopObservation]:
    """Read canonical downstream evidence without mutating commercial state."""
    if now.tzinfo is None:
        raise ValueError("now must include timezone")
    current = now.astimezone(timezone.utc)

    acquisitions = _reader_rows(
        reader,
        "/rest/v1/prospect_acquisitions",
        {
            "select": "prospect_id,source,created_at",
            "order": "created_at.desc",
            "limit": "1",
        },
    )
    reviews = _reader_rows(
        reader,
        "/rest/v1/buyer_candidate_reviews",
        {
            "select": "id,status,reviewed_at,evidence",
            "status": "eq.approved",
            "order": "reviewed_at.desc",
            "limit": "25",
        },
    )
    hunter_contact_outcomes = _reader_rows(
        reader,
        "/rest/v1/intelligence_outcomes",
        {
            "select": "id,outcome_type,outcome_value,occurred_at",
            "source_system": "eq.empire_hunter",
            "outcome_type": "in.(contact_bounced,contact_complained,contact_suppressed)",
            "order": "occurred_at.desc",
            "limit": "100",
        },
    )
    degraded_emails = {
        str(value.get("email") or "").strip().lower()
        for row in hunter_contact_outcomes
        for value in [row.get("outcome_value")]
        if isinstance(value, dict)
        and str(value.get("email") or "").strip()
    }

    approved_reviews = []
    for row in reviews:
        evidence = row.get("evidence")
        if not isinstance(evidence, dict):
            continue
        if evidence.get("outreach_ready") is not True:
            continue
        contacts = evidence.get("verified_contacts")
        if not isinstance(contacts, list) or not contacts:
            continue
        viable = False
        for contact in contacts:
            if not isinstance(contact, dict):
                continue
            email = str(contact.get("email") or "").strip().lower()
            if (
                email
                and contact.get("bound_to_decision_maker") is True
                and contact.get("is_valid") is True
                and email not in degraded_emails
            ):
                viable = True
                break
        if viable:
            approved_reviews.append(row)

    intents = _reader_rows(
        reader,
        "/rest/v1/outbound_intents",
        {
            "select": "id,status,approved_at,expires_at",
            "status": "in.(approved,sent,delivered,replied)",
            "order": "created_at.desc",
            "limit": "25",
        },
    )
    authorized: list[dict[str, Any]] = []
    for row in intents:
        status = str(row.get("status") or "").lower()
        if status in {"sent", "delivered", "replied"}:
            authorized.append(row)
            continue
        expires_raw = str(row.get("expires_at") or "").strip()
        if not expires_raw or not row.get("approved_at"):
            continue
        normalized = (
            expires_raw[:-1] + "+00:00"
            if expires_raw.endswith("Z")
            else expires_raw
        )
        try:
            expires_at = datetime.fromisoformat(normalized)
        except ValueError:
            continue
        if expires_at.tzinfo and expires_at.astimezone(timezone.utc) > current:
            authorized.append(row)

    active_sent = [
        row for row in authorized
        if str(row.get("status") or "").lower()
        in {"sent", "delivered", "replied"}
    ]
    replies = _reader_rows(
        reader,
        "/rest/v1/outbound_replies",
        {
            "select": "id,classification,received_at",
            "order": "received_at.desc",
            "limit": "25",
        },
    )
    commercial_replies = [
        row for row in replies
        if str(row.get("classification") or "").strip().lower()
        in {"positive", "question", "objection"}
    ]
    orders = _reader_rows(
        reader,
        "/rest/v1/fulfilment_orders",
        {
            "select": "id,state,updated_at",
            "order": "updated_at.desc",
            "limit": "25",
        },
    )
    payment_requests = _reader_rows(
        reader,
        "/rest/v1/bsc_payment_requests",
        {
            "select": "id,status,approved_at,created_at",
            "order": "created_at.desc",
            "limit": "1",
        },
    )
    payment_evidence = _reader_rows(
        reader,
        "/rest/v1/bsc_payment_evidence",
        {
            "select": "id,request_id,verified_at",
            "order": "verified_at.desc",
            "limit": "1",
        },
    )
    outcomes = _reader_rows(
        reader,
        "/rest/v1/commercial_outcomes",
        {
            "select": "id,recorded_at",
            "order": "recorded_at.desc",
            "limit": "1",
        },
    )
    revenue = _reader_rows(
        reader,
        "/rest/v1/commercial_events",
        {
            "select": "id,amount_cents,cost_cents,margin_cents,occurred_at",
            "event_type": "eq.revenue_recognized",
            "order": "occurred_at.desc",
            "limit": "1",
        },
    )

    allocated_orders = [
        row for row in orders
        if str(row.get("state") or "").lower()
        not in {"", "raw", "qualified"}
    ]
    delivered_orders = [
        row for row in orders
        if str(row.get("state") or "").lower()
        in {
            "delivered",
            "confirmed",
            "invoiced",
            "paid",
            "settled",
            "outcome_captured",
        }
    ]
    realized_gp = [
        row for row in revenue
        if row.get("margin_cents") is not None
    ]

    return {
        "real_acquisition": CommercialLoopObservation(
            "real_acquisition",
            bool(acquisitions),
            evidence_ref="canonical:prospect_acquisitions",
            detail=(
                "canonical real acquisition evidence exists"
                if acquisitions
                else "no canonical real acquisition evidence observed"
            ),
        ),
        "buyer_candidate_approved": CommercialLoopObservation(
            "buyer_candidate_approved",
            bool(approved_reviews),
            evidence_ref="canonical:buyer_candidate_reviews:approved",
            detail=f"{len(approved_reviews)} approved outreach-ready buyer candidate(s)",
        ),
        "outbound_authorized": CommercialLoopObservation(
            "outbound_authorized",
            bool(authorized),
            evidence_ref="canonical:outbound_intents:approved",
            detail=f"{len(authorized)} currently authorized/sent outbound intent(s)",
        ),
        "outbound_sent": CommercialLoopObservation(
            "outbound_sent",
            bool(active_sent),
            evidence_ref="canonical:outbound_intents:current_sent_state",
            detail=f"{len(active_sent)} currently sent/delivered/replied intent(s)",
        ),
        "buyer_conversation": CommercialLoopObservation(
            "buyer_conversation",
            bool(commercial_replies),
            evidence_ref="canonical:outbound_replies:commercial",
            detail=(
                f"{len(commercial_replies)} commercial buyer reply(s); "
                f"{len(replies)} total reply(s)"
            ),
        ),
        "inventory_allocation": CommercialLoopObservation(
            "inventory_allocation",
            bool(allocated_orders),
            evidence_ref="canonical:fulfilment_orders",
            detail=f"{len(allocated_orders)} non-raw fulfilment order(s) observed",
        ),
        "bsc_payment_request": CommercialLoopObservation(
            "bsc_payment_request",
            bool(payment_requests),
            evidence_ref="canonical:bsc_payment_requests",
            detail=f"{len(payment_requests)} BSC payment request observation(s)",
        ),
        "bsc_usdt_payment": CommercialLoopObservation(
            "bsc_usdt_payment",
            bool(payment_evidence),
            evidence_ref="canonical:bsc_payment_evidence",
            detail=f"{len(payment_evidence)} verified BSC USDT payment evidence row(s)",
        ),
        "fulfilment": CommercialLoopObservation(
            "fulfilment",
            bool(delivered_orders),
            evidence_ref="canonical:fulfilment_orders:delivery",
            detail=f"{len(delivered_orders)} delivered/confirmed order observation(s)",
        ),
        "commercial_outcome": CommercialLoopObservation(
            "commercial_outcome",
            bool(outcomes),
            evidence_ref="canonical:commercial_outcomes",
            detail=f"{len(outcomes)} verified commercial outcome(s)",
        ),
        "recognized_revenue": CommercialLoopObservation(
            "recognized_revenue",
            bool(revenue),
            evidence_ref="canonical:commercial_events:revenue_recognized",
            detail=f"{len(revenue)} recognized revenue event observation(s)",
        ),
        "realized_gross_profit": CommercialLoopObservation(
            "realized_gross_profit",
            bool(realized_gp),
            evidence_ref="canonical:commercial_events:margin_cents",
            detail=f"{len(realized_gp)} revenue event(s) with realized GP evidence",
        ),
    }


def observations_from_cycle(
    *,
    acquisition_accepted: int | None,
    qualification: dict[str, Any],
    omega: dict[str, Any],
    buyer_readiness: dict[str, Any],
    canonical_observations: dict[
        str, CommercialLoopObservation
    ] | None = None,
) -> dict[str, CommercialLoopObservation]:
    qualified = int(qualification.get("qualified") or 0)
    scores = int(
        omega.get("scores_written")
        or omega.get("candidates_seen")
        or 0
    )
    terms_verified = int(
        buyer_readiness.get("buyers_with_verified_terms") or 0
    )
    activated_capacity = int(
        buyer_readiness.get("activated_buyers_with_capacity") or 0
    )

    observations = {
        "real_acquisition": CommercialLoopObservation(
            "real_acquisition",
            (
                None
                if acquisition_accepted is None
                else acquisition_accepted > 0
            ),
            evidence_ref="runtime:acquisition/latest.json",
            detail=(
                None
                if acquisition_accepted is None
                else f"{acquisition_accepted} real acquisition(s) accepted"
            ),
        ),
        "qualification_v2": CommercialLoopObservation(
            "qualification_v2",
            qualified > 0 or scores > 0,
            evidence_ref="canonical:prospect_qualifications:v2",
            detail=(
                f"{qualified} qualification(s) written in current cycle; "
                f"{scores} downstream Omega observation(s)"
            ),
        ),
        "omega_projection": CommercialLoopObservation(
            "omega_projection",
            scores > 0,
            evidence_ref="canonical:intelligence_scores:omega_opportunity",
            detail=f"{scores} Omega candidate/score observation(s)",
        ),
        "commercial_terms": CommercialLoopObservation(
            "commercial_terms",
            terms_verified > 0,
            evidence_ref="canonical:buyers:commercial_terms",
            detail=f"{terms_verified} buyer(s) with verified commercial terms",
        ),
        "verified_buyer_capacity": CommercialLoopObservation(
            "verified_buyer_capacity",
            activated_capacity > 0,
            evidence_ref="canonical:buyers:commercial_activation",
            detail=(
                f"{activated_capacity} commercially activated buyer(s) "
                "with remaining verified capacity"
            ),
        ),
    }
    canonical = canonical_observations or {}
    canonical_real = canonical.get("real_acquisition")
    observations.update(
        {
            key: value
            for key, value in canonical.items()
            if key != "real_acquisition"
        }
    )
    runtime_real = observations["real_acquisition"]
    if canonical_real is not None and canonical_real.observed is True:
        observations["real_acquisition"] = canonical_real
    elif runtime_real.observed is not True and canonical_real is not None:
        observations["real_acquisition"] = canonical_real
    return observations


def read_latest_acquisition_accepted(
    path: str | Path | None = None,
) -> int | None:
    source = Path(
        path
        or os.getenv(
            "EMPIRE_ACQUISITION_LATEST",
            "/srv/empire_os/runtime/acquisition/latest.json",
        )
    )
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    tail = str(raw.get("stdout_tail") or "")
    marker = '"accepted": '
    values: list[int] = []
    for segment in tail.split(marker)[1:]:
        digits = ""
        for char in segment:
            if char.isdigit():
                digits += char
            else:
                break
        if digits:
            values.append(int(digits))
    if values:
        return values[-1]

    direct = raw.get("accepted")
    try:
        return int(direct) if direct is not None else None
    except (TypeError, ValueError):
        return None


def write_commercial_loop_snapshot(
    status: CommercialLoopStatus,
    path: str | Path | None = None,
) -> Path:
    target = Path(
        path
        or os.getenv(
            "EMPIRE_COMMERCIAL_LOOP_LATEST",
            "/srv/empire_os/runtime/commercial_loop/latest.json",
        )
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(status.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.chmod(tmp, 0o600)
    tmp.replace(target)
    os.chmod(target, 0o600)
    return target
