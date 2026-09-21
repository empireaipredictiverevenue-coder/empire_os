import json
from datetime import datetime, timezone

from empire_os.acquisition_soak_summary import build_soak_summary


def test_soak_summary_counts_evidence_in_exact_window(tmp_path):
    expiry = int(
        datetime(
            2026, 9, 21, 20, 0, tzinfo=timezone.utc
        ).timestamp()
    )
    log = tmp_path / "crawler.jsonl"
    inbox = tmp_path / "signals.json"
    rows = [
        {
            "ts": "2026-09-21T10:00:00+0000",
            "msg": "crawler_run_start",
            "source": "overpass",
            "metro": "Dallas, TX",
        },
        {
            "ts": "2026-09-21T10:00:03+0000",
            "msg": "prospect_acquired",
            "prospect_id": "p1",
            "source": "overpass_osm",
        },
        {
            "ts": "2026-09-21T10:00:04+0000",
            "msg": "crawler_run_done",
            "candidates": 3,
            "accepted": 1,
            "errors": 0,
        },
        {
            "ts": "2026-09-21T11:00:00+0000",
            "msg": "crawler_run_start",
            "source": "permits",
            "metro": "NYC",
        },
        {
            "ts": "2026-09-21T11:00:02+0000",
            "msg": "signal_queued",
            "signal_id": "s1",
            "source": "permits_nyc",
        },
        {
            "ts": "2026-09-21T11:00:03+0000",
            "msg": "crawler_run_done",
            "candidates": 2,
            "accepted": 2,
            "errors": 0,
        },
    ]
    log.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n"
    )
    inbox.write_text(json.dumps({
        "s1": {
            "signal_id": "s1",
            "source": "permits_nyc",
            "status": "resolved",
            "created_at": "2026-09-21T11:00:02+00:00",
        }
    }))

    result = build_soak_summary(
        crawler_log=log,
        signal_inbox=inbox,
        expiry_epoch=expiry,
    )
    assert result["crawler_runs_completed"] == 2
    assert result["crawler_candidates_seen"] == 5
    assert result["accepted_event_total"] == 3
    assert result["crawler_errors"] == 0
    assert result["unique_canonical_prospects_observed"] == 1
    assert result["unique_signals_observed"] == 1
    assert result["source_runs"] == {
        "overpass": 1,
        "permits": 1,
    }
    assert result["signal_statuses_at_summary"] == {
        "resolved": 1,
    }
    assert result["actual_revenue"] is False
