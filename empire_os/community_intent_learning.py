"""Bounded, provenance-aware ICP source learning: research only, never revenue.

Existing Cortex and Economic Memory retain authority over actual conversion
labels. This journal learns which permitted *public sources* yield novel,
relevant observations and what safe research task to review next.
"""
from __future__ import annotations
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping, Sequence
from empire_os.icp_intent_relevance import classify_icp_intent

SCHEMA = "empire.icp_research_learning.v1"
MAX_EPISODES = 512


def source_id(item: tuple[str, str, str, str]) -> str:
    return "|".join(item).casefold()


def load_history(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    if path.is_symlink() or path.stat().st_size > 2500000:
        raise ValueError("unsafe_learning_file")
    raw = json.loads(path.read_text())
    if not isinstance(raw, dict) or raw.get("schema_version") != SCHEMA:
        raise ValueError("invalid_learning_schema")
    rows = raw.get("episodes")
    if not isinstance(rows, list) or len(rows) > MAX_EPISODES:
        raise ValueError("invalid_learning_history")
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("episode_id"), str):
            raise ValueError("invalid_learning_episode")
        if row["episode_id"] in seen or len(row["episode_id"]) != 64:
            raise ValueError("duplicated_or_invalid_episode")
        seen.add(row["episode_id"])
        if type(row.get("slot")) is not int or row["slot"] < 0:
            raise ValueError("invalid_learning_slot")
        if type(row.get("retrieval_ok")) is not bool:
            raise ValueError("invalid_learning_proof")
        for k in ("unique_new_posts", "explicit_requests", "operator_problems", "seller_pitches"):
            if type(row.get(k)) is not int or not 0 <= row[k] <= 1000:
                raise ValueError("invalid_learning_count")
    return rows


def select_source(
    sources: Sequence[tuple[str, str, str, str]],
    episodes: Sequence[Mapping[str, Any]], *, slot: int,
) -> tuple[str, str, str, str]:
    if not sources:
        raise ValueError("no_public_sources")
    stats = {}
    for episode in episodes:
        if episode.get("slot", slot) >= slot:
            continue
        s = stats.setdefault(episode["source_id"], {"n": 0, "latest": -1, "quality": 0.0})
        s["n"] += 1
        s["latest"] = max(s["latest"], episode["slot"])
        s["quality"] += (
            2 * episode["explicit_requests"] + episode["operator_problems"]
            + .25 * episode["unique_new_posts"] - episode["seller_pitches"]
            - (0 if episode["retrieval_ok"] else 1)
        )
    # Cold-start every new ICP venue before exploiting a noisy high-scoring post.
    untried = [(i, x) for i, x in enumerate(sources) if source_id(x) not in stats]
    if untried:
        cursor = slot % len(sources)
        return min(untried, key=lambda pair: (pair[0]-cursor) % len(sources))[1]
    # Hard starvation bound: every configured community is rechecked even
    # if another source had a historically high (unverified) discussion score.
    overdue = [
        (slot - stats[source_id(row)]["latest"], (i-slot) % len(sources), row)
        for i, row in enumerate(sources)
        if slot - stats[source_id(row)]["latest"] >= 3 * len(sources)
    ]
    if overdue:
        return sorted(overdue, key=lambda r: (-r[0], r[1]))[0][2]
    choices = []
    for i, row in enumerate(sources):
        s = stats[source_id(row)]
        age = max(0, slot - s["latest"] - 1)
        score = (s["quality"] / s["n"]) + min(8, age / len(sources)) * .75
        choices.append((-round(score, 5), (i-slot) % len(sources), row))
    return sorted(choices, key=lambda pair: (pair[0], pair[1]))[0][2]


