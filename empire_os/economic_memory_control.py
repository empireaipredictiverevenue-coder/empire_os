# EMPIRE_WAVE_091B
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from typing import Any
import json


STRONG_IDS = (
    "economic_event_id",
    "event_id",
    "payment_id",
    "order_id",
    "outcome_id",
    "conversion_id",
    "transaction_id",
    "fulfilment_id",
    "fulfillment_id",
)


RELATION_IDS = (
    "decision_id",
    "opportunity_id",
    "order_id",
    "payment_id",
    "outcome_id",
    "conversion_id",
    "fulfilment_id",
    "fulfillment_id",
)


AMOUNT_FIELDS = (
    "realised_revenue",
    "realized_revenue",
    "revenue",
    "amount",
    "amount_paid",
    "payment_amount",
    "value",
)


CURRENCY_FIELDS = (
    "currency",
    "settlement_currency",
    "payment_currency",
)


ECONOMIC_HINTS = (
    "economic",
    "revenue",
    "payment",
    "order",
    "conversion",
    "outcome",
    "fulfil",
    "fulfill",
    "transaction",
)


def stable_hash(
    value: str,
) -> str:

    return sha256(
        value.encode(
            "utf-8"
        )
    ).hexdigest()


def lower_map(
    row: dict[str, Any],
):

    return {
        str(k).casefold():
            v
        for k, v in row.items()
    }


def first_nonempty(
    row: dict[str, Any],
    names,
):

    lower = lower_map(
        row
    )

    for name in names:

        value = lower.get(
            name
        )

        if value not in (
            None,
            "",
        ):
            return (
                name,
                value,
            )

    return (
        None,
        None,
    )


def classify_event(
    row: dict[str, Any],
) -> str | None:

    lower = lower_map(
        row
    )

    keys = set(
        lower
    )

    if (
        "payment_id" in keys
        or "transaction_id" in keys
    ):
        return "PAYMENT"

    if "order_id" in keys:
        return "ORDER"

    if "conversion_id" in keys:
        return "CONVERSION"

    if "outcome_id" in keys:
        return "OUTCOME"

    if (
        "fulfilment_id" in keys
        or "fulfillment_id" in keys
    ):
        return "FULFILMENT"

    if any(
        key in keys
        for key in (
            "realised_revenue",
            "realized_revenue",
            "revenue",
        )
    ):
        return "REVENUE"

    for name in (
        "event_type",
        "type",
        "kind",
    ):

        value = lower.get(
            name
        )

        if value is None:
            continue

        text = str(
            value
        ).casefold()

        for hint in ECONOMIC_HINTS:

            if hint in text:
                return (
                    hint.upper()
                )

    return None


def canonical_event_id(
    row: dict[str, Any],
    event_type: str,
):

    lower = lower_map(
        row
    )

    priority = {
        "PAYMENT": (
            "payment_id",
            "transaction_id",
            "economic_event_id",
            "event_id",
        ),

        "ORDER": (
            "order_id",
            "economic_event_id",
            "event_id",
        ),

        "CONVERSION": (
            "conversion_id",
            "economic_event_id",
            "event_id",
        ),

        "OUTCOME": (
            "outcome_id",
            "economic_event_id",
            "event_id",
        ),

        "FULFILMENT": (
            "fulfilment_id",
            "fulfillment_id",
            "economic_event_id",
            "event_id",
        ),

        "REVENUE": (
            "economic_event_id",
            "event_id",
            "payment_id",
            "order_id",
            "conversion_id",
        ),
    }

    names = (
        priority.get(
            event_type,
            STRONG_IDS,
        )
    )

    for name in names:

        value = lower.get(
            name
        )

        if value not in (
            None,
            "",
        ):

            return (
                "economic:"
                + stable_hash(
                    event_type
                    + ":"
                    + name
                    + ":"
                    + str(value)
                )
            )

    return None


def relation_fingerprints(
    row: dict[str, Any],
):

    lower = lower_map(
        row
    )

    result = {}

    for name in RELATION_IDS:

        value = lower.get(
            name
        )

        if value in (
            None,
            "",
        ):
            continue

        result[
            name
        ] = stable_hash(
            name
            + ":"
            + str(value)
        )

    return result


def decimal_text(
    value: Any,
):

    if value in (
        None,
        "",
    ):
        return None

    try:

        number = Decimal(
            str(value)
        )

    except (
        InvalidOperation,
        ValueError,
    ):
        return None

    return format(
        number.normalize(),
        "f",
    )


