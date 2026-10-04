"""Governed continuation from Intent Brain into identity resolution.

Pipeline:

completed Intent Brain job
    -> RESOLVE_IDENTITY only
    -> Business Identity Actor
    -> verified business/site only
    -> First-Party Identity Actor

WATCH, REJECT and every other intent decision terminate here.

This module grants no execution, outbound, promotion or payment authority.
"""

from __future__ import annotations

import fcntl
import json
import time
from pathlib import Path
from typing import Any, Callable, Mapping

from empire_os.business_identity_actor import (
    run_business_identity_actor,
)
from empire_os.first_party_identity_actor import (
    run_first_party_identity_actor,
)


BusinessRunner = Callable[
    [Mapping[str, Any]],
    Mapping[str, Any],
]

FirstPartyRunner = Callable[
    [Mapping[str, Any]],
    Mapping[str, Any],
]


SCHEMA_VERSION = (
    "empire.revenue_identity_handoff.v1"
)

STATE_SCHEMA_VERSION = (
    "empire.revenue_identity_handoff_state.v1"
)

PROVIDER_RETRY_SECONDS = 3600.0


def _load_json(
    path: Path,
    default: Any,
) -> Any:
    try:
        return json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )
    except FileNotFoundError:
        return default


def _atomic_write(
    path: Path,
    payload: Mapping[str, Any],
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary = path.with_name(
        path.name + ".tmp"
    )

    temporary.write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            default=str,
        )
        + "\n",
        encoding="utf-8",
    )

    temporary.replace(
        path
    )


def _decision(
    envelope: Mapping[str, Any] | None,
) -> str:
    if not isinstance(
        envelope,
        Mapping,
    ):
        return ""

    return str(
        envelope.get(
            "decision"
        )
        or ""
    ).strip()


def _find_value(
    value: Any,
    key: str,
) -> Any:
    if isinstance(
        value,
        Mapping,
    ):
        if key in value:
            return value[key]

        for child in value.values():
            found = _find_value(
                child,
                key,
            )

            if found is not None:
                return found

    elif isinstance(
        value,
        (list, tuple),
    ):
        for child in value:
            found = _find_value(
                child,
                key,
            )

            if found is not None:
                return found

    return None


def _clean(
    value: Any,
) -> str:
    return " ".join(
        str(value or "").split()
    )


def _business_anchor(
    result: Mapping[str, Any],
) -> tuple[
    str,
    str,
    bool,
]:
    business_name = _clean(
        _find_value(
            result,
            "business_name",
        )
    )

    website = _clean(
        _find_value(
            result,
            "website",
        )
    )

    verified = (
        _find_value(
            result,
            "business_identity_verified",
        )
        is True
    )

    return (
        business_name,
        website,
        verified,
    )


def _state_default() -> dict[str, Any]:
    return {
        "schema_version":
            STATE_SCHEMA_VERSION,
        "jobs":
            {},
        "execution_authority":
            "none",
    }


def _identity_input(
    job: Mapping[str, Any],
) -> dict[str, Any]:
    payload = (
        job.get("payload")
        or job.get("input")
        or {}
    )

    if not isinstance(
        payload,
        Mapping,
    ):
        payload = {}

    result = dict(
        payload
    )

    result[
        "upstream_decision"
    ] = "RESOLVE_IDENTITY"

    result[
        "intent_decision"
    ] = "RESOLVE_IDENTITY"

    return result


def _terminal(
    record: Mapping[str, Any],
    now: float,
) -> bool:
    status = str(
        record.get("status")
        or ""
    )

    if status == "retry_provider":
        retry_after = float(
            record.get(
                "retry_after"
            )
            or 0.0
        )

        return retry_after > now

    return status in {
        "business_unresolved",
        "business_review",
        "identity_verified",
        "identity_unresolved",
        "identity_review",
        "not_eligible",
        "stopped",
    }