def record_episode(
    episodes: Sequence[Mapping[str, Any]], *, source: tuple[str, str, str, str],
    slot: int, retrieval_ok: bool, observations: Sequence[Any],
    previously_observed_urls: set[str], now: datetime,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    key = source_id(source)
    episode_id = sha256(f"public_reddit_rss:{slot}:{key}".encode()).hexdigest()
    for prior in episodes:
        if prior["episode_id"] == episode_id:
            return [dict(x) for x in episodes], dict(prior)
    seen = set()
    classes = Counter()
    external = 0
    for row in observations:
        data = row if isinstance(row, Mapping) else row.as_dict()
        url = data.get("url")
        if not isinstance(url, str) or url in previously_observed_urls or url in seen:
            continue
        seen.add(url)
        c = classify_icp_intent(data)["intent_class"]
        classes[c] += 1
        external += bool(data.get("evidence_urls"))
    if classes["EXPLICIT_REQUEST_UNVERIFIED"]:
        action = "FOUNDER_REVIEW_UNATTRIBUTED_REQUESTS"
    elif classes["OPERATOR_PROBLEM_SELF_REPORTED"]:
        action = "REVIEW_ICP_PROBLEM_PRODUCT_FIT"
    elif not retrieval_ok:
        action = "REPAIR_OR_DEFER_SOURCE"
    else:
        action = "RESEARCH_NEXT_ICP_SOURCE"
    episode = {
        "episode_id": episode_id, "source_id": key, "slot": slot,
        "observed_at": now.astimezone(timezone.utc).isoformat(),
        "retrieval_ok": bool(retrieval_ok),
        "unique_new_posts": len(seen),
        "explicit_requests": classes["EXPLICIT_REQUEST_UNVERIFIED"],
        "operator_problems": classes["OPERATOR_PROBLEM_SELF_REPORTED"],
        "seller_pitches": classes["SELLER_PITCH"],
        "external_citations_not_identity_proof": external,
        "next_research_task": action,
        "task_status": "EVIDENCE_RECORDED",
        "buyer_identity_verified": False, "payment_verified": False,
        "outbound_authorized": False,
    }
    return ([dict(x) for x in episodes] + [episode])[-MAX_EPISODES:], episode


def snapshot(
    episodes: Sequence[Mapping[str, Any]],
    sources: Sequence[tuple[str, str, str, str]], *,
    now: datetime, latest: Mapping[str, Any], next_source: tuple[str, str, str, str],
) -> dict[str, Any]:
    source_results = []
    for src in sources:
        rows = [r for r in episodes if r["source_id"] == source_id(src)]
        source_results.append({
            "source_id": source_id(src),
            "attempted_cycles": len(rows),
            "successful_retrievals": sum(r["retrieval_ok"] for r in rows),
            "new_posts": sum(r["unique_new_posts"] for r in rows),
            "explicit_requests_unverified": sum(r["explicit_requests"] for r in rows),
            "operator_problems_unverified": sum(r["operator_problems"] for r in rows),
            "seller_pitches": sum(r["seller_pitches"] for r in rows),
        })
    return {
        "schema_version": SCHEMA,
        "generated_at": now.astimezone(timezone.utc).isoformat(),
        "mode": "OBSERVE",
        "learning_scope": "public_source_selection_only",
        "episodes": list(episodes)[-MAX_EPISODES:],
        "episode_count": len(episodes),
        "source_results": source_results,
        "latest_episode": dict(latest),
        "next_research_task": latest["next_research_task"],
        "next_research_source": source_id(next_source),
        "actual_revenue_learning": "REQUIRES_VERIFIED_CORTEX_AND_ECONOMIC_MEMORY",
        "verified_buyer_conversions": 0, "recognized_revenue_cents": None,
        "self_modifying_code": False, "outbound_execution": False,
        "spend_execution": False, "execution_authority": "NONE",
    }


def write_snapshot(path: Path, payload: Mapping[str, Any]) -> None:
    if path.is_symlink() or path.parent.is_symlink():
        raise ValueError("unsafe_learning_destination")
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(payload, sort_keys=True, indent=2) + "\n")
    temp = path.with_suffix(".json.tmp")
    temp.write_text(data)
    temp.replace(path)
