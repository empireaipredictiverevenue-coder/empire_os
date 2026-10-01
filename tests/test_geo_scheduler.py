import json

from empire_os.geo_registry import acquisition_markets
from empire_os.geo_scheduler import choose_market, recent_market_stats


def _runs(path):
    rows = [
        {
            "msg": "crawler_run_start",
            "source": "overpass",
            "metro": "Dallas, TX",
        },
        {
            "msg": "crawler_run_done",
            "accepted": 25,
            "errors": 0,
        },
        {
            "msg": "crawler_run_start",
            "source": "overpass",
            "metro": "Birmingham, AL",
        },
        {
            "msg": "crawler_run_done",
            "accepted": 1,
            "errors": 0,
        },
    ]
    path.write_text("\n".join(json.dumps(x) for x in rows))


def test_stats(tmp_path):
    p = tmp_path / "l"
    _runs(p)
    s = recent_market_stats(p, source="overpass")
    assert s["Dallas, TX"]["accepted"] == 25


def test_global_source_80_20(tmp_path):
    p = tmp_path / "l"
    p.write_text("")
    state = {"country_market_cursors": {}}
    countries = []

    for cycle in range(10):
        state["geo_cycle_count"] = cycle
        r = choose_market(
            acquisition_markets(),
            state=state,
            source="overpass",
            log_path=p,
        )
        countries.append(r["market"].country_code)
        state["country_market_cursors"] = r[
            "country_market_cursors"
        ]

    assert sum(x == "US" for x in countries) == 8
    assert sum(x != "US" for x in countries) == 2


def test_us_markets_rotate(tmp_path):
    p = tmp_path / "l"
    p.write_text("")

    a = choose_market(
        acquisition_markets(),
        state={
            "geo_cycle_count": 0,
            "country_market_cursors": {},
        },
        source="overpass",
        log_path=p,
    )

    b = choose_market(
        acquisition_markets(),
        state={
            "geo_cycle_count": 5,
            "country_market_cursors":
                a["country_market_cursors"],
        },
        source="overpass",
        log_path=p,
    )

    assert a["market"].country_code == "US"
    assert b["market"].country_code == "US"
    assert a["market"].market_id != b["market"].market_id


def test_nws_is_us_only(tmp_path):
    p = tmp_path / "l"
    p.write_text("")
    r = choose_market(
        acquisition_markets(),
        state={"geo_cycle_count": 4},
        source="nws_alerts",
        log_path=p,
    )
    assert r["market"].country_code == "US"


def test_global_source_can_go_international(tmp_path):
    p = tmp_path / "l"
    p.write_text("")
    r = choose_market(
        acquisition_markets(),
        state={"geo_cycle_count": 4},
        source="overpass",
        log_path=p,
    )
    assert r["target_bucket"] == "INTL"
    assert r["market"].country_code != "US"


def test_fixed_specialist_geography(tmp_path):
    p = tmp_path / "l"
    p.write_text("")

    ny = choose_market(
        acquisition_markets(),
        state={"geo_cycle_count": 4},
        source="permits",
        log_path=p,
    )
    chi = choose_market(
        acquisition_markets(),
        state={"geo_cycle_count": 4},
        source="chicago_311",
        log_path=p,
    )

    assert ny["market"].market_id == "US-NY"
    assert chi["market"].market_id == "US-IL"


def test_healthy_observed_market_wins(tmp_path):
    p = tmp_path / "l"
    _runs(p)

    r = choose_market(
        acquisition_markets(),
        state={
            "geo_cycle_count": 1,
            "country_market_cursors": {},
        },
        source="overpass",
        log_path=p,
    )

    assert r["market"].metro == "Dallas, TX"
