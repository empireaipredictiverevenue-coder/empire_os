"""Runtime aggregator for the flagship Empire AI Media OS channel.

This is the first internal runtime loop for Media OS. It consumes only observed
adapter artifacts already present under runtime/media_os/input and writes one
read-only/draft status artifact. Missing evidence remains missing.

No network calls, publishing, channel creation, GPU provisioning, outreach, or
revenue recognition occur here.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from empire_os.media_algorithm_intelligence import (
    DistributionObservation,
    analyse_distribution,
    build_algorithm_hypothesis_packet,
    build_recommendation_chain_packet,
)
from empire_os.media_analytics import (
    normalize_owned_channel_analytics,
)
from empire_os.media_build_journal import (
    BuildJournalEntry,
    content_opportunity_from_build,
)
from empire_os.media_idea_factory import MediaIdeaCandidate
from empire_os.media_trend_fusion import MediaTrendSignal, fuse_media_trend
from empire_os.youtube_intelligence import (
    build_channel_baseline,
    build_outlier_candidates,
    normalize_youtube_video_observation,
)


OUTPUT = Path("runtime/media_os/latest.json")
INPUT_DIR = Path("runtime/media_os/input")

INPUTS = {
    "youtube_public": INPUT_DIR / "youtube_public_observations.json",
    "youtube_owned_analytics": INPUT_DIR / "youtube_owned_analytics.json",
    "youtube_owned_video_metrics": (
        INPUT_DIR / "youtube_owned_video_metrics.json"
    ),
    "trend_signals": INPUT_DIR / "trend_signals.json",
    "build_journal": INPUT_DIR / "build_journal.json",
    "idea_candidates": INPUT_DIR / "idea_candidates.json",
    "empire_opportunity_ideas": (
        INPUT_DIR / "empire_opportunity_ideas.json"
    ),
    "empire_build_journal": (
        INPUT_DIR / "empire_build_journal.json"
    ),
    "research_pack_candidates": (
        INPUT_DIR / "research_pack_candidates.json"
    ),
    "verified_research_packs": (
        INPUT_DIR / "verified_research_packs.json"
    ),
    "canonical_content_candidates": (
        INPUT_DIR / "canonical_content_candidates.json"
    ),
    "script_brief_candidates": (
        INPUT_DIR / "script_brief_candidates.json"
    ),
}


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _records(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [dict(row) for row in value if isinstance(row, Mapping)]
    if isinstance(value, Mapping):
        for key in ("items", "records", "observations", "candidates", "signals"):
            rows = value.get(key)
            if isinstance(rows, list):
                return [
                    dict(row)
                    for row in rows
                    if isinstance(row, Mapping)
                ]
    return []


def _dedupe_records(
    rows: Iterable[Mapping[str, Any]],
    *,
    keys: tuple[str, ...],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    seen: set[str] = set()

    for raw in rows:
        row = dict(raw)
        identity = ""
        for key in keys:
            value = str(row.get(key) or "").strip()
            if value:
                identity = f"{key}:{value}"
                break
        if not identity:
            identity = json.dumps(row, sort_keys=True, default=str)
        if identity in seen:
            continue
        seen.add(identity)
        output.append(row)

    return output


def _refs(row: Mapping[str, Any]) -> tuple[str, ...]:
    values = row.get("evidence_refs")
    if isinstance(values, list):
        refs = tuple(
            str(value).strip()
            for value in values
            if str(value).strip()
        )
        if refs:
            return refs
    single = str(row.get("evidence_ref") or "").strip()
    return (single,) if single else ()


def _source_state(repo_root: Path) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, relative in INPUTS.items():
        path = repo_root / relative
        raw = _read_json(path)
        rows = _records(raw)
        result[key] = {
            "available": raw is not None,
            "record_count": len(rows),
            "path": str(relative),
        }
    return result


def _youtube_public_runtime(
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    views_by_channel: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        channel_id = str(
            row.get("channel_id")
            or (row.get("snippet") or {}).get("channelId")
            or ""
        ).strip()
        value = (
            row.get("views")
            if row.get("views") is not None
            else (row.get("statistics") or {}).get("viewCount")
        )
        try:
            views = float(value)
        except (TypeError, ValueError):
            continue
        if channel_id and views >= 0:
            views_by_channel[channel_id].append(views)

    baselines = {
        channel_id: build_channel_baseline(
            values,
            metric="views",
        )
        for channel_id, values in views_by_channel.items()
    }

    observations = []
    rejected = []
    for index, row in enumerate(rows):
        refs = _refs(row)
        if not refs:
            rejected.append({
                "index": index,
                "reason": "missing_evidence_refs",
            })
            continue

        channel_id = str(
            row.get("channel_id")
            or (row.get("snippet") or {}).get("channelId")
            or ""
        ).strip()
        try:
            observation = normalize_youtube_video_observation(
                row,
                evidence_refs=refs,
                owned_channel=False,
                channel_baseline=baselines.get(channel_id),
            )
        except (TypeError, ValueError) as exc:
            rejected.append({
                "index": index,
                "reason": str(exc),
            })
            continue
        observations.append(observation)

    outliers = build_outlier_candidates(observations)
    return {
        "observation_count": len(observations),
        "rejected_count": len(rejected),
        "rejected": rejected,
        "channel_baseline_count": sum(
            row.value is not None
            for row in baselines.values()
        ),
        "outliers": outliers,
        "observations": observations,
    }


def _owned_video_metrics_runtime(
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    normalized = []
    rejected = []

    for index, row in enumerate(rows):
        refs = _refs(row)
        if not refs:
            rejected.append({
                "index": index,
                "reason": "missing_evidence_refs",
            })
            continue
        try:
            item = normalize_owned_channel_analytics(
                row,
                evidence_refs=refs,
            )
        except (TypeError, ValueError) as exc:
            rejected.append({
                "index": index,
                "reason": str(exc),
            })
            continue
        normalized.append(item)

    totals = {
        "views": 0.0,
        "engaged_views": 0.0,
        "watch_time_minutes": 0.0,
        "subscribers_gained": 0.0,
        "subscribers_lost": 0.0,
    }
    known_counts = {key: 0 for key in totals}

    for item in normalized:
        metrics = item.get("metrics") or {}
        for key in totals:
            value = metrics.get(key)
            if value is None:
                continue
            totals[key] += float(value)
            known_counts[key] += 1

    observed_totals = {
        key: (
            round(value, 6)
            if known_counts[key] > 0
            else None
        )
        for key, value in totals.items()
    }

    return {
        "record_count": len(normalized),
        "rejected_count": len(rejected),
        "rejected": rejected,
        "observed_totals": observed_totals,
        "metrics": normalized,
        "platform_estimated_revenue_is_not_revenue_pulse_truth": True,
        "actual_revenue": False,
        "execution_authority": "none",
    }


def _owned_algorithm_runtime(
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    observations: list[DistributionObservation] = []
    rejected = []

    for index, row in enumerate(rows):
        refs = _refs(row)
        if not refs:
            rejected.append({
                "index": index,
                "reason": "missing_evidence_refs",
            })
            continue

        surface = str(row.get("surface") or "").strip().upper()
        if not surface:
            rejected.append({
                "index": index,
                "reason": "missing_surface",
            })
            continue

        try:
            observation = DistributionObservation(
                video_id=str(row.get("video_id") or "").strip(),
                surface=surface,
                evidence_refs=refs,
                impressions=row.get("impressions"),
                views=row.get("views"),
                engaged_views=row.get("engaged_views"),
                watch_time_minutes=row.get("watch_time_minutes"),
                average_view_duration_seconds=row.get(
                    "average_view_duration_seconds"
                ),
                average_view_percentage=row.get(
                    "average_view_percentage"
                ),
                subscribers_gained=row.get("subscribers_gained"),
                returning_viewers=row.get("returning_viewers"),
                source_video_id=(
                    str(row.get("source_video_id") or "").strip()
                    or None
                ),
                query=str(row.get("query") or "").strip() or None,
                audience_cluster_ref=(
                    str(row.get("audience_cluster_ref") or "").strip()
                    or None
                ),
            )
            observation.validate()
        except (TypeError, ValueError) as exc:
            rejected.append({
                "index": index,
                "reason": str(exc),
            })
            continue
        observations.append(observation)

    distribution = analyse_distribution(observations)
    recommendation_chain = build_recommendation_chain_packet(observations)

    by_video: dict[str, list[DistributionObservation]] = defaultdict(list)
    for row in observations:
        by_video[row.video_id].append(row)

    hypotheses = []
    for video_id, video_rows in sorted(by_video.items()):
        dist = analyse_distribution(video_rows)
        evidence_refs = sorted({
            ref
            for row in video_rows
            for ref in row.evidence_refs
        })
        hypotheses.append(
            build_algorithm_hypothesis_packet(
                video_id=video_id,
                distribution=dist,
                retention_ref=None,
                creative_package_ref=None,
                audience_cluster_ref=next(
                    (
                        row.audience_cluster_ref
                        for row in video_rows
                        if row.audience_cluster_ref
                    ),
                    None,
                ),
                evidence_refs=evidence_refs,
            )
        )

    return {
        "observation_count": len(observations),
        "rejected_count": len(rejected),
        "rejected": rejected,
        "distribution": distribution,
        "recommendation_chain": recommendation_chain,
        "hypothesis_count": len(hypotheses),
        "hypotheses": hypotheses,
    }


def _trend_runtime(
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    signals_by_topic: dict[str, list[MediaTrendSignal]] = defaultdict(list)
    rejected = []

    for index, row in enumerate(rows):
        refs = _refs(row)
        topic = str(row.get("topic") or "").strip()
        source_family = str(row.get("source_family") or "").strip()
        if not topic or not source_family or not refs:
            rejected.append({
                "index": index,
                "reason": "topic_source_family_and_evidence_required",
            })
            continue
        try:
            signal = MediaTrendSignal(
                topic=topic,
                source_family=source_family,
                velocity=row.get("velocity"),
                evidence_refs=refs,
                observed_at=(
                    str(row.get("observed_at") or "").strip() or None
                ),
                source_component=(
                    str(row.get("source_component") or "").strip()
                    or None
                ),
            )
            signal.validate()
        except (TypeError, ValueError) as exc:
            rejected.append({
                "index": index,
                "reason": str(exc),
            })
            continue
        signals_by_topic[topic].append(signal)

    fused = [
        fuse_media_trend(topic, signals)
        for topic, signals in sorted(signals_by_topic.items())
    ]
    return {
        "signal_count": sum(
            len(values)
            for values in signals_by_topic.values()
        ),
        "topic_count": len(fused),
        "rejected_count": len(rejected),
        "rejected": rejected,
        "topics": fused,
    }


def _build_journal_runtime(
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    candidates = []
    rejected = []

    for index, row in enumerate(rows):
        refs = _refs(row)
        try:
            entry = BuildJournalEntry(
                entry_id=str(row.get("entry_id") or "").strip(),
                system=str(row.get("system") or "").strip(),
                change=str(row.get("change") or "").strip(),
                problem=str(row.get("problem") or "").strip(),
                solution=str(row.get("solution") or "").strip(),
                evidence_refs=refs,
                before_refs=tuple(row.get("before_refs") or ()),
                after_refs=tuple(row.get("after_refs") or ()),
                screenshot_refs=tuple(row.get("screenshot_refs") or ()),
                metric_refs=tuple(row.get("metric_refs") or ()),
                business_relevance=(
                    str(row.get("business_relevance") or "").strip()
                    or None
                ),
                lessons=tuple(row.get("lessons") or ()),
                created_at=(
                    str(row.get("created_at") or "").strip()
                    or datetime.now(timezone.utc).isoformat()
                ),
            )
            entry.validate()
        except (TypeError, ValueError) as exc:
            rejected.append({
                "index": index,
                "reason": str(exc),
            })
            continue

        opportunity = content_opportunity_from_build(
            entry,
            novelty_observed=row.get("novelty_observed") is True,
            audience_relevance_observed=(
                row.get("audience_relevance_observed") is True
            ),
            demonstration_available=(
                row.get("demonstration_available") is True
            ),
            commercial_relevance_observed=(
                row.get("commercial_relevance_observed") is True
            ),
        )
        candidates.append(opportunity)

    return {
        "entry_count": len(candidates),
        "rejected_count": len(rejected),
        "rejected": rejected,
        "opportunity_candidate_count": sum(
            row.get("state") == "MEDIA_OPPORTUNITY_CANDIDATE"
            for row in candidates
        ),
        "items": candidates,
    }


def _idea_runtime(
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    candidates = []
    rejected = []

    for index, row in enumerate(rows):
        refs = _refs(row)
        source_systems = tuple(
            str(value).strip()
            for value in (row.get("source_systems") or ())
            if str(value).strip()
        )
        try:
            idea = MediaIdeaCandidate(
                idea_id=str(row.get("idea_id") or "").strip(),
                topic=str(row.get("topic") or "").strip(),
                angle=str(row.get("angle") or "").strip(),
                audience=str(row.get("audience") or "").strip(),
                evidence_refs=refs,
                source_systems=source_systems,
                format_candidates=tuple(
                    row.get("format_candidates") or ()
                ),
                product_refs=tuple(row.get("product_refs") or ()),
                opportunity_refs=tuple(
                    row.get("opportunity_refs") or ()
                ),
                content_franchise_candidate=(
                    str(
                        row.get("content_franchise_candidate") or ""
                    ).strip()
                    or None
                ),
            )
            candidate = idea.as_dict(
                opportunity_features=dict(
                    row.get("opportunity_features") or {}
                )
            )
        except (TypeError, ValueError) as exc:
            rejected.append({
                "index": index,
                "reason": str(exc),
            })
            continue

        # Quant review is intentionally not invented here. An adapter can add
        # a real quant packet later; until then this remains pending.
        candidate["quant_packet_ref"] = (
            str(row.get("quant_packet_ref") or "").strip() or None
        )
        candidate["quant_packet_status"] = (
            str(row.get("quant_packet_status") or "").strip()
            or "UNAVAILABLE"
        )
        candidate["commercial_quant_is_media_score"] = (
            row.get("commercial_quant_is_media_score") is True
        )
        candidate["source_context"] = (
            dict(row.get("source_context"))
            if isinstance(row.get("source_context"), Mapping)
            else {}
        )
        candidates.append(candidate)

    candidates.sort(
        key=lambda row: (
            -int(
                (row.get("opportunity_features") or {}).get(
                    "known_feature_count"
                ) or 0
            ),
            str(row.get("idea_id") or ""),
        )
    )

    return {
        "candidate_count": len(candidates),
        "rejected_count": len(rejected),
        "rejected": rejected,
        "pending_quant_review_count": sum(
            row.get("decision") == "PENDING_QUANT_REVIEW"
            for row in candidates
        ),
        "commercial_quant_available_count": sum(
            row.get("quant_packet_status") == "AVAILABLE"
            for row in candidates
        ),
        "scored_candidate_count": 0,
        "candidates": candidates,
        "ranking_note": (
            "sorted by observed feature completeness only; "
            "commercial/media score remains owned by Quant review"
        ),
    }


def build_media_os_runtime(repo_root: Path) -> dict[str, Any]:
    sources = _source_state(repo_root)

    public_rows = _records(
        _read_json(repo_root / INPUTS["youtube_public"])
    )
    owned_rows = _records(
        _read_json(repo_root / INPUTS["youtube_owned_analytics"])
    )
    owned_video_rows = _records(
        _read_json(repo_root / INPUTS["youtube_owned_video_metrics"])
    )
    trend_rows = _records(
        _read_json(repo_root / INPUTS["trend_signals"])
    )
    journal_rows = _dedupe_records(
        [
            *_records(
                _read_json(repo_root / INPUTS["build_journal"])
            ),
            *_records(
                _read_json(
                    repo_root / INPUTS["empire_build_journal"]
                )
            ),
        ],
        keys=("entry_id",),
    )
    idea_rows = _dedupe_records(
        [
            *_records(
                _read_json(repo_root / INPUTS["idea_candidates"])
            ),
            *_records(
                _read_json(
                    repo_root / INPUTS["empire_opportunity_ideas"]
                )
            ),
        ],
        keys=("idea_id",),
    )
    raw_research_pack_rows = _records(
        _read_json(
            repo_root / INPUTS["research_pack_candidates"]
        )
    )
    verified_research_rows = _records(
        _read_json(
            repo_root / INPUTS["verified_research_packs"]
        )
    )
    # Verified rows take precedence over their unverified source candidate
    # with the same research_id.
    research_pack_rows = _dedupe_records(
        [
            *verified_research_rows,
            *raw_research_pack_rows,
        ],
        keys=("research_id",),
    )
    canonical_content_rows = _dedupe_records(
        _records(
            _read_json(
                repo_root / INPUTS["canonical_content_candidates"]
            )
        ),
        keys=("content_id",),
    )
    script_brief_rows = _dedupe_records(
        _records(
            _read_json(
                repo_root / INPUTS["script_brief_candidates"]
            )
        ),
        keys=("content_id", "content_ref"),
    )

    youtube_public = _youtube_public_runtime(public_rows)
    owned_video_metrics = _owned_video_metrics_runtime(
        owned_video_rows
    )
    algorithm = _owned_algorithm_runtime(owned_rows)
    trends = _trend_runtime(trend_rows)
    journal = _build_journal_runtime(journal_rows)
    ideas = _idea_runtime(idea_rows)
    research_packs = {
        "candidate_count": len(research_pack_rows),
        "verified_pack_count": len(verified_research_rows),
        "verified_claim_count": sum(
            int(row.get("verified_claim_count") or 0)
            for row in research_pack_rows
        ),
        "script_ready_count": sum(
            row.get("script_ready") is True
            for row in research_pack_rows
        ),
        "claim_verification_required_count": sum(
            row.get("claim_verification_required") is True
            for row in research_pack_rows
        ),
        "candidates": research_pack_rows,
        "automatic_script_generation_authorized": False,
        "execution_authority": "none",
    }
    content_pipeline = {
        "canonical_content_candidate_count": len(
            canonical_content_rows
        ),
        "script_brief_candidate_count": len(
            script_brief_rows
        ),
        "script_prose_generated": False,
        "canonical_content_candidates": canonical_content_rows,
        "script_brief_candidates": script_brief_rows,
        "public_publish_authorized": False,
        "execution_authority": "none",
    }

    observed_source_count = sum(
        row["available"] and row["record_count"] > 0
        for row in sources.values()
    )

    return {
        "schema_version": "empire.media_os.runtime.v1",
        "mode": "OBSERVE",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "channel": {
            "internal_channel_ref": "empire-ai",
            "display_name": "EMPIRE AI",
            "external_youtube_channel_id": None,
            "external_channel_id_known": False,
            "flagship": True,
        },
        "source_state": sources,
        "observed_source_count": observed_source_count,
        "youtube_public": youtube_public,
        "owned_video_metrics": owned_video_metrics,
        "algorithm_intelligence": algorithm,
        "trend_fusion": trends,
        "build_journal": journal,
        "idea_backlog": ideas,
        "research_packs": research_packs,
        "content_pipeline": content_pipeline,
        "runtime_active": True,
        "real_evidence_present": observed_source_count > 0,
        "ready_for_research_generation": (
            ideas["candidate_count"] > 0
            or journal["opportunity_candidate_count"] > 0
            or trends["topic_count"] > 0
            or youtube_public["outliers"]["candidate_count"] > 0
        ),
        "ready_for_claim_verification": (
            research_packs["candidate_count"] > 0
            and research_packs["claim_verification_required_count"] > 0
        ),
        "ready_for_script_generation": (
            research_packs["script_ready_count"] > 0
        ),
        "ready_for_script_prose_generation": (
            content_pipeline["script_brief_candidate_count"] > 0
        ),
        "ready_for_storyboard_generation": False,
        "public_publish_authorized": False,
        "comment_publish_authorized": False,
        "new_channel_launch_authorized": False,
        "material_gpu_cloud_commitment_authorized": False,
        "database_write_performed": False,
        "external_action_performed": False,
        "actual_revenue": False,
        "execution_authority": "none",
    }


def refresh_media_os_runtime(repo_root: Path) -> dict[str, Any]:
    payload = build_media_os_runtime(repo_root)
    path = repo_root / OUTPUT
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)
    return payload
