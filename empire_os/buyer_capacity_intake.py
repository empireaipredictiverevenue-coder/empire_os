"""Deterministic extraction of buyer-stated operating capacity.

This parser only records explicit statements from a genuine inbound reply. It
never infers price, contractual acceptance, commercial activation, or revenue.
"""
from __future__ import annotations

import re
from typing import Any

_CAPACITY_PATTERNS = (
    re.compile(
        r"\b(?:handle|take|accept|manage|capacity(?:\s+is|\s*:)?|"
        r"can\s+do)\D{0,24}(\d{1,4})(?:\s*[-–]\s*(\d{1,4}))?"
        r"\s*(?:qualified\s+)?(?:leads?|opportunities|calls?)?"
        r"\s*(?:per|a|/)\s*day\b",
        re.I,
    ),
    re.compile(
        r"\b(\d{1,4})(?:\s*[-–]\s*(\d{1,4}))?"
        r"\s*(?:qualified\s+)?(?:leads?|opportunities|calls?)"
        r"\s*(?:per|a|/)\s*day\b",
        re.I,
    ),
)

_TERRITORY_PATTERNS = (
    re.compile(
        r"\b(?:we\s+)?cover(?:age)?(?:\s+area)?\s*(?:is|are|:)?\s*"
        r"([A-Za-z][A-Za-z0-9 .,&/'-]{1,90}?)"
        r"(?=(?:[.;\n]|\s+and\s+(?:we|can|our|email|phone|webhook|api)\b|$))",
        re.I,
    ),
    re.compile(
        r"\b(?:target\s+area|territory|market)\s*(?:is|are|:)?\s*"
        r"([A-Za-z][A-Za-z0-9 .,&/'-]{1,90}?)"
        r"(?=(?:[.;\n]|\s+and\s+(?:we|can|our|email|phone|webhook|api)\b|$))",
        re.I,
    ),
)

_EMAIL_RE = re.compile(
    r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
    re.I,
)
_URL_RE = re.compile(r"https?://[^\s<>()]+", re.I)
_PHONE_RE = re.compile(r"(?<!\d)(\+?\d[\d ()-]{7,}\d)(?!\d)")


def _clean_territory(value: str) -> str:
    text = " ".join(value.strip(" ,:-").split())
    return text[:120]


def _capacity(text: str) -> tuple[int | None, dict[str, Any]]:
    for pattern in _CAPACITY_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        low = int(match.group(1))
        high = int(match.group(2)) if match.group(2) else low
        if low < 1 or high < 1 or low > 10000 or high > 10000:
            continue
        bounded = min(low, high)
        return bounded, {
            "capacity_low": min(low, high),
            "capacity_high": max(low, high),
            "capacity_match": match.group(0).strip(),
            "capacity_policy": "lower_bound_for_bounded_planning",
        }
    return None, {}


def _territory(text: str) -> tuple[str | None, dict[str, Any]]:
    for pattern in _TERRITORY_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        value = _clean_territory(match.group(1))
        if len(value) < 2:
            continue
        return value, {
            "territory_match": match.group(0).strip(),
        }
    return None, {}


def _delivery(text: str) -> tuple[str | None, str | None, dict[str, Any]]:
    lowered = text.lower()
    routes: list[str] = []
    if "webhook" in lowered:
        routes.append("webhook")
    if re.search(r"\bapi\b", lowered):
        routes.append("api")
    if re.search(r"\bemail\b|\be-mail\b", lowered):
        routes.append("email")
    if re.search(r"\bphone\b|\bcall(?:s|ing)?\b", lowered):
        routes.append("phone")

    routes = list(dict.fromkeys(routes))
    if len(routes) != 1:
        return None, None, {
            "delivery_options": routes,
            "delivery_ambiguous": len(routes) > 1,
        }

    route = routes[0]
    reference: str | None = None
    if route == "email":
        match = _EMAIL_RE.search(text)
        reference = match.group(0).lower() if match else None
    elif route in {"webhook", "api"}:
        match = _URL_RE.search(text)
        reference = match.group(0).rstrip(".,") if match else None
    elif route == "phone":
        match = _PHONE_RE.search(text)
        reference = " ".join(match.group(1).split()) if match else None

    return route, reference, {
        "delivery_options": routes,
        "delivery_ambiguous": False,
    }


def parse_buyer_capacity_reply(body_text: str) -> dict[str, Any]:
    text = str(body_text or "").strip()
    if not text:
        return {
            "has_explicit_capacity_evidence": False,
            "state": "none",
            "territory": None,
            "daily_cap": None,
            "delivery_route": None,
            "delivery_reference": None,
            "evidence": {},
        }

    daily_cap, cap_evidence = _capacity(text)
    territory, territory_evidence = _territory(text)
    route, reference, delivery_evidence = _delivery(text)

    present = [
        name
        for name, value in (
            ("territory", territory),
            ("daily_cap", daily_cap),
            ("delivery_route", route),
            ("delivery_reference", reference),
        )
        if value is not None
    ]
    complete = (
        territory is not None
        and daily_cap is not None
        and route is not None
    )
    evidence = {
        **cap_evidence,
        **territory_evidence,
        **delivery_evidence,
        "explicit_fields": present,
        "parser": "buyer_capacity_intake_v1",
        "binding_commercial_terms": False,
        "actual_revenue": False,
    }
    return {
        "has_explicit_capacity_evidence": bool(present),
        "state": "complete" if complete else ("partial" if present else "none"),
        "territory": territory,
        "daily_cap": daily_cap,
        "delivery_route": route,
        "delivery_reference": reference,
        "evidence": evidence,
    }
