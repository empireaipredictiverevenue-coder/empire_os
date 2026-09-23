#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from empire_os.media_runtime import refresh_media_os_runtime


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="/srv/empire_os")
    args = parser.parse_args()

    payload = refresh_media_os_runtime(
        Path(args.repo_root).resolve()
    )

    print(json.dumps({
        "ok": True,
        "schema_version": payload["schema_version"],
        "generated_at": payload["generated_at"],
        "observed_source_count": payload["observed_source_count"],
        "real_evidence_present": payload["real_evidence_present"],
        "youtube_observation_count": (
            payload["youtube_public"]["observation_count"]
        ),
        "outlier_candidate_count": (
            payload["youtube_public"]["outliers"]["candidate_count"]
        ),
        "owned_video_metric_count": (
            payload["owned_video_metrics"]["record_count"]
        ),
        "algorithm_observation_count": (
            payload["algorithm_intelligence"]["observation_count"]
        ),
        "trend_topic_count": payload["trend_fusion"]["topic_count"],
        "build_journal_opportunity_count": (
            payload["build_journal"]["opportunity_candidate_count"]
        ),
        "idea_candidate_count": (
            payload["idea_backlog"]["candidate_count"]
        ),
        "ready_for_research_generation": (
            payload["ready_for_research_generation"]
        ),
        "public_publish_authorized": False,
        "external_action_performed": False,
        "actual_revenue": False,
        "execution_authority": "none",
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
