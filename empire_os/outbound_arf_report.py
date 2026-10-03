"""Minimal Abuse Reporting Format (ARF) parser for complaint evidence."""
from __future__ import annotations

from email import policy
from email.parser import Parser
from typing import Any


def parse_arf_report(raw_message: str) -> dict[str, Any]:
    message = Parser(policy=policy.default).parsestr(str(raw_message or ""))
    report: dict[str, Any] = {}

    if message.get_content_type() != "multipart/report":
        return {
            "is_arf": False,
            "feedback_type": None,
            "report": {},
            "complaint": False,
        }

    for part in message.walk():
        if part.get_content_type() != "message/feedback-report":
            continue
        payload = part.get_payload()
        if isinstance(payload, list) and payload:
            feedback = payload[0]
            for key in (
                "Feedback-Type",
                "User-Agent",
                "Version",
                "Original-Mail-From",
                "Original-Rcpt-To",
                "Arrival-Date",
                "Source-IP",
                "Authentication-Results",
                "Reported-Domain",
                "Reported-Uri",
                "Incidents",
            ):
                value = feedback.get(key)
                if value is not None:
                    report[key.lower().replace("-", "_")] = str(value)
        elif isinstance(payload, str):
            for line in payload.splitlines():
                if ":" not in line:
                    continue
                key, value = line.split(":", 1)
                normalized = key.strip().lower().replace("-", "_")
                if normalized:
                    report[normalized] = value.strip()

    feedback_type = str(report.get("feedback_type") or "").lower() or None
    return {
        "is_arf": bool(report),
        "feedback_type": feedback_type,
        "report": report,
        "complaint": feedback_type in {"abuse", "fraud"},
    }
