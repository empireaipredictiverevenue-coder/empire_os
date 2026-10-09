# EMPIRE_WAVE_090C_B
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any
from urllib.parse import urlparse
import json
import re


EMAIL_RE = re.compile(
    r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
)

PHONE_RE = re.compile(
    r"^\+?[0-9]{8,15}$"
)


FALSE_STATES = {
    "false",
    "0",
    "inactive",
    "disabled",
    "removed",
    "revoked",
    "resolved",
    "unsuppressed",
    "allow",
    "allowed",
}


TRUE_STATES = {
    "true",
    "1",
    "active",
    "suppressed",
    "blocked",
    "deny",
    "denied",
    "optout",
    "opt_out",
    "opted_out",
    "unsubscribe",
    "unsubscribed",
    "dnc",
}


def stable_hash(
    value: str,
) -> str:

    return sha256(
        value.encode(
            "utf-8"
        )
    ).hexdigest()


def normalize_email(
    value: Any,
) -> str | None:

    if value is None:
        return None

    candidate = str(
        value
    ).strip().casefold()

    if not EMAIL_RE.match(
        candidate
    ):
        return None

    return candidate


def normalize_phone(
    value: Any,
) -> tuple[str | None, bool]:

    if value is None:
        return None, False

    raw = str(
        value
    ).strip()

    raw = re.sub(
        r"[()\-\s.]",
        "",
        raw,
    )

    if raw.startswith("00"):
        raw = "+" + raw[2:]

    if not PHONE_RE.match(
        raw
    ):
        return None, False

    digits = re.sub(
        r"\D",
        "",
        raw,
    )

    if not (
        8
        <= len(digits)
        <= 15
    ):
        return None, False

    international = raw.startswith(
        "+"
    )

    return raw, international


def normalize_domain(
    value: Any,
) -> str | None:

    if value is None:
        return None

    raw = str(
        value
    ).strip().casefold()

    if not raw:
        return None

    if "://" not in raw:
        parsed = urlparse(
            "//" + raw
        )
    else:
        parsed = urlparse(
            raw
        )

    host = (
        parsed.hostname
        or ""
    ).strip(".").casefold()

    if host.startswith(
        "www."
    ):
        host = host[4:]

    if (
        "." not in host
        or " " in host
    ):
        return None

    return host


def first_value(
    row: dict[str, Any],
    names: tuple[str, ...],
):

    lower = {
        str(k).lower():
            v
        for k, v in row.items()
    }

    for name in names:

        if name in lower:
            value = lower[
                name
            ]

            if value not in (
                None,
                "",
            ):
                return value

    return None


def source_id(
    row: dict[str, Any],
) -> str:

    explicit = first_value(
        row,
        (
            "id",
            "suppression_id",
            "event_id",
            "uuid",
            "record_id",
        ),
    )

    if explicit not in (
        None,
        "",
    ):
        return (
            "outbound_suppressions:"
            + stable_hash(
                str(explicit)
            )[:24]
        )

    material = json.dumps(
        row,
        sort_keys=True,
        default=str,
        separators=(
            ",",
            ":",
        ),
    )

    return (
        "outbound_suppressions:"
        + stable_hash(
            material
        )[:24]
    )


def explicit_suppressed_state(
    row: dict[str, Any],
) -> bool | None:

    lower = {
        str(k).lower():
            v
        for k, v in row.items()
    }

    for key in (
        "suppressed",
        "is_suppressed",
        "active",
        "is_active",
        "blocked",
        "is_blocked",
    ):

        if key not in lower:
            continue

        value = lower[
            key
        ]

        if isinstance(
            value,
            bool,
        ):
            return value

        text = str(
            value
        ).strip().casefold()

        if text in TRUE_STATES:
            return True

        if text in FALSE_STATES:
            return False

    for key in (
        "status",
        "state",
        "decision",
    ):

        if key not in lower:
            continue

        text = str(
            lower[
                key
            ]
        ).strip().casefold()

        normalized = re.sub(
            r"[\s\-]+",
            "_",
            text,
        )

        if normalized in TRUE_STATES:
            return True

        if normalized in FALSE_STATES:
            return False

    return None


