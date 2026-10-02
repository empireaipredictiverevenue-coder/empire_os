#!/usr/bin/env python3
"""Recurring OBSERVE-only competitive intelligence refresh chain."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import time
from typing import Any, Callable, Mapping

from empire_os.competitor_account_brief import (
    build_account_brief_batch,
    write_account_brief_snapshot,
)
from empire_os.competitor_audience_research_executor import (
    execute_account_research,
    execute_snapshot_research,
    write_account_research_snapshot,
)
from empire_os.competitor_audience_runtime import (
    refresh_competitor_audience_snapshot,
)
from empire_os.competitor_ecosystem_mining import refresh_ecosystem_snapshot
from empire_os.competitor_intelligence_feed import refresh_feed_snapshot
from empire_os.competitor_market_opportunity import (
    refresh_market_opportunity_snapshot,
)
from empire_os.competitor_market_scale import (
    run_market_scale_sweep,
    write_market_scale_snapshot,
)
from empire_os.competitor_public_activity import (
    refresh_public_activity_snapshot,
)
from empire_os.competitor_public_review_overlap import (
    refresh_public_review_overlap_snapshot,
)
from empire_os.competitor_search_presence import (
    refresh_search_presence_snapshot,
)
from empire_os.intelligence_materializer_transport import (
    PostgresIntelligenceMaterializer,
)
from empire_os.opportunity_brief import (
    materialize_opportunity_briefs,
    write_opportunity_briefs,
)
from empire_os.predictive_cloud_status import refresh_predictive_cloud_status


OUTPUT = Path(
    "runtime/competitive_intelligence/refresh_chain_latest.json"
)
RESEARCH = Path(
    "runtime/competitive_intelligence/"
    "competitor_account_research_latest.json"
)
MARKET_CONFIG = Path("config/competitor_markets/denver_roofing.json")
MAX_AGE = timedelta(hours=2)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _parse_time(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _direct_hash_index(
    payload: Mapping[str, Any],
) -> dict[tuple[str, str], str]:
    rows: dict[tuple[str, str], str] = {}
    for action in payload.get("actions") or []:
        if not isinstance(action, Mapping):
            continue
        entity_id = str(action.get("entity_id") or "").strip()
        if not entity_id:
            continue
        for observation in action.get("observations") or []:
            if not isinstance(observation, Mapping):
                continue
            if observation.get("observation_type") not in {
                "public_first_party_page",
                "reobserved_public_evidence",
            }:
                continue
            url = str(observation.get("url") or "").strip()
            digest = str(
                observation.get("content_sha256") or ""
            ).strip()
            if url and digest:
                rows[(entity_id, url)] = digest
    return rows


def detect_page_changes(
    previous: Mapping[str, Any],
    current: Mapping[str, Any],
) -> dict[str, Any]:
    old = _direct_hash_index(previous)
    new = _direct_hash_index(current)
    changed = []
    added = []
    for key, digest in sorted(new.items()):
        previous_digest = old.get(key)
        if previous_digest is None:
            added.append({
                "entity_id": key[0],
                "url": key[1],
                "content_sha256": digest,
            })
        elif previous_digest != digest:
            changed.append({
                "entity_id": key[0],
                "url": key[1],
                "previous_content_sha256": previous_digest,
                "content_sha256": digest,
            })
    return {
        "tracked_page_count": len(new),
        "changed_page_count": len(changed),
        "new_page_count": len(added),
        "changed_pages": changed,
        "new_pages": added,
        "execution_authority": "none",
    }


def _run_stage(
    name: str,
    fn: Callable[[], Any],
    *,
    attempts: int = 1,
    critical: bool = False,
) -> tuple[dict[str, Any], Any]:
    errors = []
    started = time.monotonic()
    result = None
    used = 0
    for used in range(1, max(1, attempts) + 1):
        try:
            result = fn()
            break
        except Exception as exc:
            errors.append(
                f"{type(exc).__name__}: {str(exc)[:300]}"
            )
    ok = result is not None
    return ({
        "stage": name,
        "ok": ok,
        "critical": critical,
        "attempts": used,
        "errors": errors,
        "duration_ms": round(
            (time.monotonic() - started) * 1000,
            3,
        ),
    }, result)


def _run_change_research(
    audience: Mapping[str, Any],
    changes: Mapping[str, Any],
    *,
    search_fn: Callable[..., Any] | None,
    fetch_fn: Callable[..., Any] | None,
) -> list[dict[str, Any]]:
    changed_entities = list(dict.fromkeys(
        str(row.get("entity_id") or "").strip()
        for row in changes.get("changed_pages") or []
        if str(row.get("entity_id") or "").strip()
    ))[:3]
    if not changed_entities:
        return []

    companies = {
        str(row.get("entity_id") or "").strip(): row
        for row in audience.get("companies") or []
        if isinstance(row, Mapping)
    }
    contexts = {
        str(row.get("entity_id") or "").strip(): row
        for row in audience.get("omega_cortex_context") or []
        if isinstance(row, Mapping)
    }
    rows = []
    for entity_id in changed_entities:
        company = companies.get(entity_id)
        context = contexts.get(entity_id)
        if company is None or context is None:
            continue
        forced = dict(context)
        forced["next_best_research_action"] = "deep_account_research"
        kwargs: dict[str, Any] = {}
        if search_fn is not None:
            kwargs["search_fn"] = search_fn
        if fetch_fn is not None:
            kwargs["fetch_fn"] = fetch_fn
        rows.append(execute_account_research(
            company,
            forced,
            **kwargs,
        ))
    return rows


def refresh_competitive_intelligence_chain(
    repo_root: str | Path,
    *,
    writer: PostgresIntelligenceMaterializer | None = None,
    search_fn: Callable[..., Any] | None = None,
    fetch_fn: Callable[..., Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("now must include timezone")
    current = current.astimezone(timezone.utc)
    materializer = writer or PostgresIntelligenceMaterializer.from_env()
    previous_research = _read_json(root / RESEARCH)
    stages: list[dict[str, Any]] = []

    config = _read_json(root / MARKET_CONFIG)
    stage, market = _run_stage(
        "market_scale_sweep",
        lambda: run_market_scale_sweep(
            writer=materializer,
            config=config,
            persist=False,
            max_seeds=8,
        ),
        critical=False,
    )
    stages.append(stage)
    if market is not None:
        write_market_scale_snapshot(root, market)

    for name, callback in (
        (
            "ecosystem",
            lambda: refresh_ecosystem_snapshot(
                root, materializer, persist=False
            ),
        ),
        (
            "public_review_overlap",
            lambda: refresh_public_review_overlap_snapshot(
                root, materializer, persist=False
            ),
        ),
        (
            "public_activity",
            lambda: refresh_public_activity_snapshot(
                root, materializer, persist=False
            ),
        ),
    ):
        stage, _ = _run_stage(name, callback, critical=False)
        stages.append(stage)

    stage, _ = _run_stage(
        "search_presence",
        lambda: refresh_search_presence_snapshot(
            root,
            materializer,
            persist=False,
            public_only=True,
        ),
        attempts=2,
        critical=False,
    )
    stages.append(stage)

    for name, callback in (
        (
            "competitor_feed",
            lambda: refresh_feed_snapshot(root, materializer),
        ),
        (
            "market_opportunity",
            lambda: refresh_market_opportunity_snapshot(
                root, materializer
            ),
        ),
    ):
        stage, _ = _run_stage(name, callback, critical=False)
        stages.append(stage)

    stage, audience = _run_stage(
        "canonical_audience",
        lambda: refresh_competitor_audience_snapshot(
            root, materializer
        ),
        critical=True,
    )
    stages.append(stage)

    research = None
    changes = {
        "tracked_page_count": 0,
        "changed_page_count": 0,
        "new_page_count": 0,
        "changed_pages": [],
        "new_pages": [],
        "execution_authority": "none",
    }
    change_research: list[dict[str, Any]] = []
    account_briefs = None
    opportunity_briefs = None

    if audience is not None:
        research_kwargs: dict[str, Any] = {}
        if search_fn is not None:
            research_kwargs["search_fn"] = search_fn
        if fetch_fn is not None:
            research_kwargs["fetch_fn"] = fetch_fn

        stage, research = _run_stage(
            "account_research",
            lambda: execute_snapshot_research(
                audience,
                **research_kwargs,
            ),
            critical=True,
        )
        stages.append(stage)

    if research is not None:
        changes = detect_page_changes(
            previous_research,
            research,
        )
        change_research = _run_change_research(
            audience or {},
            changes,
            search_fn=search_fn,
            fetch_fn=fetch_fn,
        )
        research = dict(research)
        research["page_change_detection"] = changes
        research["research_on_change_triggered"] = bool(
            change_research
        )
        research["change_research_count"] = len(change_research)
        research["change_research"] = change_research
        write_account_research_snapshot(root, research)

        stage, account_briefs = _run_stage(
            "account_briefs",
            lambda: build_account_brief_batch(
                audience or {},
                research,
            ),
            critical=True,
        )
        stages.append(stage)
        if account_briefs is not None:
            write_account_brief_snapshot(root, account_briefs)

    if account_briefs is not None:
        stage, opportunity_briefs = _run_stage(
            "opportunity_briefs",
            lambda: materialize_opportunity_briefs(
                account_briefs
            ),
            critical=True,
        )
        stages.append(stage)
        if opportunity_briefs is not None:
            write_opportunity_briefs(root, opportunity_briefs)

    stage, predictive = _run_stage(
        "predictive_cloud_status",
        lambda: refresh_predictive_cloud_status(root),
        critical=True,
    )
    stages.append(stage)

    critical_failures = [
        row["stage"]
        for row in stages
        if row["critical"] and not row["ok"]
    ]
    degraded_stages = [
        row["stage"]
        for row in stages
        if not row["ok"]
    ]
    expires = current + MAX_AGE
    payload = {
        "schema_version": (
            "empire.competitive-intelligence-refresh-chain.v1"
        ),
        "mode": "OBSERVE_TO_REVIEW_ONLY",
        "generated_at": current.isoformat(),
        "expires_at": expires.isoformat(),
        "freshness": "FRESH",
        "ok": not critical_failures,
        "degraded": bool(degraded_stages),
        "critical_failures": critical_failures,
        "degraded_stages": degraded_stages,
        "stages": stages,
        "page_change_detection": changes,
        "research_on_change_triggered": bool(change_research),
        "change_research_count": len(change_research),
        "canonical_signal_row_count": int(
            (audience or {}).get(
                "canonical_signal_row_count"
            ) or 0
        ),
        "account_research_observation_count": int(
            (research or {}).get("observation_count") or 0
        ),
        "supported_claim_count": int(
            (account_briefs or {}).get(
                "supported_claim_count"
            ) or 0
        ),
        "blocked_claim_count": int(
            (account_briefs or {}).get(
                "blocked_claim_count"
            ) or 0
        ),
        "opportunity_brief_count": int(
            (opportunity_briefs or {}).get(
                "brief_count"
            ) or 0
        ),
        "review_ready_count": int(
            (opportunity_briefs or {}).get(
                "review_ready_count"
            ) or 0
        ),
        "predictive_cloud_refreshed": predictive is not None,
        "external_send_allowed": False,
        "payment_mutation": False,
        "revenue_recognition": False,
        "execution_authority": "none",
    }

    target = root / OUTPUT
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(target)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="/srv/empire_os")
    args = parser.parse_args()
    payload = refresh_competitive_intelligence_chain(
        args.repo_root
    )
    print(json.dumps(
        payload,
        indent=2,
        sort_keys=True,
    ))
    return 0 if payload["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
