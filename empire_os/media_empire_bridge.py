"""Bridge canonical EmpireOS intelligence into Media OS input artifacts.

Consumes existing runtime truth rather than rebuilding source systems:
- Opportunity Radar -> evidence-linked Media idea candidates.
- Opportunity Quant Review -> attached commercial-decision evidence context.
- Git history -> owned Empire Build Journal entries.

This bridge performs no external requests and creates no public actions.
Commercial opportunity scores are never reinterpreted as media scores.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any, Iterable, Mapping


OPPORTUNITY_RADAR = Path("runtime/opportunity_radar/latest.json")
QUANT_REVIEW = Path(
    "runtime/opportunity_factory/quant_review_latest.json"
)
MEDIA_IDEAS = Path(
    "runtime/media_os/input/empire_opportunity_ideas.json"
)
BUILD_JOURNAL = Path(
    "runtime/media_os/input/empire_build_journal.json"
)


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _clean(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _refs(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    return list(dict.fromkeys(
        _clean(value)
        for value in values
        if _clean(value)
    ))


def _stable_id(prefix: str, value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}:{digest}"


def _quant_by_opportunity(
    quant_review: Mapping[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    if not isinstance(quant_review, Mapping):
        return {}

    output: dict[str, dict[str, Any]] = {}
    for raw in quant_review.get("items") or []:
        if not isinstance(raw, Mapping):
            continue
        key = _clean(raw.get("opportunity_key"))
        packet = raw.get("decision_packet")
        if not key or not isinstance(packet, Mapping):
            continue
        output[key] = dict(packet)
    return output


def _idea_angle(
    opportunity_class: str,
    title: str,
) -> str:
    if opportunity_class == "community_pain":
        return (
            f"Evidence review: what public audience signals are "
            f"showing around {title}"
        )
    if opportunity_class == "competitive_research_gap":
        return (
            f"Research walkthrough: what public competitor evidence "
            f"does and does not show about {title}"
        )
    if opportunity_class == "market_research":
        return (
            f"Market intelligence walkthrough: what Empire is "
            f"currently observing about {title}"
        )
    return f"Evidence-led analysis of {title}"


def _formats(opportunity_class: str) -> list[str]:
    if opportunity_class == "community_pain":
        return ["tutorial", "rapid_intelligence"]
    if opportunity_class == "competitive_research_gap":
        return ["documentary", "rapid_intelligence"]
    if opportunity_class == "market_research":
        return ["rapid_intelligence", "documentary"]
    return ["rapid_intelligence"]


def build_media_ideas_from_opportunity_radar(
    radar: Mapping[str, Any] | None,
    *,
    quant_review: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    candidates = (
        radar.get("candidates")
        if isinstance(radar, Mapping)
        and isinstance(radar.get("candidates"), list)
        else []
    )
    quant = _quant_by_opportunity(quant_review)

    output = []
    rejected = []

    for index, raw in enumerate(candidates):
        if not isinstance(raw, Mapping):
            continue

        key = _clean(raw.get("opportunity_key"))
        title = _clean(raw.get("title"))
        refs = _refs(raw.get("evidence_refs"))
        opportunity_class = _clean(raw.get("opportunity_class"))
        source = _clean(raw.get("source"))

        if not key or not title or not refs:
            rejected.append({
                "index": index,
                "opportunity_key": key or None,
                "reason": "key_title_and_evidence_refs_required",
            })
            continue

        niche = _clean(raw.get("niche"))
        audience = (
            f"{niche} founders and operators"
            if niche
            else "founders and operators"
        )

        packet = quant.get(key) or {}
        quant_status = _clean(packet.get("status")) or "UNAVAILABLE"
        quant_ref = (
            f"opportunity_quant_review:{key}"
            if packet
            else None
        )

        products = [
            _clean(value)
            for value in (raw.get("products") or [])
            if _clean(value)
        ]

        output.append({
            "idea_id": _stable_id("media-opportunity", key),
            "topic": title,
            "angle": _idea_angle(opportunity_class, title),
            "audience": audience,
            "evidence_refs": refs,
            "source_systems": list(dict.fromkeys([
                "opportunity_radar",
                source,
            ])),
            "format_candidates": _formats(opportunity_class),
            "product_refs": products,
            "opportunity_refs": [key],
            "content_franchise_candidate": None,
            # No media feature is fabricated from Opportunity Radar's
            # research-priority or commercial score.
            "opportunity_features": {},
            "source_context": {
                "opportunity_class": opportunity_class,
                "trigger": raw.get("trigger"),
                "observed_priority_score": raw.get(
                    "observed_priority_score"
                ),
                "evidence_strength": raw.get("evidence_strength"),
                "commercial_demand_observed": (
                    raw.get("commercial_demand_observed") is True
                ),
                "recommended_next_actions": list(
                    raw.get("recommended_next_actions") or []
                ),
            },
            "quant_packet_ref": quant_ref,
            "quant_packet_status": quant_status,
            "commercial_quant_is_media_score": False,
            "automatic_build_authorized": False,
            "public_publish_authorized": False,
            "execution_authority": "none",
        })

    return {
        "schema_version": "empire.media.empire_opportunity_ideas.v1",
        "mode": "OBSERVE",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_available": isinstance(radar, Mapping),
        "candidate_count": len(output),
        "rejected_count": len(rejected),
        "rejected": rejected,
        "candidates": output,
        "commercial_quant_available_count": sum(
            row["quant_packet_status"] == "AVAILABLE"
            for row in output
        ),
        "media_score_created": False,
        "automatic_build_authorized": False,
        "public_publish_authorized": False,
        "actual_revenue": False,
        "execution_authority": "none",
    }


def collect_git_build_journal(
    repo_root: Path,
    *,
    limit: int = 30,
) -> dict[str, Any]:
    bounded = max(1, min(int(limit), 100))
    command = [
        "git",
        "-C",
        str(repo_root),
        "log",
        f"-n{bounded}",
        "--format=%H%x1f%cI%x1f%s",
    ]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {
            "schema_version": "empire.media.git_build_journal.v1",
            "mode": "OBSERVE",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "git_available": False,
            "error": type(exc).__name__,
            "items": [],
            "entry_count": 0,
            "content_opportunity_flags_inferred": False,
            "execution_authority": "none",
        }

    entries = []
    for line in result.stdout.splitlines():
        parts = line.split("\x1f", 2)
        if len(parts) != 3:
            continue
        sha, committed_at, subject = (
            _clean(parts[0]),
            _clean(parts[1]),
            _clean(parts[2]),
        )
        if not sha or not subject:
            continue

        entries.append({
            "entry_id": f"git:{sha}",
            "system": "EmpireOS",
            "change": subject,
            "problem": "UNKNOWN_NOT_RECORDED_IN_COMMIT_METADATA",
            "solution": subject,
            "evidence_refs": [f"git_commit:{sha}"],
            "before_refs": [],
            "after_refs": [f"git_commit:{sha}"],
            "screenshot_refs": [],
            "metric_refs": [],
            "business_relevance": None,
            "lessons": [],
            "created_at": committed_at or None,
            # These require separate observed evidence; commit metadata alone
            # must not promote itself into a content opportunity.
            "novelty_observed": False,
            "audience_relevance_observed": False,
            "demonstration_available": False,
            "commercial_relevance_observed": False,
        })

    return {
        "schema_version": "empire.media.git_build_journal.v1",
        "mode": "OBSERVE",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_available": True,
        "entry_count": len(entries),
        "items": entries,
        "content_opportunity_flags_inferred": False,
        "public_publish_authorized": False,
        "execution_authority": "none",
    }


def _write_json(path: Path, payload: Mapping[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(dict(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)
    return path


def refresh_media_empire_bridge(
    repo_root: Path,
    *,
    git_limit: int = 30,
) -> dict[str, Any]:
    radar = _read_json(repo_root / OPPORTUNITY_RADAR)
    quant = _read_json(repo_root / QUANT_REVIEW)

    ideas = build_media_ideas_from_opportunity_radar(
        radar,
        quant_review=quant,
    )
    journal = collect_git_build_journal(
        repo_root,
        limit=git_limit,
    )

    idea_path = _write_json(
        repo_root / MEDIA_IDEAS,
        ideas,
    )
    journal_path = _write_json(
        repo_root / BUILD_JOURNAL,
        journal,
    )

    return {
        "schema_version": "empire.media.empire_bridge.v1",
        "mode": "OBSERVE",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "opportunity_radar_available": isinstance(radar, Mapping),
        "quant_review_available": isinstance(quant, Mapping),
        "media_idea_candidate_count": ideas["candidate_count"],
        "commercial_quant_available_count": ideas[
            "commercial_quant_available_count"
        ],
        "git_build_journal_available": journal["git_available"],
        "git_build_journal_entry_count": journal["entry_count"],
        "written_paths": [
            str(idea_path.relative_to(repo_root)),
            str(journal_path.relative_to(repo_root)),
        ],
        "external_action_performed": False,
        "database_write_performed": False,
        "media_score_created": False,
        "actual_revenue": False,
        "execution_authority": "none",
    }
