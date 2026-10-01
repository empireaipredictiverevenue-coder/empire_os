import json

from empire_os.acquisition_source_policy import (
    choose_source,
    recent_source_stats,
    source_health,
)


def _run(source, useful=0, errors=0):
    rows = [{"msg": "source_run_start", "source": source}]
    rows += [
        {"msg": "signal_queued", "source": source}
        for _ in range(useful)
    ]
    rows.append({
        "msg": "source_run_done",
        "source": source,
        "accepted": useful,
        "errors": errors,
    })
    return rows


def test_match_is_not_new_yield(tmp_path):
    p = tmp_path / "log.jsonl"
    rows = [
        {"msg": "source_run_start", "source": "overpass"},
        {"msg": "prospect_matched", "source": "overpass"},
        {
            "msg": "source_run_done",
            "source": "overpass",
            "accepted": 1,
            "errors": 0,
        },
    ]
    p.write_text("\n".join(json.dumps(x) for x in rows))
    s = recent_source_stats(p)["overpass"]
    assert s["matches"] == 1
    assert s["prospects"] == 0
    assert s["zero_yield_runs"] == 1


def test_signal_is_useful_yield(tmp_path):
    p = tmp_path / "log.jsonl"
    p.write_text(
        "\n".join(
            json.dumps(x)
            for x in _run("courtlistener", 3)
        )
    )
    s = recent_source_stats(p)["courtlistener"]
    assert s["signals"] == 3
    assert s["productive_runs"] == 1


def test_productive_beats_zero_yield(tmp_path):
    p = tmp_path / "log.jsonl"
    rows = []
    for _ in range(8):
        rows += _run("reddit")
    for _ in range(3):
        rows += _run("courtlistener", 3)

    p.write_text("\n".join(json.dumps(x) for x in rows))

    c = choose_source(
        {
            "next_family_index": 1,
            "geo_cycle_count": 1,
            "source_states": {
                "overpass": "QUARANTINED",
                "permits": "QUARANTINED",
                "chicago_311": "QUARANTINED",
                "nyc_hpd": "QUARANTINED",
                "nws_alerts": "QUARANTINED",
            },
        },
        log_path=p,
    )
    assert c["source"] == "courtlistener"


def test_errors_reduce_health():
    good = {
        "runs": 4,
        "prospects": 4,
        "signals": 0,
        "errors": 0,
        "zero_yield_runs": 0,
    }
    bad = dict(good, errors=4)
    assert source_health(good) > source_health(bad)


def test_bounded_exploration(tmp_path):
    p = tmp_path / "log.jsonl"
    rows = []
    for _ in range(20):
        rows += _run("nws_alerts")
    p.write_text("\n".join(json.dumps(x) for x in rows))

    c = choose_source(
        {
            "next_family_index": 3,
            "geo_cycle_count": 11,
        },
        log_path=p,
    )
    assert c["source"] == "nws_alerts"
    assert c["exploration"] is True


def test_quarantine_is_fail_closed(tmp_path):
    p = tmp_path / "log.jsonl"
    p.write_text("")
    c = choose_source(
        {
            "next_family_index": 0,
            "geo_cycle_count": 11,
            "source_states": {"overpass": "QUARANTINED"},
        },
        log_path=p,
    )
    assert c["source"] != "overpass"
