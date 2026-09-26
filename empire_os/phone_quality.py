"""Shared phone-quality rules for commercial contact evidence."""
from __future__ import annotations

import re
from typing import Any


def phone_digits(value: Any) -> str:
    return re.sub(r"\D", "", str(value or ""))


def is_obvious_placeholder_phone(value: Any) -> bool:
    digits = phone_digits(value)
    nanp = digits[1:] if len(digits) == 11 and digits.startswith("1") else digits

    if len(nanp) == 10:
        area = nanp[:3]
        exchange = nanp[3:6]
        if area == "555" or exchange == "555":
            return True
        if nanp in {
            "0000000000",
            "1111111111",
            "1234567890",
            "0123456789",
        }:
            return True
        if len(set(nanp)) == 1:
            return True

    return False


def is_commercially_usable_phone(value: Any) -> bool:
    digits = phone_digits(value)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) == 10:
        return not is_obvious_placeholder_phone(value)

    # International evidence may be valid without NANP semantics.
    raw = re.sub(r"[^0-9+]", "", str(value or "").strip())
    if re.fullmatch(r"\+[1-9][0-9]{7,14}", raw):
        return not is_obvious_placeholder_phone(raw)
    return False


def normalized_e164(value: Any) -> str:
    raw = re.sub(r"[^0-9+]", "", str(value or "").strip())
    if not re.fullmatch(r"\+[1-9][0-9]{7,14}", raw):
        return ""
    return raw if is_commercially_usable_phone(raw) else ""
