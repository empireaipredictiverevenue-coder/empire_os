"""Governed product-demo recording manifests.

This module plans what a technical demo should show. It does not launch a
browser, record a screen, publish media, or claim commercial outcomes.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable
from urllib.parse import urlparse


ALLOWED_ACTIONS = {"navigate", "click", "wait", "scroll", "highlight"}


@dataclass(frozen=True)
class DemoStep:
    action: str
    target: str
    description: str
    evidence_ref: str

    def validate(self) -> None:
        if self.action not in ALLOWED_ACTIONS:
            raise ValueError(f"unsupported demo action: {self.action}")
        if not self.target.strip():
            raise ValueError("demo target required")
        if not self.description.strip():
            raise ValueError("demo description required")
        if not self.evidence_ref.strip():
            raise ValueError("demo evidence_ref required")


def build_video_demo_manifest(
    *,
    title: str,
    app_url: str,
    niche: str,
    steps: Iterable[DemoStep],
    capability_evidence_refs: Iterable[str],
    target_duration_seconds: int = 180,
) -> dict[str, Any]:
    parsed = urlparse(str(app_url or "").strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("app_url must be an http(s) URL")
    if not str(title or "").strip():
        raise ValueError("title required")
    if not str(niche or "").strip():
        raise ValueError("niche required")
    if not 30 <= int(target_duration_seconds) <= 600:
        raise ValueError("target_duration_seconds must be 30-600")

    rows = tuple(steps)
    if not rows:
        raise ValueError("at least one demo step required")
    for step in rows:
        step.validate()

    refs = tuple(
        dict.fromkeys(
            [
                *(
                    ref.strip()
                    for ref in capability_evidence_refs
                    if str(ref).strip()
                ),
                *(step.evidence_ref.strip() for step in rows),
            ]
        )
    )
    if not refs:
        raise ValueError("demo manifest requires evidence refs")

    return {
        "schema_version": "empire.video_demo_manifest.v1",
        "title": title.strip(),
        "niche": niche.strip(),
        "app_url": app_url.strip(),
        "target_duration_seconds": int(target_duration_seconds),
        "steps": [asdict(step) for step in rows],
        "evidence_refs": list(refs),
        "recording_engine": "playwright_optional_adapter",
        "recording_enabled": False,
        "publishing_enabled": False,
        "automatic_distribution": False,
        "synthetic_proof_allowed": False,
        "pricing_claims_allowed_without_evidence": False,
        "revenue_claims_allowed_without_evidence": False,
        "actual_revenue": False,
    }
