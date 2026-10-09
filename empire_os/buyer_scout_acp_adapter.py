"""Pre-canonical Buyer Scout admission for Autonomous Commercial Progression.

This adapter does one reversible internal transition:

REVIEW_READY buyer-scout holding
    -> canonical raw prospect

It never creates:
- a buyer
- a qualification
- outbound authority
- a live message
- a call
- binding terms
- payment/funds
- recognized revenue

The existing database promotion RPC remains the atomic authority boundary.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, Mapping
import urllib.parse

from empire_os.buyer_scout_raw_prospect_promotion import (
    run_raw_prospect_promotion,
)
from empire_os.sb import request_json
from empire_os.buyer_scout_review_readiness import _official_source_identity_matches
from empire_os.autonomous_commercial_progression import (
    ExecutionAuthority, authority_state, authority_blocker,
)
from empire_os.buyer_scout_canonical_person_bridge import materialize_buyer_scout_identity


ACP_ACTOR = (
    "empire_autonomous_commercial_progression"
)


def _text(value: Any) -> str:
    return str(
        value or ""
    ).strip()


def _int(value: Any) -> int:
    try:
        return int(
            float(
                str(
                    value
                    if value is not None
                    else 0
                )
            )
        )
    except (
        TypeError,
        ValueError,
    ):
        return 0


def _verified_people(
    row: Mapping[str, Any],
) -> list[dict[str, Any]]:
    site = (
        row.get("site_evidence")
        or {}
    )

    if not isinstance(
        site,
        Mapping,
    ):
        return []

    people = (
        site.get("first_party_people")
        or []
    )

    output = []

    for raw in people:
        if not isinstance(
            raw,
            Mapping,
        ):
            continue

        person = dict(raw)

        if (
            person.get(
                "person_explicitly_named"
            ) is not True
            or person.get(
                "email_directly_bound_to_person"
            ) is not True
            or person.get(
                "mx_verified"
            ) is not True
            or not _text(
                person.get("name")
            )
            or not _text(
                person.get("email")
            )
        ):
            continue

        source = _text(
            person.get("source")
        )

        source_url = _text(
            person.get("source_url")
        )

        if (
            source != "first_party_site"
            or not source_url
        ):
            continue

        output.append(
            person
        )

    return output


def eligible_for_acp_admission(
    row: Mapping[str, Any],
) -> bool:
    if (
        row.get("review_state")
        != "review_ready"
    ):
        return False

    if (
        row.get(
            "reconciliation_state"
        )
        != "REVIEW_READY"
    ):
        return False

    if _text(
        row.get(
            "canonical_prospect_id"
        )
    ):
        return False

    if not _text(
        row.get("id")
    ):
        return False

    if not _text(
        row.get("domain")
    ):
        return False

    if not (
        row.get("target_product_codes")
        or []
    ):
        return False

    # Historical REVIEW_READY rows must not bypass newer identity checks.
    # The ACP reader includes canonical query evidence, never just status.
    queries = row.get("query_evidence") or []
    if not isinstance(queries, list) or not _official_source_identity_matches(
        queries,
        row.get("site_evidence") or {},
        _text(row.get("business_name")),
    ):
        return False

    return bool(
        _verified_people(row)
    )


def _enterprise_fit(
    row: Mapping[str, Any],
) -> int:
    provenance = (
        row.get("provenance")
        or {}
    )

    if not isinstance(
        provenance,
        Mapping,
    ):
        return 0

    return _int(
        provenance.get(
            "predictive_revenue_enterprise_fit_score"
        )
    )


def _enterprise_candidate(
    row: Mapping[str, Any],
) -> bool:
    provenance = (
        row.get("provenance")
        or {}
    )

    return bool(
        isinstance(
            provenance,
            Mapping,
        )
        and provenance.get(
            "predictive_revenue_enterprise_candidate"
        )
        is True
    )


def rank_precanonical_candidates(
    candidates: Iterable[
        Mapping[str, Any]
    ],
    *,
    excluded_candidate_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    excluded = {
        _text(value)
        for value in (
            excluded_candidate_ids
            or set()
        )
        if _text(value)
    }

    rows = []

    for raw in candidates:
        row = dict(raw)

        if not eligible_for_acp_admission(
            row
        ):
            continue

        if _text(
            row.get("id")
        ) in excluded:
            continue

        row[
            "_acp_verified_person_count"
        ] = len(
            _verified_people(row)
        )

        row[
            "_acp_enterprise_fit"
        ] = _enterprise_fit(row)

        row[
            "_acp_enterprise_candidate"
        ] = _enterprise_candidate(
            row
        )

        rows.append(row)

    rows.sort(
        key=lambda row: (
            -int(
                bool(
                    row.get(
                        "_acp_enterprise_candidate"
                    )
                )
            ),
            -_int(
                row.get(
                    "_acp_enterprise_fit"
                )
            ),
            -_int(
                row.get(
                    "_acp_verified_person_count"
                )
            ),
            -int(
                bool(
                    row.get(
                        "explicit_direct_buyer_evidence"
                    )
                )
            ),
            -_int(
                row.get(
                    "direct_buyer_score"
                )
            ),
            _text(
                row.get("id")
            ),
        )
    )

    return rows


def fetch_precanonical_candidates(
    *,
    limit: int = 500,
) -> list[dict[str, Any]]:
    bounded = max(
        1,
        min(
            int(limit),
            500,
        ),
    )

    query = urllib.parse.urlencode({
        "select": (
            "id,domain,business_name,website,"
            "review_state,reconciliation_state,"
            "canonical_buyer_id,canonical_prospect_id,"
            "direct_buyer_score,"
            "explicit_direct_buyer_evidence,"
            "target_buyer_pools,target_product_codes,"
            "site_evidence,query_evidence,provenance,"
            "updated_at,last_seen_at"
        ),
        "review_state":
            "eq.review_ready",
        "reconciliation_state":
            "eq.REVIEW_READY",
        "canonical_prospect_id":
            "is.null",
        "limit":
            str(bounded),
    })

    rows = request_json(
        "GET",
        (
            "/rest/v1/"
            "buyer_scout_candidates?"
            + query
        ),
    ) or []

    if not isinstance(
        rows,
        list,
    ):
        raise ValueError(
            "buyer-scout candidate projection "
            "must be a list"
        )

    return [
        dict(row)
        for row in rows
        if isinstance(
            row,
            Mapping,
        )
    ]


def run_precanonical_admission(
    *,
    excluded_candidate_ids: set[str] | None = None,
    selected_candidate: Mapping[str, Any] | None = None,
    mode: str = "AUTO_INTERNAL",
    execution_authority: ExecutionAuthority | None = None,
) -> dict[str, Any]:
    state = authority_state(mode, execution_authority)
    if not state["internal_mutation_authorized"]:
        return {
            **authority_blocker(mode, execution_authority),
            "action": "canonicalize_buyer_scout_candidate",
            "selected_action": "canonicalize_buyer_scout_candidate",
            "candidate_id": (selected_candidate or {}).get("id"),
            "canonical_prospect_id": None,
        }
    # Selection and execution must operate on the same row.
    # A caller that has already ranked a candidate passes that
    # exact evidence snapshot here; we must not silently refetch
    # and select a different company.
    if selected_candidate is None:
        candidates = (
            fetch_precanonical_candidates()
        )
    else:
        candidates = [
            dict(selected_candidate)
        ]

    ranked = rank_precanonical_candidates(
        candidates,
        excluded_candidate_ids=(
            excluded_candidate_ids
        ),
    )

    if not ranked:
        return {
            **state,
            "schema_version":
                "empire.buyer-scout-acp-admission.v1",
            "generated_at":
                datetime.now(
                    timezone.utc
                ).isoformat(),
            "status":
                "NO_ELIGIBLE_PRECANONICAL_CANDIDATE",
            "action":
                "canonicalize_buyer_scout_candidate",
            "candidate_id": None,
            "canonical_prospect_id": None,
            "internal_mutation_performed": False,
            "external_execution_performed": False,
            "outbound_sent": False,
            "call_placed": False,
            "binding_terms_action": False,
            "payment_action": False,
            "actual_revenue": False,
        }

    selected = ranked[0]

    candidate_id = _text(
        selected.get("id")
    )

    people = _verified_people(
        selected
    )

    promotion = (
        run_raw_prospect_promotion(
            [selected],
            rpc_call=(
                lambda method, path, body:
                    request_json(
                        method,
                        path,
                        payload=body,
                    )
            ),
            execute=state["internal_mutation_authorized"],
            actor=ACP_ACTOR,
            authority_mode="auto_internal",
        )
    )

    results = (
        promotion.get("results")
        or []
    )

    first = (
        results[0]
        if results
        and isinstance(
            results[0],
            Mapping,
        )
        else {}
    )

    canonical_prospect_id = _text(
        first.get(
            "canonical_prospect_id"
        )
    ) or None

    promoted = (
        promotion.get(
            "canonical_promotion_performed"
        )
        is True
    )

    wrote = (
        promotion.get(
            "database_write_performed"
        )
        is True
    )

    if promoted:
        status = (
            "ADVANCED_CANONICAL_PROSPECT_CREATED"
        )
        blocker = None
    elif canonical_prospect_id:
        status = (
            "ALREADY_CANONICAL"
        )
        blocker = None
    else:
        status = "BLOCKED"
        blocker = (
            _text(
                first.get("decision")
            )
            or "canonical_promotion_not_performed"
        )

    # Continue with the exact RPC result, never another candidate selection.
    identity_bridge = None
    if canonical_prospect_id:
        try:
            identity_bridge = materialize_buyer_scout_identity(
                prospect_id=canonical_prospect_id,
                write_authorized=state["internal_mutation_authorized"],
                request_factory=request_json,
            )
        except Exception:
            identity_bridge = {
                "ok": False, "retryable": True,
                "blocker": "CANONICAL_PERSON_BRIDGE_FAILED",
            }
        if identity_bridge.get("ok") is not True:
            blocker = identity_bridge.get("blocker") or "CANONICAL_PERSON_BRIDGE_FAILED"
        elif identity_bridge.get("decision_status") != "RESOLVED":
            blocker = identity_bridge.get("decision_status")

    return {
        **state,
        "selected_action": "canonicalize_buyer_scout_candidate",
        "schema_version":
            "empire.buyer-scout-acp-admission.v1",
        "generated_at":
            datetime.now(
                timezone.utc
            ).isoformat(),
        "status": status,
        "action":
            "canonicalize_buyer_scout_candidate",
        "blocker": blocker,
        "recovery_strategy":
            "review_ready_person_bound_to_canonical_prospect",
        "candidate_id":
            candidate_id,
        "company_name":
            selected.get(
                "business_name"
            ),
        "domain":
            selected.get("domain"),
        "enterprise_candidate":
            selected.get(
                "_acp_enterprise_candidate"
            ),
        "enterprise_fit":
            selected.get(
                "_acp_enterprise_fit"
            ),
        "verified_person_count":
            len(people),
        "verified_people": [
            {
                "name":
                    person.get("name"),
                "title":
                    person.get("title"),
                "email":
                    person.get("email"),
                "source_url":
                    person.get(
                        "source_url"
                    ),
            }
            for person in people
        ],
        "target_product_codes":
            list(
                selected.get(
                    "target_product_codes"
                )
                or []
            ),
        "canonical_prospect_id":
            canonical_prospect_id,
        "identity_bridge": identity_bridge,
        "retryable": bool(identity_bridge and identity_bridge.get("retryable")),
        "promotion":
            promotion,
        "internal_mutation_performed":
            wrote or bool(identity_bridge and identity_bridge.get("internal_mutation_performed")),
        "external_execution_performed":
            False,
        "outbound_sent": False,
        "call_placed": False,
        "binding_terms_action": False,
        "payment_action": False,
        "actual_revenue": False,
    }
