# EMPIRE_WAVE_090C_B3
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse


EMAIL_RE = re.compile(
    r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
)

PHONE_HINTS = (
    "phone",
    "mobile",
    "telephone",
    "tel",
    "sms",
    "voice",
    "call",
)

DOMAIN_HINTS = (
    "domain",
    "website",
    "site",
    "host",
    "company_domain",
)

VALUE_HINTS = (
    "recipient",
    "target",
    "address",
    "value",
    "identity",
    "suppression_key",
    "normalized_value",
    "normalized_recipient",
    "destination",
)

TYPE_HINTS = (
    "type",
    "kind",
    "channel",
    "identity_type",
    "recipient_type",
    "target_type",
)


@dataclass(frozen=True)
class IdentityCandidate:
    entity_type: str
    value: str
    confidence: float
    basis: str


def normalize_email(value: Any):

    if value is None:
        return None

    value = str(value).strip().casefold()

    if EMAIL_RE.fullmatch(value):
        return value

    return None


def normalize_phone(
    value: Any,
    *,
    column_hint: str = "",
):

    if value is None:
        return None

    raw = str(value).strip()

    digits = re.sub(
        r"\D",
        "",
        raw,
    )

    if not (
        8 <= len(digits) <= 15
    ):
        return None

    hint = column_hint.casefold()

    strongly_named = any(
        token in hint
        for token in PHONE_HINTS
    )

    visibly_phone = (
        raw.startswith("+")
        or bool(
            re.search(
                r"[()\-\s]",
                raw,
            )
        )
    )

    if not (
        strongly_named
        or visibly_phone
    ):
        # Avoid classifying numeric IDs as phone numbers.
        return None

    if raw.startswith("+"):
        return "+" + digits

    return digits


def normalize_domain(
    value: Any,
    *,
    column_hint: str = "",
):

    if value is None:
        return None

    raw = str(value).strip().casefold()

    if not raw:
        return None

    hint = column_hint.casefold()

    strongly_named = any(
        token in hint
        for token in DOMAIN_HINTS
    )

    explicit_url = (
        raw.startswith("http://")
        or raw.startswith("https://")
    )

    if not (
        strongly_named
        or explicit_url
    ):
        return None

    parsed = urlparse(
        raw
        if "://" in raw
        else "//" + raw
    )

    host = (
        parsed.hostname
        or ""
    ).strip(".").casefold()

    if host.startswith("www."):
        host = host[4:]

    if (
        "." not in host
        or " " in host
    ):
        return None

    return host


def type_hint(row: dict[str, Any]):

    lowered = {
        str(k).casefold(): v
        for k, v in row.items()
    }

    for key, value in lowered.items():

        if not any(
            token in key
            for token in TYPE_HINTS
        ):
            continue

        if value in (
            None,
            "",
        ):
            continue

        return str(value).casefold()

    return ""


def discover_direct_identities(
    row: dict[str, Any],
):

    results = []
    seen = set()

    hint = type_hint(
        row
    )

    for key, value in row.items():

        if value is None:
            continue

        if isinstance(
            value,
            (
                dict,
                list,
                tuple,
                set,
            ),
        ):
            continue

        column = str(
            key
        ).casefold()

        email = normalize_email(
            value
        )

        if email:

            candidate = IdentityCandidate(
                entity_type="EMAIL",
                value=email,
                confidence=1.0,
                basis=f"direct:{column}",
            )

            fingerprint = (
                candidate.entity_type,
                candidate.value,
            )

            if fingerprint not in seen:
                results.append(candidate)
                seen.add(fingerprint)

            continue

        if (
            "email" in hint
            or "email" in column
        ):

            email = normalize_email(
                value
            )

            if email:

                candidate = IdentityCandidate(
                    "EMAIL",
                    email,
                    0.99,
                    f"typed:{column}",
                )

                fingerprint = (
                    candidate.entity_type,
                    candidate.value,
                )

                if fingerprint not in seen:
                    results.append(candidate)
                    seen.add(fingerprint)

                continue

        phone = normalize_phone(
            value,
            column_hint=(
                column
                + " "
                + hint
            ),
        )

        if phone:

            candidate = IdentityCandidate(
                entity_type="PHONE",
                value=phone,
                confidence=(
                    1.0
                    if str(value).strip().startswith("+")
                    else 0.90
                ),
                basis=f"direct:{column}",
            )

            fingerprint = (
                candidate.entity_type,
                candidate.value,
            )

            if fingerprint not in seen:
                results.append(candidate)
                seen.add(fingerprint)

            continue

        domain = normalize_domain(
            value,
            column_hint=(
                column
                + " "
                + hint
            ),
        )

        if domain:

            candidate = IdentityCandidate(
                entity_type="DOMAIN",
                value=domain,
                confidence=0.95,
                basis=f"direct:{column}",
            )

            fingerprint = (
                candidate.entity_type,
                candidate.value,
            )

            if fingerprint not in seen:
                results.append(candidate)
                seen.add(fingerprint)

    return results


def strong_join_columns(
    suppression_columns,
    lead_columns,
):

    suppression_columns = {
        str(x).casefold()
        for x in suppression_columns
    }

    lead_columns = {
        str(x).casefold()
        for x in lead_columns
    }

    strong_names = (
        "lead_id",
        "enriched_lead_id",
        "contact_id",
        "person_id",
        "company_id",
        "canonical_person_id",
        "canonical_contact_id",
        "identity_fingerprint",
        "recipient_hash",
        "email_hash",
        "phone_hash",
    )

    pairs = []

    for name in strong_names:

        if (
            name in suppression_columns
            and name in lead_columns
        ):
            pairs.append(
                (
                    name,
                    name,
                    "EXACT_STRONG_KEY",
                )
            )

    # Semantic FK-style aliases to the lead PK.
    for left in (
        "lead_id",
        "enriched_lead_id",
    ):

        if (
            left in suppression_columns
            and "id" in lead_columns
        ):

            pairs.append(
                (
                    left,
                    "id",
                    "SEMANTIC_LEAD_ID",
                )
            )

    return pairs
