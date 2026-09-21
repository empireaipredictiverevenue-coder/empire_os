import json

from empire_os.acquisition_source_policy import choose_source


def test_source_policy_rotates_families_and_explores_underused(tmp_path):
    log = tmp_path / "crawler.jsonl"
    log.write_text("\n".join([
        json.dumps({
            "msg": "source_run_done",
            "source": "overpass",
            "accepted": 20,
            "errors": 0,
        })
        for _ in range(5)
    ]))

    coverage = choose_source(
        {"next_family_index": 0},
        log_path=log,
    )
    intent = choose_source(
        {"next_family_index": 1},
        log_path=log,
    )

    assert coverage["family"] == "coverage"
    assert coverage["source"] == "biz_search"
    assert intent["family"] == "intent"
    assert intent["source"] in {"reddit", "courtlistener"}
    assert coverage["next_family_index"] == 1



def test_source_policy_prefers_novel_yield_over_duplicate_acceptance(tmp_path):
    log = tmp_path / "crawler.jsonl"
    rows = []
    for _ in range(3):
        rows.extend([
            {
                "msg": "source_run_done",
                "source": "overpass",
                "accepted": 20,
                "errors": 0,
            },
            {
                "msg": "prospect_matched",
                "source": "overpass",
            },
            {
                "msg": "source_run_done",
                "source": "biz_search",
                "accepted": 1,
                "errors": 0,
            },
            {
                "msg": "prospect_acquired",
                "source": "biz_search",
            },
        ])
    log.write_text("\n".join(json.dumps(row) for row in rows))

    choice = choose_source(
        {"next_family_index": 0},
        log_path=log,
    )

    assert choice["source"] == "biz_search"
    assert choice["recent_stats"]["prospects"] == 3
