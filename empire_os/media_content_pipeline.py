"""Canonical-content and script-brief materialization for Media OS.

Consumes only verified research packs. It does not generate prose scripts from
unverified search observations and does not call a model provider.

Verified factual claims retain their original source refs. Contested,
unsupported and unknown claims are excluded from the factual claim catalogue.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from empire_os.media_os_foundation import (
    CanonicalContentObject,
    MediaClaim,
)
from empire_os.media_script_engine import build_script_brief


INPUT = Path(
    "runtime/media_os/input/verified_research_packs.json"
)
CANONICAL_OUTPUT = Path(
    "runtime/media_os/input/canonical_content_candidates.json"
)
SCRIPT_BRIEF_OUTPUT = Path(
    "runtime/media_os/input/script_brief_candidates.json"
)
STATUS_OUTPUT = Path(
    "runtime/media_os/content_pipeline_latest.json"
)


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _records(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [
            dict(row)
            for row in value
            if isinstance(row, Mapping)
        ]
    if isinstance(value, Mapping):
        for key in ("candidates", "items", "records"):
            rows = value.get(key)
            if isinstance(rows, list):
                return [
                    dict(row)
                    for row in rows
                    if isinstance(row, Mapping)
                ]
    return []


def _clean(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _stable_id(prefix: str, value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}:{digest}"


def _write(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(dict(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)


def _script_format(pack: Mapping[str, Any]) -> str:
    opportunity_class = _clean(
        pack.get("opportunity_class")
    )
    if opportunity_class == "community_pain":
        return "tutorial"
    if opportunity_class == "competitive_research_gap":
        return "documentary"
    if opportunity_class == "market_research":
        return "rapid_intelligence"
    return "rapid_intelligence"


def canonical_content_from_verified_pack(
    pack: Mapping[str, Any],
) -> dict[str, Any]:
    if pack.get("script_ready") is not True:
        raise ValueError("verified research pack is not script_ready")

    claims = []
    evidence_refs: list[str] = []

    for raw in pack.get("claims") or []:
        if not isinstance(raw, Mapping):
            continue
        verification = (
            raw.get("verification")
            if isinstance(raw.get("verification"), Mapping)
            else {}
        )
        if verification.get("verdict") != "SUPPORTED":
            continue
        refs = tuple(
            _clean(value)
            for value in (raw.get("evidence_refs") or [])
            if _clean(value)
        )
        if not refs:
            continue
        claims.append(
            MediaClaim(
                claim=_clean(raw.get("text")),
                claim_type="factual",
                evidence_refs=refs,
                source_timestamp=(
                    _clean(raw.get("source_timestamp")) or None
                ),
                freshness_class=(
                    _clean(raw.get("freshness_class"))
                    or "CURRENT"
                ),
                uncertainty=(
                    _clean(raw.get("uncertainty")) or None
                ),
            )
        )
        evidence_refs.extend(refs)

    if not claims:
        raise ValueError(
            "script_ready research requires supported factual claims"
        )

    research_id = _clean(pack.get("research_id"))
    content_id = _stable_id("media-content", research_id)
    opportunity_key = _clean(pack.get("opportunity_key"))

    uncertainty = [
        _clean(value)
        for value in (pack.get("uncertainty") or [])
        if _clean(value)
    ]
    contested = [
        _clean(row.get("text"))
        for row in (pack.get("contested_claims") or [])
        if isinstance(row, Mapping) and _clean(row.get("text"))
    ]
    if contested:
        uncertainty.append(
            "Contested claims excluded from the factual script catalogue: "
            + " | ".join(contested[:5])
        )

    object_ = CanonicalContentObject(
        content_id=content_id,
        topic=_clean(pack.get("topic")),
        thesis=_clean(pack.get("thesis")),
        audience=_clean(pack.get("audience")),
        claims=tuple(claims),
        evidence_refs=tuple(dict.fromkeys(evidence_refs)),
        insight_refs=(research_id,),
        opportunity_refs=(
            (opportunity_key,)
            if opportunity_key
            else ()
        ),
        product_refs=tuple(
            _clean(value)
            for value in (pack.get("product_evidence_refs") or [])
            if _clean(value)
        ),
        stories=(),
        examples=tuple(
            _clean(value)
            for value in (pack.get("examples") or [])
            if _clean(value)
        ),
        visual_ideas=(
            "Show the directly observed source evidence with provenance.",
            "Use an evidence-to-visual treatment only where source lineage exists.",
        ),
        cta=(
            "Follow Empire AI for evidence-led builds, experiments and "
            "market intelligence."
        ),
        uncertainty=tuple(dict.fromkeys(uncertainty)),
    )
    row = object_.as_dict()
    row.update({
        "research_id": research_id,
        "source_claim_count": len(claims),
        "claim_verification_complete": (
            pack.get("claim_verification_complete") is True
        ),
        "script_generation_candidate": True,
        "script_generated": False,
        "storyboard_generated": False,
        "public_publish_authorized": False,
        "execution_authority": "none",
    })
    return row


def build_content_pipeline(
    verified_payload: Mapping[str, Any] | None,
) -> dict[str, Any]:
    packs = _records(verified_payload)
    canonical = []
    briefs = []
    rejected = []

    for pack in packs:
        if pack.get("script_ready") is not True:
            continue
        try:
            content_row = canonical_content_from_verified_pack(pack)
        except ValueError as exc:
            rejected.append({
                "research_id": pack.get("research_id"),
                "reason": str(exc),
            })
            continue

        content = CanonicalContentObject(
            content_id=content_row["content_id"],
            topic=content_row["topic"],
            thesis=content_row["thesis"],
            audience=content_row["audience"],
            claims=tuple(
                MediaClaim(
                    claim=row["claim"],
                    claim_type=row["claim_type"],
                    evidence_refs=tuple(row["evidence_refs"]),
                    source_timestamp=row.get("source_timestamp"),
                    freshness_class=row.get(
                        "freshness_class", "CURRENT"
                    ),
                    uncertainty=row.get("uncertainty"),
                )
                for row in content_row["claims"]
            ),
            evidence_refs=tuple(content_row["evidence_refs"]),
            insight_refs=tuple(content_row["insight_refs"]),
            opportunity_refs=tuple(
                content_row["opportunity_refs"]
            ),
            product_refs=tuple(content_row["product_refs"]),
            stories=tuple(content_row["stories"]),
            examples=tuple(content_row["examples"]),
            visual_ideas=tuple(content_row["visual_ideas"]),
            cta=content_row.get("cta"),
            uncertainty=tuple(content_row["uncertainty"]),
            created_at=content_row["created_at"],
        )

        script_format = _script_format(pack)
        brief = build_script_brief(
            content,
            script_format=script_format,
            target_duration_seconds=(
                480
                if script_format == "rapid_intelligence"
                else 720
            ),
        )
        brief.update({
            "research_id": pack.get("research_id"),
            "content_ref": content_row["content_id"],
            "claim_verification_complete": True,
            "script_generation_candidate": True,
            "script_generation_authorized": True,
            "public_publish_authorized": False,
            "execution_authority": "none",
        })

        canonical.append(content_row)
        briefs.append(brief)

    return {
        "schema_version": "empire.media.content_pipeline.v1",
        "mode": "OBSERVE",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "verified_research_pack_count": len(packs),
        "canonical_content_candidate_count": len(canonical),
        "script_brief_candidate_count": len(briefs),
        "rejected_count": len(rejected),
        "rejected": rejected,
        "canonical_content_candidates": canonical,
        "script_brief_candidates": briefs,
        "factual_claims_require_verified_research": True,
        "unverified_claims_excluded": True,
        "script_prose_generated": False,
        "public_publish_authorized": False,
        "actual_revenue": False,
        "execution_authority": "none",
    }


def refresh_media_content_pipeline(
    repo_root: Path,
) -> dict[str, Any]:
    payload = build_content_pipeline(
        _read_json(repo_root / INPUT)
    )
    _write(repo_root / STATUS_OUTPUT, payload)
    _write(
        repo_root / CANONICAL_OUTPUT,
        {
            "schema_version": (
                "empire.media.canonical_content_candidates.v1"
            ),
            "generated_at": payload["generated_at"],
            "candidate_count": payload[
                "canonical_content_candidate_count"
            ],
            "candidates": payload[
                "canonical_content_candidates"
            ],
            "public_publish_authorized": False,
            "execution_authority": "none",
        },
    )
    _write(
        repo_root / SCRIPT_BRIEF_OUTPUT,
        {
            "schema_version": (
                "empire.media.script_brief_candidates.v1"
            ),
            "generated_at": payload["generated_at"],
            "candidate_count": payload[
                "script_brief_candidate_count"
            ],
            "candidates": payload[
                "script_brief_candidates"
            ],
            "script_prose_generated": False,
            "public_publish_authorized": False,
            "execution_authority": "none",
        },
    )
    return payload
