#!/usr/bin/env python3
"""
Empire OS — GTM Publisher v1.

Converts the GTM planner's local JSON plan into:
    gtm_opportunities
    gtm_jobs
    commercial_events

Default mode:
    observe

Live publication:
    EMPIRE_GTM_PUBLISH_MODE=live

This module never executes workers.
It only publishes governed work for the autonomous execution bus.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from empire_os.gtm_publisher_repository import GTMPublisherRepository


ENV_PATH = "/etc/empire_os.env"

RUNTIME_ROOT = Path(
    os.environ.get(
        "EMPIRE_RUNTIME_ROOT",
        "/srv/empire_os/runtime",
    )
)

PLAN_PATH = Path(
    os.environ.get(
        "GTM_PLAN_PATH",
        str(RUNTIME_ROOT / "gtm" / "gtm_plan.json"),
    )
)

PUBLISH_MODE = os.environ.get(
    "EMPIRE_GTM_PUBLISH_MODE",
    "observe",
).strip().lower()

BATCH_SIZE = 50


def stable_key(*parts: Any) -> str:
    raw = "|".join(
        str(part or "").strip().lower()
        for part in parts
    )

    return hashlib.sha256(
        raw.encode("utf-8")
    ).hexdigest()


def load_plan() -> dict[str, Any]:
    if not PLAN_PATH.exists():
        raise RuntimeError(
            f"GTM plan does not exist: {PLAN_PATH}"
        )

    with PLAN_PATH.open(encoding="utf-8") as fh:
        plan = json.load(fh)

    if plan.get("schema_version") != "gtm_engine.v2":
        raise RuntimeError(
            "unsupported GTM plan schema: "
            f"{plan.get('schema_version')}"
        )

    return plan


def find_opportunity(
    niche: str,
    metro: str,
    *,
    repository: GTMPublisherRepository | None = None,
) -> dict[str, Any] | None:
    store = repository or GTMPublisherRepository.from_environment()
    return store.find_opportunity(niche, metro)


def publish_opportunity(
    opportunity: dict[str, Any],
    *,
    repository: GTMPublisherRepository | None = None,
) -> str:
    store = repository or GTMPublisherRepository.from_environment()
    niche = str(opportunity["niche"])
    metro = str(opportunity["metro"])

    existing = find_opportunity(
        niche,
        metro,
        repository=store,
    )

    payload = {
        "niche": niche,
        "niche_family": opportunity.get(
            "niche_family",
            niche,
        ),
        "metro": metro,
        "opportunity_type": (
            "market_allocation"
        ),
        "source_channel": (
            "gtm_engine_v2"
        ),
        "demand_score": opportunity.get(
            "buyer_demand_score",
            0,
        ),
        "supply_score": opportunity.get(
            "supply_score",
            0,
        ),
        "buyer_demand_score": opportunity.get(
            "buyer_demand_score",
            0,
        ),
        "economic_score": opportunity.get(
            "economic_score",
            0,
        ),
        "fulfilment_score": opportunity.get(
            "fulfilment_score",
            0,
        ),
        "visibility_score": opportunity.get(
            "visibility_score",
            0,
        ),
        "expected_revenue_cents": opportunity.get(
            "expected_revenue_cents",
            0,
        ),
        "expected_margin_cents": opportunity.get(
            "expected_margin_cents",
            0,
        ),
        "priority_score": opportunity.get(
            "priority_score",
            0,
        ),
        "hypothesis": (
            "Allocate autonomous GTM capacity to "
            f"{niche} in {metro}."
        ),
        "rationale": {
            "market_balance": opportunity.get(
                "market_balance"
            ),
            "prospect_count": opportunity.get(
                "prospect_count",
                0,
            ),
            "new_count": opportunity.get(
                "new_count",
                0,
            ),
            "activated_count": opportunity.get(
                "activated_count",
                0,
            ),
            "buyer_count": opportunity.get(
                "buyer_count",
                0,
            ),
            "buyer_capacity": opportunity.get(
                "buyer_capacity",
                0,
            ),
            "observed_buyer_rate": opportunity.get(
                "observed_buyer_rate"
            ),
            "notes": opportunity.get(
                "rationale",
                [],
            ),
        },
        "signal_payload": opportunity,
        "status": "discovered",
    }

    if existing:
        store.update_opportunity(str(existing["id"]), payload)
        return str(existing["id"])

    row = store.insert_opportunity(payload)
    return str(row["id"])


def create_job(
    *,
    opportunity_id: str,
    job: dict[str, Any],
    opportunity: dict[str, Any],
    repository: GTMPublisherRepository | None = None,
) -> dict[str, Any]:
    store = repository or GTMPublisherRepository.from_environment()
    job_type = str(job["job_type"])
    worker_adapter = str(
        job["worker_adapter"]
    )

    idempotency_key = (
        "gtm:"
        + stable_key(
            opportunity_id,
            job_type,
            worker_adapter,
        )
    )

    # Autonomous policy:
    # only adapters already validated as non-destructive coordination
    # work are automatically queued. Other jobs remain planned until
    # their production adapter has been hardened and registered.
    autonomous_adapters = {
        "omega_qualification_adapter",
        "fulfilment_capacity_adapter",
    }

    auto_queue = worker_adapter in autonomous_adapters

    payload = {
        "opportunity_id": opportunity_id,
        "job_type": job_type,
        "worker_adapter": worker_adapter,
        "priority": job.get("priority", 0),
        "status": "queued" if auto_queue else "planned",
        "requires_approval": not auto_queue,
        "approved_at": "now" if auto_queue else None,
        "payload": {
            **job.get("payload", {}),
            "target": job.get("target", {}),
            "publisher": "gtm_publisher_v1",
        },
        "attempts": 0,
        "max_attempts": 5,
        "created_by": "gtm_publisher_v1",
        "idempotency_key": idempotency_key,
    }

    row = store.insert_job_if_new(payload)

    return {
        "job_type": job_type,
        "worker_adapter": worker_adapter,
        "idempotency_key": idempotency_key,
        "created": row is not None,
        "row": row,
    }


def publish_plan(
    plan: dict[str, Any],
    *,
    repository: GTMPublisherRepository | None = None,
) -> dict[str, Any]:
    store = repository or GTMPublisherRepository.from_environment()
    opportunities = plan["market"][
        "top_opportunities"
    ][:50]

    jobs = plan["jobs"]["items"]

    job_by_target: dict[tuple[str, str], list[dict[str, Any]]] = {}

    for job in jobs:
        target = job.get("target") or {}

        key = (
            str(
                target.get(
                    "niche_family",
                    target.get("niche", ""),
                )
            ).lower(),
            str(
                target.get("metro", "")
            ).lower(),
        )

        job_by_target.setdefault(
            key,
            [],
        ).append(job)

    opportunity_results = []
    job_results = []

    for opportunity in opportunities:
        niche = str(
            opportunity.get(
                "niche_family",
                opportunity.get("niche", ""),
            )
        )

        metro = str(
            opportunity.get("metro", "")
        )

        matching_jobs = job_by_target.get(
            (
                niche.lower(),
                metro.lower(),
            ),
            [],
        )

        opportunity_results.append(
            {
                "niche": niche,
                "metro": metro,
                "priority_score": opportunity.get(
                    "priority_score",
                    0,
                ),
                "job_count": len(matching_jobs),
            }
        )

        if PUBLISH_MODE != "live":
            continue

        opportunity_id = publish_opportunity(
            opportunity,
            repository=store,
        )

        store.append_event({
                "event_type": "gtm_opportunity_published",
                "opportunity_id": opportunity_id,
                "channel": "gtm",
                "actor": "gtm_publisher_v1",
                "payload": {
                    "niche": niche,
                    "metro": metro,
                    "priority_score": opportunity.get(
                        "priority_score",
                        0,
                    ),
                    "job_count": len(matching_jobs),
                },
                "occurred_at": (
                    plan.get("generated_at")
                    or "now"
                ),
            })

        for job in matching_jobs:
            result = create_job(
                opportunity_id=opportunity_id,
                job=job,
                opportunity=opportunity,
                repository=store,
            )

            job_results.append(result)

    return {
        "mode": PUBLISH_MODE,
        "opportunities_considered": len(
            opportunities
        ),
        "opportunities_published": (
            len(opportunity_results)
            if PUBLISH_MODE == "live"
            else 0
        ),
        "jobs_considered": sum(
            len(
                job_by_target.get(
                    (
                        str(
                            opportunity.get(
                                "niche_family",
                                opportunity.get(
                                    "niche",
                                    "",
                                ),
                            )
                        ).lower(),
                        str(
                            opportunity.get(
                                "metro",
                                "",
                            )
                        ).lower(),
                    ),
                    [],
                )
            )
            for opportunity in opportunities
        ),
        "jobs_published": len(job_results),
        "opportunities": opportunity_results,
        "jobs": job_results,
    }


def main() -> None:
    plan = load_plan()

    print(
        "GTM PUBLISHER:",
        PUBLISH_MODE.upper(),
    )

    result = publish_plan(plan)

    print(
        json.dumps(
            result,
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
