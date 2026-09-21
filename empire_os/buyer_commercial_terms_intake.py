"""Conservative extraction of explicit buyer-stated commercial price.

Only literal USD price statements tied to a supported unit are captured.
This module never chooses a price, verifies evidence, accepts terms, creates
payment requests, or recognizes revenue.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import re
from typing import Any


_PRICE_RE = re.compile(
    r"(?<!\w)(?:USD\s*)?\$\s*"
    r"(?P<amount>\d{1,6}(?:\.\d{1,2})?)"
    r"\s*(?:/|per\s+|a\s+)"
    r"(?P<unit>lead|call)s?\b",
    re.I,
)

_PRICE_WORD_RE = re.compile(
    r"\b(?:pay|paying|rate(?:\s+is)?|price(?:\s+is)?|budget(?:\s+is)?)"
    r"\s*(?:of|at|:|=)?\s*"
    r"(?:USD\s*)?\$\s*"
    r"(?P<amount>\d{1,6}(?:\.\d{1,2})?)"
    r"\s*(?:/|per\s+|a\s+)"
    r"(?P<unit>lead|call)s?\b",
    re.I,
)
def _to_cents(value: str) -> int | None:
    try:
        amount = Decimal(value)
    except (InvalidOperation, ValueError):
        return None
    if amount <= 0 or amount > Decimal("100000"):
        return None
    cents = (amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(cents)


def parse_buyer_stated_price(body_text: str) -> dict[str, Any]:
    text = str(body_text or "").strip()
    empty = {
        "has_explicit_price_evidence": False,
        "amount_cents": None,
        "unit": None,
        "currency": "USD",
        "evidence": {},
    }
    if not text:
        return empty

    matches: list[tuple[int, int, str, str]] = []
    seen: set[tuple[int, int]] = set()
    for pattern in (_PRICE_WORD_RE, _PRICE_RE):
        for match in pattern.finditer(text):
            span = match.span()
            if span in seen:
                continue
            seen.add(span)
            cents = _to_cents(match.group("amount"))
            if cents is None:
                continue
            unit = "per_lead" if match.group("unit").lower() == "lead" else "per_call"
            matches.append((span[0], cents, unit, match.group(0).strip()))

    matches.sort(key=lambda row: row[0])
    unique = {(cents, unit) for _, cents, unit, _ in matches}
    if len(unique) != 1:
        return {
            **empty,
            "evidence": {
                "parser": "buyer_stated_price_v1",
                "ambiguous": bool(matches),
                "matched_prices": [m[3] for m in matches[:5]],
                "binding": False,
                "actual_revenue": False,
            },
        }

    _, cents, unit, phrase = matches[0]
    return {
        "has_explicit_price_evidence": True,
        "amount_cents": cents,
        "unit": unit,
        "currency": "USD",
        "evidence": {
            "price_match": phrase,
            "parser": "buyer_stated_price_v1",
            "source_type": "buyer_stated",
            "binding": False,
            "verified": False,
            "actual_revenue": False,
        },
    }
