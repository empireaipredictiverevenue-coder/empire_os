"""Deterministic quality-control gate for Empire Media OS."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping


QC_CATEGORIES = (
    "video",
    "audio",
    "text",
    "thumbnail",
    "brand",
    "content",
    "rights",
)

ALLOWED_STATUS = frozenset({"PASS", "FAIL", "UNKNOWN"})


@dataclass(frozen=True)
class MediaQCCheck:
    category: str
    check: str
    status: str
    evidence_refs: tuple[str, ...] = ()
    detail: str | None = None
    required: bool = True

    def as_dict(self) -> dict[str, Any]:
        if self.category not in QC_CATEGORIES:
            raise ValueError("unsupported QC category")
        if not self.check.strip():
            raise ValueError("QC check name is required")
        if self.status not in ALLOWED_STATUS:
            raise ValueError("unsupported QC status")
        if self.status == "PASS" and not self.evidence_refs:
            raise ValueError("PASS QC checks require evidence_refs")
        return {
            "category": self.category,
            "check": self.check,
            "status": self.status,
            "evidence_refs": list(self.evidence_refs),
            "detail": self.detail,
            "required": self.required,
        }


def evaluate_media_quality_gate(
    checks: Iterable[MediaQCCheck],
    *,
    rights_manifest: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    rows = [check.as_dict() for check in checks]
    required_failures = [
        row
        for row in rows
        if row["required"] and row["status"] == "FAIL"
    ]
    required_unknowns = [
        row
        for row in rows
        if row["required"] and row["status"] == "UNKNOWN"
    ]

    rights_ready = (
        rights_manifest is not None
        and rights_manifest.get("commercial_release_ready") is True
    )

    if required_failures:
        decision = "REJECT_OR_REGENERATE"
    elif required_unknowns or not rights_ready:
        decision = "HOLD_FOR_EVIDENCE"
    else:
        decision = "QC_READY_FOR_GOVERNED_PUBLISH_REVIEW"

    by_category = {
        category: {
            "pass": sum(
                row["category"] == category
                and row["status"] == "PASS"
                for row in rows
            ),
            "fail": sum(
                row["category"] == category
                and row["status"] == "FAIL"
                for row in rows
            ),
            "unknown": sum(
                row["category"] == category
                and row["status"] == "UNKNOWN"
                for row in rows
            ),
        }
        for category in QC_CATEGORIES
    }

    return {
        "schema_version": "empire.media.qc_gate.v1",
        "mode": "OBSERVE",
        "check_count": len(rows),
        "checks": rows,
        "category_summary": by_category,
        "required_failure_count": len(required_failures),
        "required_unknown_count": len(required_unknowns),
        "rights_ready": rights_ready,
        "decision": decision,
        "publish_ready_candidate": (
            decision == "QC_READY_FOR_GOVERNED_PUBLISH_REVIEW"
        ),
        "public_publish_authorized": False,
        "execution_authority": "none",
    }