def process_identity_handoffs(
    *,
    queue: Path,
    state: Path,
    lock: Path,
    limit: int = 25,
    business_runner: BusinessRunner
        = run_business_identity_actor,
    first_party_runner: FirstPartyRunner
        = run_first_party_identity_actor,
) -> dict[str, Any]:
    if limit < 1 or limit > 50:
        raise ValueError(
            "identity handoff limit must be 1-50"
        )

    queue_payload = _load_json(
        queue,
        {
            "jobs": {},
        },
    )

    jobs = queue_payload.get(
        "jobs",
        {},
    )

    if not isinstance(
        jobs,
        Mapping,
    ):
        raise ValueError(
            "revenue actor queue jobs must be an object"
        )

    lock.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    eligible = 0
    attempted = 0
    business_attempted = 0
    first_party_attempted = 0
    deduplicated = 0
    stopped = 0

    by_business_decision: dict[
        str,
        int,
    ] = {}

    by_identity_decision: dict[
        str,
        int,
    ] = {}

    with lock.open(
        "a+",
        encoding="utf-8",
    ) as handle:
        fcntl.flock(
            handle.fileno(),
            fcntl.LOCK_EX,
        )

        state_payload = _load_json(
            state,
            _state_default(),
        )

        state_jobs = state_payload.setdefault(
            "jobs",
            {},
        )

        now = time.time()

        ordered = sorted(
            jobs.items(),
            key=lambda item: str(
                item[1].get(
                    "updated_at"
                )
                or item[1].get(
                    "created_at"
                )
                or ""
            ),
        )

        for job_id, job in ordered:
            if attempted >= limit:
                break

            if not isinstance(
                job,
                Mapping,
            ):
                continue

            if (
                str(
                    job.get(
                        "status"
                    )
                    or ""
                )
                != "completed"
            ):
                continue

            result = job.get(
                "result"
            )

            if not isinstance(
                result,
                Mapping,
            ):
                continue

            intent_decision = _decision(
                result
            )

            # Hard stop for WATCH / REJECT / review states.
            if (
                intent_decision
                != "RESOLVE_IDENTITY"
            ):
                continue

            eligible += 1

            existing = state_jobs.get(
                str(job_id)
            )

            if (
                isinstance(
                    existing,
                    Mapping,
                )
                and _terminal(
                    existing,
                    now,
                )
            ):
                deduplicated += 1
                continue

            attempted += 1

            identity_payload = _identity_input(
                job
            )

            business_attempted += 1

            business_result = dict(
                business_runner(
                    identity_payload
                )
            )

            business_decision = _decision(
                business_result
            )

            by_business_decision[
                business_decision
                or "UNKNOWN"
            ] = (
                by_business_decision.get(
                    business_decision
                    or "UNKNOWN",
                    0,
                )
                + 1
            )

            record: dict[str, Any] = {
                "source_job_id":
                    str(job_id),
                "source_ref":
                    job.get(
                        "source_ref"
                    ),
                "intent_decision":
                    intent_decision,
                "business_decision":
                    business_decision,
                "business_result":
                    business_result,
                "updated_at":
                    now,
                "execution_authority":
                    "none",
            }

            if (
                business_decision
                == "DISCOVERY_PROVIDER_DEGRADED"
            ):
                record.update({
                    "status":
                        "retry_provider",
                    "retry_after":
                        now
                        + PROVIDER_RETRY_SECONDS,
                })

                state_jobs[
                    str(job_id)
                ] = record

                continue

            if (
                business_decision
                == "NEEDS_REVIEW"
            ):
                record[
                    "status"
                ] = "business_review"

                state_jobs[
                    str(job_id)
                ] = record

                stopped += 1

                continue

            if (
                business_decision
                == "NOT_ELIGIBLE"
            ):
                record[
                    "status"
                ] = "not_eligible"

                state_jobs[
                    str(job_id)
                ] = record

                stopped += 1

                continue

            if (
                business_decision
                != "BUSINESS_IDENTITY_VERIFIED"
            ):
                record[
                    "status"
                ] = "business_unresolved"

                state_jobs[
                    str(job_id)
                ] = record

                stopped += 1

                continue

            (
                business_name,
                website,
                business_verified,
            ) = _business_anchor(
                business_result
            )

            if (
                not business_verified
                or not business_name
                or not website
            ):
                record[
                    "status"
                ] = "stopped"

                record[
                    "blocker"
                ] = (
                    "business_verification_anchor_missing"
                )

                state_jobs[
                    str(job_id)
                ] = record

                stopped += 1

                continue

            first_party_payload = dict(
                identity_payload
            )

            first_party_payload.update({
                "business_name":
                    business_name,
                "website":
                    website,
                "first_party_site_verified":
                    True,
                "canonical_business_site_verified":
                    True,
            })

            first_party_attempted += 1

            first_party_result = dict(
                first_party_runner(
                    first_party_payload
                )
            )

            identity_decision = _decision(
                first_party_result
            )

            by_identity_decision[
                identity_decision
                or "UNKNOWN"
            ] = (
                by_identity_decision.get(
                    identity_decision
                    or "UNKNOWN",
                    0,
                )
                + 1
            )

            record.update({
                "business_name":
                    business_name,
                "website":
                    website,
                "identity_decision":
                    identity_decision,
                "first_party_result":
                    first_party_result,
            })

            if (
                identity_decision
                == "IDENTITY_VERIFIED"
            ):
                record[
                    "status"
                ] = "identity_verified"

            elif (
                identity_decision
                == "NEEDS_REVIEW"
            ):
                record[
                    "status"
                ] = "identity_review"

            else:
                record[
                    "status"
                ] = "identity_unresolved"

            state_jobs[
                str(job_id)
            ] = record

        state_payload[
            "execution_authority"
        ] = "none"

        state_payload[
            "updated_at"
        ] = time.time()

        _atomic_write(
            state,
            state_payload,
        )

        fcntl.flock(
            handle.fileno(),
            fcntl.LOCK_UN,
        )

    return {
        "schema_version":
            SCHEMA_VERSION,
        "mode":
            "OBSERVE",
        "eligible":
            eligible,
        "attempted":
            attempted,
        "business_attempted":
            business_attempted,
        "first_party_attempted":
            first_party_attempted,
        "deduplicated":
            deduplicated,
        "stopped":
            stopped,
        "by_business_decision":
            by_business_decision,
        "by_identity_decision":
            by_identity_decision,
        "outbound_sent":
            False,
        "canonical_promotion_performed":
            False,
        "payment_mutation":
            False,
        "execution_authority":
            "none",
    }