def immutable_economic_facts(
    row: dict[str, Any],
):

    lower = lower_map(
        row
    )

    amount = None

    for field in AMOUNT_FIELDS:

        if field not in lower:
            continue

        amount = decimal_text(
            lower[
                field
            ]
        )

        if amount is not None:
            break

    currency = None

    for field in CURRENCY_FIELDS:

        value = lower.get(
            field
        )

        if value not in (
            None,
            "",
        ):

            currency = str(
                value
            ).strip().upper()

            break

    relations = relation_fingerprints(
        row
    )

    return {
        "amount":
            amount,

        "currency":
            currency,

        "relations":
            relations,
    }


def economic_candidate(
    row: dict[str, Any],
) -> bool:

    lower = lower_map(
        row
    )

    haystack = " ".join(
        lower.keys()
    )

    return any(
        hint in haystack
        for hint in ECONOMIC_HINTS
    )


def iter_event_dicts(
    value: Any,
    *,
    depth: int = 0,
    max_depth: int = 5,
):

    if depth > max_depth:
        return

    if isinstance(
        value,
        dict,
    ):

        if economic_candidate(
            value
        ):

            yield value

        for child in value.values():

            if isinstance(
                child,
                (
                    dict,
                    list,
                ),
            ):

                yield from iter_event_dicts(
                    child,
                    depth=depth + 1,
                    max_depth=max_depth,
                )

    elif isinstance(
        value,
        list,
    ):

        for child in value[:5000]:

            yield from iter_event_dicts(
                child,
                depth=depth + 1,
                max_depth=max_depth,
            )