def extract_identity_candidates(
    row: dict[str, Any],
):

    lower = {
        str(k).lower():
            v
        for k, v in row.items()
    }

    candidates = []

    # Explicit email columns.
    for key, value in lower.items():

        if "email" not in key:
            continue

        email = normalize_email(
            value
        )

        if email:

            candidates.append(
                {
                    "entity_type":
                        "EMAIL",

                    "canonical_value":
                        email,

                    "confidence":
                        1.0,

                    "quarantine":
                        False,
                }
            )

    # Explicit phone columns.
    for key, value in lower.items():

        if not any(
            token in key
            for token in (
                "phone",
                "mobile",
                "telephone",
            )
        ):
            continue

        phone, international = (
            normalize_phone(
                value
            )
        )

        if phone:

            candidates.append(
                {
                    "entity_type":
                        (
                            "PHONE"
                            if international
                            else "PHONE_LOCAL"
                        ),

                    "canonical_value":
                        phone,

                    "confidence":
                        (
                            1.0
                            if international
                            else 0.75
                        ),

                    "quarantine":
                        not international,
                }
            )

    # Explicit domain/site columns.
    for key, value in lower.items():

        if not any(
            token in key
            for token in (
                "domain",
                "website",
                "host",
            )
        ):
            continue

        domain = normalize_domain(
            value
        )

        if domain:

            candidates.append(
                {
                    "entity_type":
                        "DOMAIN",

                    "canonical_value":
                        domain,

                    "confidence":
                        0.95,

                    "quarantine":
                        False,
                }
            )

    # Generic suppression contracts often use
    # type/channel + value/target/recipient.
    identity_type = first_value(
        row,
        (
            "identity_type",
            "target_type",
            "recipient_type",
            "channel",
            "kind",
            "type",
        ),
    )

    identity_value = first_value(
        row,
        (
            "identity_value",
            "suppression_key",
            "target",
            "recipient",
            "address",
            "value",
            "identifier",
        ),
    )

    if identity_value is not None:

        kind = str(
            identity_type
            or ""
        ).strip().casefold()

        if (
            "email" in kind
            or normalize_email(
                identity_value
            )
        ):

            email = normalize_email(
                identity_value
            )

            if email:

                candidates.append(
                    {
                        "entity_type":
                            "EMAIL",

                        "canonical_value":
                            email,

                        "confidence":
                            0.98,

                        "quarantine":
                            False,
                    }
                )

        elif any(
            token in kind
            for token in (
                "phone",
                "mobile",
                "sms",
                "voice",
                "call",
            )
        ):

            phone, international = (
                normalize_phone(
                    identity_value
                )
            )

            if phone:

                candidates.append(
                    {
                        "entity_type":
                            (
                                "PHONE"
                                if international
                                else "PHONE_LOCAL"
                            ),

                        "canonical_value":
                            phone,

                        "confidence":
                            (
                                0.98
                                if international
                                else 0.70
                            ),

                        "quarantine":
                            not international,
                    }
                )

        elif any(
            token in kind
            for token in (
                "domain",
                "company",
                "website",
            )
        ):

            domain = normalize_domain(
                identity_value
            )

            if domain:

                candidates.append(
                    {
                        "entity_type":
                            "DOMAIN",

                        "canonical_value":
                            domain,

                        "confidence":
                            0.90,

                        "quarantine":
                            False,
                    }
                )

    # Deduplicate identities inside one source row.
    seen = set()
    unique = []

    for item in candidates:

        fingerprint = (
            item[
                "entity_type"
            ],
            item[
                "canonical_value"
            ],
        )

        if fingerprint in seen:
            continue

        seen.add(
            fingerprint
        )

        unique.append(
            item
        )

    return unique


def canonical_record(
    *,
    row: dict[str, Any],
    identity: dict[str, Any],
):

    entity_type = identity[
        "entity_type"
    ]

    value = identity[
        "canonical_value"
    ]

    canonical_id = (
        "suppression:"
        + stable_hash(
            entity_type
            + ":"
            + value
        )
    )

    explicit = (
        explicit_suppressed_state(
            row
        )
    )

    # Presence in outbound_suppressions is
    # conservative suppression evidence unless
    # the row explicitly states inactive.
    if explicit is False:
        state = "INACTIVE_OR_RELEASED"
    else:
        state = "SUPPRESSED"

    quarantined = bool(
        identity[
            "quarantine"
        ]
    )

    if state == "INACTIVE_OR_RELEASED":
        # OBSERVE cannot turn an old suppression
        # row into an allow decision.
        quarantined = True

    return {
        "canonical_id":
            canonical_id,

        "entity_type":
            entity_type,

        # Never persist raw email/phone/domain
        # in the control artifact.
        "identity_fingerprint":
            stable_hash(
                value
            ),

        "identity_confidence":
            identity[
                "confidence"
            ],

        "suppression_state":
            state,

        "source_id":
            source_id(
                row
            ),

        "quarantined":
            quarantined,

        "recommended_action":
            (
                "BLOCK"
                if (
                    state
                    == "SUPPRESSED"
                    and not quarantined
                )
                else "HOLD"
            ),
    }


