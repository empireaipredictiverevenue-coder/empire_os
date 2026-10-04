"""Bridge verified Revenue Identity outcomes into Buyer Scout seeds.

This bridge intentionally stops before persistence.

Flow:

Revenue Intent
    -> RESOLVE_IDENTITY
    -> BUSINESS_IDENTITY_VERIFIED
    -> IDENTITY_VERIFIED
    -> Buyer Scout seed
    -> existing Buyer Scout reconciliation
    -> existing Buyer Scout holding persistence

The bridge never:
- proposes buyer review directly;
- promotes a candidate;
- authorizes outbound;
- sends outreach;
- accepts commercial terms;
- mutates payments.

Only identities already verified by the governed first-party identity
actor are eligible.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

from empire_os.intent_seed_bridge import (
    _profile_for_niche,
)


DEFAULT_IDENTITY_STATE = Path(
    "runtime/revenue_actors/identity_handoff.json"
)

DEFAULT_ACTOR_QUEUE = Path(
    "runtime/revenue_actors/intent_actor_queue.json"
)


def _clean(
    value: Any,
) -> str:
    return " ".join(
        str(value or "").split()
    )


def _float(
    value: Any,
) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _load_object(
    path: Path,
) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )
    except (
        FileNotFoundError,
        OSError,
        json.JSONDecodeError,
    ):
        return {}

    return (
        dict(value)
        if isinstance(
            value,
            Mapping,
        )
        else {}
    )


def _host(
    value: Any,
) -> str:
    text = _clean(value)

    if not text:
        return ""

    try:
        parsed = urlparse(
            text
            if "://" in text
            else f"https://{text}"
        )
    except Exception:
        return ""

    host = (
        parsed.netloc
        or parsed.path.split("/")[0]
    ).strip().lower()

    if host.startswith(
        "www."
    ):
        host = host[4:]

    return host


def _find_value(
    value: Any,
    key: str,
) -> Any:
    if isinstance(
        value,
        Mapping,
    ):
        if (
            key in value
            and value[key] is not None
        ):
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


def _source_signal_id(
    job_id: str,
    record: Mapping[str, Any],
    job: Mapping[str, Any],
) -> str:
    payload = (
        job.get("payload")
        or job.get("input")
        or {}
    )

    if isinstance(
        payload,
        Mapping,
    ):
        signal_id = _clean(
            payload.get(
                "signal_id"
            )
        )

        if signal_id:
            return signal_id

    source_ref = _clean(
        job.get(
            "source_ref"
        )
        or record.get(
            "source_ref"
        )
    )

    if source_ref.startswith(
        "signal_inbox:"
    ):
        return source_ref.split(
            ":",
            1,
        )[1]

    return job_id


def _verified_decision_maker(
    first_party_result: Mapping[str, Any],
) -> dict[str, Any] | None:
    if (
        _clean(
            first_party_result.get(
                "decision"
            )
        )
        != "IDENTITY_VERIFIED"
    ):
        return None

    governance = (
        first_party_result.get(
            "governance"
        )
        or {}
    )

    if not isinstance(
        governance,
        Mapping,
    ):
        return None

    if (
        _clean(
            governance.get(
                "execution_authority"
            )
        )
        != "none"
    ):
        return None

    output = (
        first_party_result.get(
            "output"
        )
        or {}
    )

    if not isinstance(
        output,
        Mapping,
    ):
        return None

    if (
        output.get(
            "identity_verified"
        )
        is not True
    ):
        return None

    if (
        output.get(
            "business_site_verified"
        )
        is not True
    ):
        return None

    person = output.get(
        "decision_maker"
    )

    if not isinstance(
        person,
        Mapping,
    ):
        return None

    name = _clean(
        person.get("name")
    )

    title = _clean(
        person.get("title")
    )

    source_url = _clean(
        person.get(
            "source_url"
        )
    )

    confidence = _float(
        person.get(
            "confidence"
        )
    )

    if not (
        name
        and title
        and source_url
        and confidence >= 0.70
        and person.get(
            "first_party"
        )
        is True
    ):
        return None

    return {
        "name":
            name,
        "title":
            title,
        "source":
            _clean(
                person.get(
                    "source"
                )
            ),
        "source_url":
            source_url,
        "confidence":
            confidence,
        "first_party":
            True,
    }


def build_verified_identity_seed_records(
    identity_state: Mapping[str, Any],
    actor_queue: Mapping[str, Any],
    *,
    limit: int = 25,
) -> list[dict[str, Any]]:
    """Return Buyer Scout seeds from verified identities only."""

    if limit < 1 or limit > 50:
        raise ValueError(
            "verified identity seed limit must be 1-50"
        )

    state_jobs = identity_state.get(
        "jobs"
    )

    queue_jobs = actor_queue.get(
        "jobs"
    )

    if not isinstance(
        state_jobs,
        Mapping,
    ):
        return []

    if not isinstance(
        queue_jobs,
        Mapping,
    ):
        return []

    seeds = []
    seen_domains = set()

    for raw_job_id, raw_record in sorted(
        state_jobs.items(),
        key=lambda item: str(
            item[0]
        ),
    ):
        if len(seeds) >= limit:
            break

        job_id = str(
            raw_job_id
        )

        if not isinstance(
            raw_record,
            Mapping,
        ):
            continue

        record = dict(
            raw_record
        )

        if (
            _clean(
                record.get(
                    "status"
                )
            )
            != "identity_verified"
        ):
            continue

        if (
            _clean(
                record.get(
                    "intent_decision"
                )
            )
            != "RESOLVE_IDENTITY"
        ):
            continue

        if (
            _clean(
                record.get(
                    "business_decision"
                )
            )
            != "BUSINESS_IDENTITY_VERIFIED"
        ):
            continue

        if (
            _clean(
                record.get(
                    "identity_decision"
                )
            )
            != "IDENTITY_VERIFIED"
        ):
            continue

        if (
            _clean(
                record.get(
                    "execution_authority"
                )
            )
            != "none"
        ):
            continue

        job = queue_jobs.get(
            job_id
        )

        if not isinstance(
            job,
            Mapping,
        ):
            continue

        if (
            _clean(
                job.get(
                    "status"
                )
            )
            != "completed"
        ):
            continue

        intent_result = (
            job.get(
                "result"
            )
            or {}
        )

        if not isinstance(
            intent_result,
            Mapping,
        ):
            continue

        if (
            _clean(
                intent_result.get(
                    "decision"
                )
            )
            != "RESOLVE_IDENTITY"
        ):
            continue

        governance = (
            intent_result.get(
                "governance"
            )
            or {}
        )

        if not isinstance(
            governance,
            Mapping,
        ):
            continue

        if (
            _clean(
                governance.get(
                    "execution_authority"
                )
            )
            != "none"
        ):
            continue

        first_party_result = (
            record.get(
                "first_party_result"
            )
            or {}
        )

        if not isinstance(
            first_party_result,
            Mapping,
        ):
            continue

        decision_maker = (
            _verified_decision_maker(
                first_party_result
            )
        )

        if decision_maker is None:
            continue

        output = (
            first_party_result.get(
                "output"
            )
            or {}
        )

        if not isinstance(
            output,
            Mapping,
        ):
            continue

        business_name = _clean(
            record.get(
                "business_name"
            )
            or output.get(
                "business_name"
            )
        )

        website = _clean(
            record.get(
                "website"
            )
            or output.get(
                "website"
            )
        )

        domain = _host(
            website
        )

        if not (
            business_name
            and website
            and domain
        ):
            continue

        if domain in seen_domains:
            continue

        payload = (
            job.get(
                "payload"
            )
            or job.get(
                "input"
            )
            or {}
        )

        if not isinstance(
            payload,
            Mapping,
        ):
            payload = {}

        niche = _clean(
            payload.get(
                "niche"
            )
            or _find_value(
                intent_result,
                "niche",
            )
            or "commercial_intent"
        )

        metro = _clean(
            payload.get(
                "metro"
            )
            or _find_value(
                intent_result,
                "metro",
            )
        )

        profile_key, pools = (
            _profile_for_niche(
                niche
            )
        )

        signal_id = (
            _source_signal_id(
                job_id,
                record,
                job,
            )
        )

        intent_score = (
            payload.get(
                "intent_score"
            )
        )

        if intent_score is None:
            intent_score = _find_value(
                intent_result,
                "intent_score",
            )

        intent_band = _clean(
            payload.get(
                "intent_band"
            )
            or _find_value(
                intent_result,
                "intent_band",
            )
        )

        observed_at = (
            payload.get(
                "observed_at"
            )
            or payload.get(
                "created_at"
            )
            or _find_value(
                intent_result,
                "observed_at",
            )
        )

        pain_points = (
            payload.get(
                "pain_points"
            )
        )

        if not isinstance(
            pain_points,
            list,
        ):
            found_pain = _find_value(
                intent_result,
                "pain_points",
            )

            pain_points = (
                list(
                    found_pain
                )
                if isinstance(
                    found_pain,
                    (list, tuple),
                )
                else []
            )

        intent_url = _clean(
            payload.get(
                "url"
            )
            or payload.get(
                "source_url"
            )
        )

        summary = _clean(
            payload.get(
                "text"
            )
            or payload.get(
                "body"
            )
            or payload.get(
                "content"
            )
            or payload.get(
                "snippet"
            )
            or payload.get(
                "title"
            )
        )

        refs = []

        for value in (
            intent_url,
            website,
            decision_maker.get(
                "source_url"
            ),
        ):
            text = _clean(
                value
            )

            if (
                text
                and text not in refs
            ):
                refs.append(
                    text
                )

        seeds.append({
            "id":
                f"verified-identity:{signal_id}",
            "business_name":
                business_name,
            "website":
                website,
            "domain":
                domain,
            "niche":
                niche,
            "metro":
                metro or None,
            "icp_profile_key":
                profile_key,
            "seed_buyer_pools":
                list(pools),
            "source_refs":
                refs,
            "seed_source":
                "verified_identity_intent",
            "seed_intent_signal_id":
                signal_id,
            "seed_intent_source":
                _clean(
                    payload.get(
                        "source"
                    )
                )
                or "verified_identity_intent",
            "seed_intent_score":
                intent_score,
            "seed_intent_band":
                intent_band or None,
            "seed_intent_observed_at":
                observed_at,
            "seed_intent_pain_points":
                pain_points,
            "seed_intent_evidence_url":
                intent_url or None,
            "seed_intent_summary":
                summary or None,
            "seed_canonical_identity_verified":
                True,
            "seed_business_identity_verified":
                True,
            "seed_first_party_people": [
                decision_maker
            ],
            "identity_source_job_id":
                job_id,
            "outreach_authorized":
                False,
            "execution_authority":
                "none",
        })

        seen_domains.add(
            domain
        )

    return seeds


def load_verified_identity_seed_records(
    repo_root: str | Path,
    *,
    limit: int = 25,
) -> list[dict[str, Any]]:
    root = Path(
        repo_root
    ).resolve()

    identity_state = _load_object(
        root
        / DEFAULT_IDENTITY_STATE
    )

    actor_queue = _load_object(
        root
        / DEFAULT_ACTOR_QUEUE
    )

    return (
        build_verified_identity_seed_records(
            identity_state,
            actor_queue,
            limit=limit,
        )
    )
