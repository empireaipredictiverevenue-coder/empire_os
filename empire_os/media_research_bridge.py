"""Bridge canonical Opportunity Research into Media OS research packs.

Opportunity Research search results are evidence candidates, not verified
facts. This bridge creates source-bearing, claimless Media research packs that
must pass a later claim-verification step before factual scripting.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from empire_os.media_research_pack import (
    MediaResearchPack,
    MediaResearchSource,
)


OPPORTUNITY_RESEARCH = Path(
    "runtime/opportunity_radar/research_latest.json"
)
OUTPUT = Path(
    "runtime/media_os/input/research_pack_candidates.json"
)


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _clean(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _stable_id(prefix: str, value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}:{digest}"


def _source_ref(opportunity_key: str, url: str) -> str:
    return _stable_id(
        "media-research-source",
        f"{opportunity_key}|{url}",
    )


def build_media_research_candidates(
    research: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if not isinstance(research, Mapping):
        return {
            "schema_version": "empire.media.research_candidates.v1",
            "mode": "OBSERVE",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_available": False,
            "candidate_count": 0,
            "source_observation_count": 0,
            "verified_claim_count": 0,
            "script_ready_count": 0,
            "candidates": [],
            "search_observations_are_verified_facts": False,
            "execution_authority": "none",
        }

    generated_at = (
        _clean(research.get("generated_at"))
        or datetime.now(timezone.utc).isoformat()
    )
    actions = (
        research.get("actions")
        if isinstance(research.get("actions"), list)
        else []
    )

    candidates = []
    source_observation_count = 0

    for raw in actions:
        if not isinstance(raw, Mapping):
            continue
        key = _clean(raw.get("opportunity_key"))
        title = _clean(raw.get("title"))
        if not key or not title:
            continue

        sources = []
        snippets = []
        seen_urls: set[str] = set()

        for observation in raw.get("observations") or []:
            if not isinstance(observation, Mapping):
                continue
            if observation.get("observation_type") != "public_search_result":
                continue
            url = _clean(observation.get("url"))
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            source_observation_count += 1

            source_ref = _source_ref(key, url)
            sources.append(
                MediaResearchSource(
                    source_ref=source_ref,
                    source_type="public_search_result",
                    observed_at=generated_at,
                    lineage_ref=url,
                    rights_state="RESEARCH_REFERENCE_ONLY",
                )
            )
            snippet = _clean(observation.get("snippet"))
            if snippet:
                snippets.append({
                    "source_ref": source_ref,
                    "snippet": snippet,
                    "verified_fact": False,
                })

        if not sources:
            continue

        pack = MediaResearchPack(
            research_id=_stable_id("media-research", key),
            topic=title,
            thesis=(
                "Research objective: verify the observed evidence and "
                f"implications around {title}."
            ),
            audience="founders and operators",
            sources=tuple(sources),
            claims=(),
            examples=(),
            counterarguments=(),
            screenshot_refs=(),
            product_evidence_refs=(),
            empire_data_refs=(f"opportunity_radar:{key}",),
            uncertainty=(
                "Public search observations are evidence candidates, not "
                "verified factual claims.",
                "Demand, buyer intent, causal impact and revenue remain "
                "unknown unless supported by separate canonical evidence.",
            ),
            generated_at=generated_at,
        ).as_dict()

        pack.update({
            "opportunity_key": key,
            "opportunity_class": raw.get("opportunity_class"),
            "planned_query_count": raw.get("planned_query_count"),
            "query_count": len(raw.get("queries") or []),
            "queries": list(raw.get("queries") or []),
            "source_observation_count": len(sources),
            "source_snippets": snippets,
            "verified_claim_count": 0,
            "claim_verification_required": True,
            "script_ready": False,
            "source_observations_are_verified_facts": False,
            "automatic_script_generation_authorized": False,
            "execution_authority": "none",
        })
        candidates.append(pack)

    return {
        "schema_version": "empire.media.research_candidates.v1",
        "mode": "OBSERVE",
        "generated_at": generated_at,
        "source_available": True,
        "candidate_count": len(candidates),
        "source_observation_count": source_observation_count,
        "verified_claim_count": 0,
        "script_ready_count": 0,
        "candidates": candidates,
        "search_observations_are_verified_facts": False,
        "automatic_script_generation_authorized": False,
        "public_publish_authorized": False,
        "actual_revenue": False,
        "execution_authority": "none",
    }


def refresh_media_research_bridge(
    repo_root: Path,
) -> dict[str, Any]:
    payload = build_media_research_candidates(
        _read_json(repo_root / OPPORTUNITY_RESEARCH)
    )
    path = repo_root / OUTPUT
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)
    return {
        **payload,
        "written_path": str(path.relative_to(repo_root)),
        "external_action_performed": False,
        "database_write_performed": False,
    }
