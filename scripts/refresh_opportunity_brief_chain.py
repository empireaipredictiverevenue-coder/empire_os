#!/usr/bin/env python3
"""Refresh canonical account evidence through to review-only opportunity briefs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable

from empire_os.competitor_account_brief import (
    build_account_brief_batch,
    write_account_brief_snapshot,
)
from empire_os.competitor_audience_research_executor import (
    execute_snapshot_research,
    write_account_research_snapshot,
)
from empire_os.competitor_audience_runtime import (
    refresh_competitor_audience_snapshot,
)
from empire_os.intelligence_materializer_transport import (
    PostgresIntelligenceMaterializer,
)
from empire_os.opportunity_brief import (
    materialize_opportunity_briefs,
    write_opportunity_briefs,
)


def refresh_opportunity_brief_chain(
    repo_root: str | Path,
    *,
    writer: PostgresIntelligenceMaterializer | None = None,
    search_fn: Callable[..., Any] | None = None,
    fetch_fn: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    materializer = writer or PostgresIntelligenceMaterializer.from_env()

    audience = refresh_competitor_audience_snapshot(root, materializer)

    research_kwargs: dict[str, Any] = {}
    if search_fn is not None:
        research_kwargs["search_fn"] = search_fn
    if fetch_fn is not None:
        research_kwargs["fetch_fn"] = fetch_fn

    research = execute_snapshot_research(audience, **research_kwargs)
    write_account_research_snapshot(root, research)

    account_briefs = build_account_brief_batch(audience, research)
    write_account_brief_snapshot(root, account_briefs)

    opportunity_briefs = materialize_opportunity_briefs(account_briefs)
    paths = write_opportunity_briefs(root, opportunity_briefs)

    return {
        "schema_version": "empire.opportunity-brief-refresh-chain.v1",
        "mode": "OBSERVE_TO_REVIEW_ONLY",
        "canonical_signal_row_count": int(
            audience.get("canonical_signal_row_count") or 0
        ),
        "canonical_latest_observed_at": audience.get("latest_observed_at"),
        "account_research_generated_at": research.get("generated_at"),
        "account_research_observation_count": int(
            research.get("observation_count") or 0
        ),
        "account_brief_count": int(account_briefs.get("brief_count") or 0),
        "supported_claim_count": int(
            account_briefs.get("supported_claim_count") or 0
        ),
        "blocked_claim_count": int(
            account_briefs.get("blocked_claim_count") or 0
        ),
        "opportunity_brief_count": int(
            opportunity_briefs.get("brief_count") or 0
        ),
        "review_ready_count": int(
            opportunity_briefs.get("review_ready_count") or 0
        ),
        "paths": [str(path) for path in paths],
        "external_send_allowed": False,
        "payment_mutation": False,
        "revenue_recognition": False,
        "execution_authority": "none",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="/srv/empire_os")
    args = parser.parse_args()
    payload = refresh_opportunity_brief_chain(args.repo_root)
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