def build_control(
    sources: list[
        tuple[
            str,
            Any,
        ]
    ],
):

    accepted = []
    quarantined = []

    source_candidate_count = 0

    for source_path, value in sources:

        seen_nodes = set()

        for row in iter_event_dicts(
            value
        ):

            node_hash = stable_hash(
                json.dumps(
                    row,
                    sort_keys=True,
                    default=str,
                    separators=(
                        ",",
                        ":",
                    ),
                )
            )

            if node_hash in seen_nodes:
                continue

            seen_nodes.add(
                node_hash
            )

            source_candidate_count += 1

            event_type = classify_event(
                row
            )

            if not event_type:

                quarantined.append(
                    {
                        "source_path":
                            source_path,

                        "source_record_id":
                            node_hash,

                        "reason":
                            "UNCLASSIFIED_ECONOMIC_EVENT",
                    }
                )

                continue

            canonical_id = (
                canonical_event_id(
                    row,
                    event_type,
                )
            )

            if not canonical_id:

                quarantined.append(
                    {
                        "source_path":
                            source_path,

                        "source_record_id":
                            node_hash,

                        "event_type":
                            event_type,

                        "reason":
                            "MISSING_STABLE_EVENT_ID",
                    }
                )

                continue

            facts = (
                immutable_economic_facts(
                    row
                )
            )

            fact_hash = stable_hash(
                json.dumps(
                    facts,
                    sort_keys=True,
                    separators=(
                        ",",
                        ":",
                    ),
                )
            )

            accepted.append(
                {
                    "canonical_id":
                        canonical_id,

                    "entity_type":
                        "ECONOMIC_EVENT",

                    "economic_event_type":
                        event_type,

                    "source_id":
                        (
                            "runtime:"
                            + stable_hash(
                                source_path
                            )
                        ),

                    "source_record_id":
                        node_hash,

                    "evidence_lineage":
                        {
                            "source_path_hash":
                                stable_hash(
                                    source_path
                                ),

                            "record_hash":
                                node_hash,
                        },

                    "economic_fact_fingerprint":
                        fact_hash,

                    "relations":
                        facts[
                            "relations"
                        ],

                    "has_amount":
                        facts[
                            "amount"
                        ]
                        is not None,

                    "has_currency":
                        facts[
                            "currency"
                        ]
                        is not None,
                }
            )

    groups = defaultdict(
        list
    )

    for item in accepted:

        groups[
            item[
                "canonical_id"
            ]
        ].append(
            item
        )

    duplicate_count = 0
    conflict_count = 0
    conflict_ids = set()

    for canonical_id, items in (
        groups.items()
    ):

        if len(items) > 1:

            duplicate_count += (
                len(items)
                - 1
            )

        facts = {
            item[
                "economic_fact_fingerprint"
            ]
            for item in items
        }

        if len(facts) > 1:

            conflict_count += 1

            conflict_ids.add(
                canonical_id
            )

    clean = []

    for item in accepted:

        if (
            item[
                "canonical_id"
            ]
            in conflict_ids
        ):

            quarantined.append(
                {
                    "canonical_id":
                        item[
                            "canonical_id"
                        ],

                    "source_id":
                        item[
                            "source_id"
                        ],

                    "reason":
                        "CONFLICTING_IMMUTABLE_ECONOMIC_FACTS",
                }
            )

            continue

        clean.append(
            item
        )

    unique = {}

    for item in clean:

        unique[
            item[
                "canonical_id"
            ]
        ] = item

    canonical_events = [
        unique[
            key
        ]
        for key in sorted(
            unique
        )
    ]

    linked_outcomes = []

    for item in canonical_events:

        relations = item[
            "relations"
        ]

        # Only emit these linkage keys when
        # source evidence actually contained them.
        linked = {
            "canonical_id":
                item[
                    "canonical_id"
                ],

            "economic_event_type":
                item[
                    "economic_event_type"
                ],
        }

        has_link = False

        for name in (
            "outcome_id",
            "payment_id",
            "order_id",
            "conversion_id",
            "opportunity_id",
            "decision_id",
            "fulfilment_id",
            "fulfillment_id",
        ):

            if name not in relations:
                continue

            linked[
                name
            ] = relations[
                name
            ]

            has_link = True

        if has_link:
            linked_outcomes.append(
                linked
            )

    accepted_count = len(
        canonical_events
    )

    candidate_count = (
        source_candidate_count
    )

    input_effective = (
        candidate_count > 0
    )

    identity_effective = (
        accepted_count > 0
    )

    outcome_effective = (
        len(
            linked_outcomes
        )
        > 0
    )

    output_verdict = (
        "PASS"
        if conflict_count == 0
        else "PASS_WITH_QUARANTINE"
    )

    return {
        "schema_version":
            "empire-economic-memory-control-v1",

        "generated_at":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "mode":
            "OBSERVE",

        "entity_classification": {
            "candidate_count":
                candidate_count,

            "accepted_event_count":
                accepted_count,

            "quarantined_count":
                len(
                    quarantined
                ),

            "event_types":
                sorted(
                    {
                        item[
                            "economic_event_type"
                        ]
                        for item
                        in canonical_events
                    }
                ),
        },

        "canonical_identity": {
            "canonical_event_count":
                accepted_count,

            "strategy":
                "EVENT_TYPE_PLUS_STABLE_SOURCE_ID_SHA256",
        },

        "duplicate_detection": {
            "duplicate_count":
                duplicate_count,

            "canonical_event_count":
                accepted_count,
        },

        "input_quality": {
            "candidate_count":
                candidate_count,

            "accepted_count":
                accepted_count,

            "quarantined_count":
                len(
                    quarantined
                ),

            "verdict":
                (
                    "PASS"
                    if (
                        candidate_count > 0
                        and accepted_count > 0
                    )
                    else "HOLD"
                ),
        },

        "output_quality": {
            "verdict":
                output_verdict,

            "canonical_event_count":
                accepted_count,

            "conflict_count":
                conflict_count,
        },

        "evidence_lineage": {
            "source_count":
                len(
                    sources
                ),

            "event_lineage_count":
                accepted_count,
        },

        "conflict_detection": {
            "conflict_count":
                conflict_count,

            "conflicting_event_count":
                len(
                    conflict_ids
                ),
        },

        "quarantine": {
            "quarantine_count":
                len(
                    quarantined
                ),

            "reasons":
                sorted(
                    {
                        item[
                            "reason"
                        ]
                        for item
                        in quarantined
                    }
                ),
        },

        "canonical_events":
            canonical_events,

        "linked_outcomes":
            linked_outcomes,

        "quarantined_events":
            quarantined[:500],

        "semantic_effectiveness": {
            "candidate_event_count":
                candidate_count,

            "canonical_event_count":
                accepted_count,

            "outcome_link_count":
                len(
                    linked_outcomes
                ),

            "effective":
                identity_effective,
        },

        # Shared adjudicator will now honour these.
        "control_effectiveness": {
            "entity_classification":
                identity_effective,

            "canonical_identity":
                identity_effective,

            "duplicate_detection":
                input_effective,

            "input_quality":
                input_effective,

            "output_quality":
                input_effective,

            "evidence_lineage":
                identity_effective,

            "conflict_detection":
                identity_effective,

            "quarantine":
                input_effective,

            "outcome_linkage":
                outcome_effective,
        },

        "governance": {
            "db_write":
                False,

            "memory_write":
                False,

            "outbound":
                False,

            "traffic":
                False,

            "funds":
                False,

            "existing_memory_modified":
                False,
        },
    }