def build_snapshot(
    rows: list[
        dict[str, Any]
    ],
):

    records = []
    unclassified = []

    for row in rows:

        identities = (
            extract_identity_candidates(
                row
            )
        )

        if not identities:

            unclassified.append(
                {
                    "source_id":
                        source_id(
                            row
                        ),

                    "reason":
                        "NO_SAFE_IDENTITY_BINDING",
                }
            )

            continue

        for identity in identities:

            records.append(
                canonical_record(
                    row=row,
                    identity=identity,
                )
            )

    groups = defaultdict(
        list
    )

    for record in records:

        groups[
            record[
                "canonical_id"
            ]
        ].append(
            record
        )

    duplicate_count = 0
    conflict_count = 0

    duplicate_entities = []
    conflict_entities = []

    for canonical_id, items in (
        groups.items()
    ):

        if len(items) > 1:

            duplicate_count += (
                len(items)
                - 1
            )

            duplicate_entities.append(
                canonical_id
            )

        states = {
            item[
                "suppression_state"
            ]
            for item in items
        }

        if len(states) > 1:

            conflict_count += 1

            conflict_entities.append(
                canonical_id
            )

            for item in items:

                item[
                    "quarantined"
                ] = True

                item[
                    "recommended_action"
                ] = "HOLD"

    records.sort(
        key=lambda item: (
            item[
                "canonical_id"
            ],
            item[
                "source_id"
            ],
        )
    )

    quarantined = [
        item
        for item in records
        if item[
            "quarantined"
        ]
    ]

    quarantined_count = (
        len(
            quarantined
        )
        + len(
            unclassified
        )
    )

    block_count = sum(
        item[
            "recommended_action"
        ] == "BLOCK"
        for item in records
    )

    hold_count = sum(
        item[
            "recommended_action"
        ] == "HOLD"
        for item in records
    ) + len(
        unclassified
    )

    generation_material = json.dumps(
        [
            (
                item[
                    "canonical_id"
                ],
                item[
                    "suppression_state"
                ],
                item[
                    "source_id"
                ],
            )
            for item in records
        ],
        sort_keys=True,
    )

    generation_id = stable_hash(
        generation_material
    )

    input_verdict = (
        "PASS"
        if not unclassified
        and not conflict_count
        else "PASS_WITH_WARNINGS"
    )

    output_verdict = (
        "PASS"
        if all(
            item[
                "recommended_action"
            ]
            in {
                "BLOCK",
                "HOLD",
            }
            for item in records
        )
        else "REJECT"
    )

    return {
        "schema_version":
            "empire-consent-suppression-control-v1",

        "generated_at":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "mode":
            "OBSERVE",

        "generation_id":
            generation_id,

        "source_table":
            "public.outbound_suppressions",

        "entity_classification": {
            "classified_count":
                len(
                    records
                ),

            "unclassified_count":
                len(
                    unclassified
                ),

            "types":
                sorted(
                    {
                        item[
                            "entity_type"
                        ]
                        for item
                        in records
                    }
                ),
        },

        "canonical_identity": {
            "strategy":
                "TYPE_SCOPED_SHA256",

            "canonical_entity_count":
                len(
                    groups
                ),

            "raw_pii_persisted":
                False,
        },

        "duplicate_detection": {
            "duplicate_count":
                duplicate_count,

            "duplicate_entity_count":
                len(
                    duplicate_entities
                ),
        },

        "input_quality": {
            "verdict":
                input_verdict,

            "source_row_count":
                len(
                    rows
                ),

            "classified_record_count":
                len(
                    records
                ),

            "unclassified_row_count":
                len(
                    unclassified
                ),
        },

        "output_quality": {
            "verdict":
                output_verdict,

            "allow_decision_count":
                0,

            "block_count":
                block_count,

            "hold_count":
                hold_count,

            "rule":
                "OBSERVE_NEVER_EMITS_ALLOW",
        },

        "evidence_lineage": {
            "source":
                "public.outbound_suppressions",

            "source_id_count":
                len(
                    {
                        item[
                            "source_id"
                        ]
                        for item
                        in records
                    }
                ),
        },

        "conflict_detection": {
            "conflict_count":
                conflict_count,

            "conflict_entity_count":
                len(
                    conflict_entities
                ),
        },

        "freshness": {
            "generated_at":
                datetime.now(
                    timezone.utc
                ).isoformat(),

            "runtime_snapshot":
                True,
        },

        "quarantine": {
            "quarantine_count":
                quarantined_count,

            "classified_quarantine_count":
                len(
                    quarantined
                ),

            "unclassified_hold_count":
                len(
                    unclassified
                ),
        },

        # Deliberately NOT emitting an action_allowed /
        # send_authority / execution_authority field.
        #
        # The observer is not live authority.
        "live_action_authority_verified":
            False,

        # Deliberately not fabricating outcome linkage.
        "outcome_linkage_verified":
            False,

        "records":
            records,

        "unclassified":
            unclassified,

        "governance": {
            "db_write":
                False,

            "outbound":
                False,

            "traffic":
                False,

            "funds":
                False,

            "existing_governor_modified":
                False,
        },
    }
