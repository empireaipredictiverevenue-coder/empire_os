# EMPIRE_WAVE_092B
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any
import json


MESSAGE_FIELDS = (
    "message_id",
    "provider_message_id",
    "gmail_message_id",
    "external_message_id",
    "inbound_message_id",
    "mail_message_id",
)


THREAD_FIELDS = (
    "thread_id",
    "provider_thread_id",
    "gmail_thread_id",
    "conversation_id",
    "in_reply_to",
    "parent_message_id",
)


IDENTITY_ID_FIELDS = (
    "canonical_id",
    "person_id",
    "contact_id",
    "lead_id",
    "company_id",
)


EMAIL_FIELDS = (
    "sender_email",
    "from_email",
    "sender",
    "email",
)


CLASSIFICATION_FIELDS = (
    "classification",
    "reply_classification",
    "reply_type",
    "intent",
    "sentiment",
    "category",
    "outcome",
)


TIME_FIELDS = (
    "received_at",
    "sent_at",
    "created_at",
    "updated_at",
    "timestamp",
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


def first_value(
    row,
    names,
):

    lower = lower_map(row)

    for name in names:

        value = lower.get(name)

        if value not in (
            None,
            "",
            [],
            {},
        ):
            return (
                name,
                str(value),
            )

    return (
        None,
        None,
    )


def message_identity(
    row,
):

    name, value = first_value(
        row,
        MESSAGE_FIELDS,
    )

    if not value:
        return None

    return (
        "message:"
        + stable_hash(
            name
            + ":"
            + value
        )
    )


def thread_identity(
    row,
):

    name, value = first_value(
        row,
        THREAD_FIELDS,
    )

    if not value:
        return None

    return (
        "thread:"
        + stable_hash(
            name
            + ":"
            + value
        )
    )


def canonical_contact_identity(
    row,
):

    lower = lower_map(row)

    # Prefer existing structured Empire identities.
    for name in IDENTITY_ID_FIELDS:

        value = lower.get(name)

        if value not in (
            None,
            "",
        ):

            return (
                "identity:"
                + stable_hash(
                    name
                    + ":"
                    + str(value)
                )
            )

    # Fall back to sender identity for inbound
    # conversation evidence. Raw email is never persisted.
    for name in EMAIL_FIELDS:

        value = lower.get(name)

        if value not in (
            None,
            "",
        ):

            text = str(value).strip().casefold()

            if "@" not in text:
                continue

            return (
                "identity:"
                + stable_hash(
                    "email:"
                    + text
                )
            )

    return None


def classification(
    row,
):

    lower = lower_map(row)

    for name in CLASSIFICATION_FIELDS:

        value = lower.get(name)

        if value in (
            None,
            "",
        ):
            continue

        text = str(value).strip()

        if text:
            return text[:120]

    return None


def event_time(
    row,
):

    _, value = first_value(
        row,
        TIME_FIELDS,
    )

    if not value:
        return None

    return stable_hash(
        value
    )


def is_inbound_reply(
    *,
    source_name: str,
    row,
):

    lower = lower_map(row)

    source = source_name.casefold()

    if (
        "reply" in source
        or "inbound" in source
    ):
        return True

    for field in (
        "direction",
        "message_direction",
        "type",
        "event_type",
    ):

        value = lower.get(field)

        if value is None:
            continue

        text = str(value).casefold()

        if (
            "inbound" in text
            or "reply" in text
            or "received" in text
        ):
            return True

    return False


def source_record_hash(
    row,
):

    return stable_hash(
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


def adjudicate_records(
    records: list[
        tuple[
            str,
            dict[str, Any],
        ]
    ],
):

    candidates = []
    quarantined = []

    for source_name, row in records:

        if not isinstance(
            row,
            dict,
        ):
            continue

        mid = message_identity(row)
        tid = thread_identity(row)
        identity = canonical_contact_identity(row)
        label = classification(row)
        timestamp_hash = event_time(row)

        inbound = is_inbound_reply(
            source_name=source_name,
            row=row,
        )

        record_hash = source_record_hash(
            row
        )

        reasons = []

        if not mid:
            reasons.append(
                "MISSING_STABLE_MESSAGE_ID"
            )

        if not tid:
            reasons.append(
                "MISSING_STABLE_THREAD_ID"
            )

        if not identity:
            reasons.append(
                "MISSING_CANONICAL_CONTACT_IDENTITY"
            )

        if reasons:

            quarantined.append(
                {
                    "source_id":
                        "source:"
                        + stable_hash(
                            source_name
                        ),

                    "source_record_id":
                        record_hash,

                    "reasons":
                        reasons,
                }
            )

            continue

        candidates.append(
            {
                "canonical_id":
                    mid,

                "message_id":
                    mid,

                "thread_id":
                    tid,

                "identity_fingerprint":
                    identity,

                "entity_type":
                    (
                        "INBOUND_REPLY"
                        if inbound
                        else "CONVERSATION_MESSAGE"
                    ),

                "classification":
                    label,

                "freshness_fingerprint":
                    timestamp_hash,

                "source_id":
                    "source:"
                    + stable_hash(
                        source_name
                    ),

                "source_record_id":
                    record_hash,

                "evidence_lineage": {
                    "source_name_hash":
                        stable_hash(
                            source_name
                        ),

                    "source_record_hash":
                        record_hash,
                },

                "inbound_reply":
                    inbound,
            }
        )

    by_message = defaultdict(
        list
    )

    for item in candidates:

        by_message[
            item["message_id"]
        ].append(item)

    duplicates = 0
    conflicts = []
    conflict_ids = set()

    for message_id, items in by_message.items():

        if len(items) > 1:
            duplicates += (
                len(items) - 1
            )

        threads = {
            x["thread_id"]
            for x in items
        }

        identities = {
            x["identity_fingerprint"]
            for x in items
        }

        classifications = {
            x["classification"]
            for x in items
            if x.get(
                "classification"
            )
        }

        reasons = []

        if len(threads) > 1:
            reasons.append(
                "MESSAGE_THREAD_COLLISION"
            )

        if len(identities) > 1:
            reasons.append(
                "MESSAGE_IDENTITY_COLLISION"
            )

        if len(classifications) > 1:
            reasons.append(
                "CONTRADICTORY_CLASSIFICATION"
            )

        if reasons:

            conflict_ids.add(
                message_id
            )

            conflicts.append(
                {
                    "message_id":
                        message_id,

                    "reasons":
                        reasons,

                    "observation_count":
                        len(items),
                }
            )

    canonical_messages = []

    for message_id in sorted(
        by_message
    ):

        if message_id in conflict_ids:

            for item in by_message[
                message_id
            ]:

                quarantined.append(
                    {
                        "canonical_id":
                            message_id,

                        "source_id":
                            item[
                                "source_id"
                            ],

                        "reasons":
                            [
                                "CONFLICTING_MESSAGE_STATE"
                            ],
                    }
                )

            continue

        canonical_messages.append(
            by_message[
                message_id
            ][0]
        )

    classified_count = sum(
        1
        for x in canonical_messages
        if x.get(
            "classification"
        )
    )

    fresh_count = sum(
        1
        for x in canonical_messages
        if x.get(
            "freshness_fingerprint"
        )
    )

    inbound_replies = [
        x
        for x in canonical_messages
        if x[
            "inbound_reply"
        ]
    ]

    outcomes = []

    for item in inbound_replies:

        outcomes.append(
            {
                "outcome_id":
                    (
                        "reply-outcome:"
                        + item[
                            "message_id"
                        ].split(
                            ":",
                            1,
                        )[-1]
                    ),

                "message_id":
                    item[
                        "message_id"
                    ],

                "thread_id":
                    item[
                        "thread_id"
                    ],

                "canonical_id":
                    item[
                        "identity_fingerprint"
                    ],

                "outcome_type":
                    "INBOUND_REPLY",
            }
        )

    candidate_count = (
        len(candidates)
        + len(quarantined)
    )

    accepted_count = len(
        canonical_messages
    )

    identity_effective = (
        accepted_count > 0
    )

    classification_effective = (
        classified_count > 0
    )

    outcome_effective = (
        len(outcomes) > 0
    )

    freshness_effective = (
        fresh_count > 0
    )

    representative = (
        canonical_messages[0]
        if canonical_messages
        else {}
    )

    result = {
        "schema_version":
            "empire-conversations-replies-control-v1",

        "generated_at":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "mode":
            "OBSERVE",

        "entity_classification": {
            "candidate_count":
                candidate_count,

            "canonical_message_count":
                accepted_count,

            "inbound_reply_count":
                len(
                    inbound_replies
                ),

            "classified_count":
                classified_count,
        },

        "canonical_identity": {
            "canonical_message_count":
                accepted_count,

            "identity_bound_count":
                sum(
                    1
                    for x in canonical_messages
                    if x.get(
                        "identity_fingerprint"
                    )
                ),
        },

        "duplicate_detection": {
            "duplicate_count":
                duplicates,
        },

        "input_quality": {
            "candidate_count":
                candidate_count,

            "accepted_count":
                accepted_count,

            "quarantine_count":
                len(
                    quarantined
                ),

            "verdict":
                (
                    "PASS"
                    if accepted_count > 0
                    else "HOLD"
                ),
        },

        "output_quality": {
            "classified_count":
                classified_count,

            "classification_coverage":
                (
                    classified_count
                    / accepted_count
                    if accepted_count
                    else 0.0
                ),

            "verdict":
                (
                    "PASS"
                    if classification_effective
                    else "HOLD"
                ),
        },

        "evidence_lineage": {
            "lineage_count":
                accepted_count,
        },

        "conflict_detection": {
            "conflict_count":
                len(
                    conflicts
                ),

            "conflicts":
                conflicts[:250],
        },

        "freshness": {
            "freshness_bound_count":
                fresh_count,
        },

        "quarantine": {
            "quarantine_count":
                len(
                    quarantined
                ),

            "records":
                quarantined[:500],
        },

        "canonical_messages":
            canonical_messages,

        "linked_outcomes":
            outcomes,

        "semantic_effectiveness": {
            "candidate_count":
                candidate_count,

            "canonical_message_count":
                accepted_count,

            "classified_count":
                classified_count,

            "inbound_reply_count":
                len(
                    inbound_replies
                ),

            "outcome_link_count":
                len(
                    outcomes
                ),

            "effective":
                identity_effective,
        },

        "control_effectiveness": {
            "entity_classification":
                identity_effective,

            "canonical_identity":
                identity_effective,

            "duplicate_detection":
                candidate_count > 0,

            "input_quality":
                candidate_count > 0,

            "output_quality":
                classification_effective,

            "evidence_lineage":
                identity_effective,

            "conflict_detection":
                identity_effective,

            "freshness":
                freshness_effective,

            "quarantine":
                candidate_count > 0,

            "outcome_linkage":
                outcome_effective,

            # Observer proof is never authority proof.
            "action_authority":
                False,
        },

        "governance": {
            "db_write":
                False,

            "mailbox_write":
                False,

            "outbound":
                False,

            "live_reply":
                False,

            "closer_action":
                False,

            "funds":
                False,
        },
    }

    # Exact top-level evidence signatures only when
    # the corresponding semantic proof actually exists.

    if representative:

        result[
            "entity_type"
        ] = representative[
            "entity_type"
        ]

        result[
            "canonical_id"
        ] = representative[
            "identity_fingerprint"
        ]

        result[
            "message_id"
        ] = representative[
            "message_id"
        ]

        result[
            "thread_id"
        ] = representative[
            "thread_id"
        ]

        result[
            "source_id"
        ] = representative[
            "source_id"
        ]

        result[
            "evidence"
        ] = representative[
            "evidence_lineage"
        ]

    if candidate_count > 0:

        result[
            "duplicate_count"
        ] = duplicates

        result[
            "conflict_count"
        ] = len(
            conflicts
        )

        result[
            "quarantine_count"
        ] = len(
            quarantined
        )

    if classification_effective:

        result[
            "classification"
        ] = next(
            x[
                "classification"
            ]
            for x in canonical_messages
            if x.get(
                "classification"
            )
        )

    if freshness_effective:

        result[
            "freshness_verified"
        ] = True

    if outcomes:

        result[
            "outcome_id"
        ] = outcomes[0][
            "outcome_id"
        ]

    return result
