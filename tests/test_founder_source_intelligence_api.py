import json

from empire_os.founder_source_intelligence_api import _latest_source_run


def test_latest_source_run_keeps_canonical_prospects_without_niche(tmp_path):
    log_path = tmp_path / "crawler_runs.jsonl"
    rows = [
        {
            "ts": "2026-09-23T19:50:23+0000",
            "msg": "crawler_run_start",
            "source": "recc_solar",
            "dry_run": False,
            "canonical_store": "supabase",
            "max_candidates": 20,
        },
        {
            "ts": "2026-09-23T19:50:24+0000",
            "msg": "prospect_acquired",
            "source": "recc_solar",
            "name": "Example Solar Ltd",
            "decision": "created",
            "prospect_id": "prospect-1",
            "country_code": "GB",
            "language_code": "en-GB",
            "timezone": "Europe/London",
        },
        {
            "ts": "2026-09-23T19:50:30+0000",
            "msg": "crawler_run_done",
            "candidates": 1,
            "accepted": 1,
            "errors": 0,
        },
    ]
    log_path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")

    proof = _latest_source_run(
        log_path,
        source="recc_solar",
        niche="solar",
    )

    assert proof["available"] is True
    assert proof["candidate_count"] == 1
    assert proof["candidates"][0]["name"] == "Example Solar Ltd"
    assert proof["candidates"][0]["niche"] == "solar"
    assert proof["run_result"] == {
        "candidates": 1,
        "accepted": 1,
        "errors": 0,
    }
