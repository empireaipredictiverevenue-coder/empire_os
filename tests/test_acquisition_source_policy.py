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
    assert coverage["source"] == "overpass"
    assert intent["family"] == "intent"
    assert intent["source"] in {"reddit", "courtlistener"}
    assert coverage["next_family_index"] == 1



def test_source_policy_skips_quarantined_family(tmp_path):
    log = tmp_path / "crawler.jsonl"
    log.write_text("")

    choice = choose_source(
        {
            "next_family_index": 0,
            "source_states": {"overpass": "QUARANTINED"},
        },
        log_path=log,
    )

    assert choice["family"] == "intent"
    assert choice["source"] in {"reddit", "courtlistener"}
