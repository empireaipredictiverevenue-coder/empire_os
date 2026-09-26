import json

from empire_os.geo_registry import acquisition_markets
from empire_os.geo_scheduler import choose_market, recent_market_stats


def _write_runs(path):
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
    path.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n"
    )


def test_recent_market_stats_pairs_start_with_done(tmp_path):
    log = tmp_path / "crawler.jsonl"
    _write_runs(log)
    stats = recent_market_stats(log, source="overpass")
    assert stats["Dallas, TX"]["runs"] == 1
    assert stats["Dallas, TX"]["accepted"] == 25
    assert stats["Birmingham, AL"]["accepted"] == 1


def test_scheduler_balances_exploration_across_countries(tmp_path):
    log = tmp_path / "crawler.jsonl"
    _write_runs(log)
    markets = acquisition_markets()

    state = {
        "geo_cycle_count": 4,
        "next_country_index": 0,
        "country_market_cursors": {},
    }
    first = choose_market(
        markets,
        state=state,
        source="overpass",
        log_path=log,
    )
    assert first["policy"] == "explore_country_balanced"
    first_country = first["market"].country_code

    state = {
        "geo_cycle_count": 8,
        "next_country_index": first["next_country_index"],
        "country_market_cursors": first["country_market_cursors"],
    }
    second = choose_market(
        markets,
        state=state,
        source="overpass",
        log_path=log,
    )
    assert second["policy"] == "explore_country_balanced"
    assert second["market"].country_code != first_country


def test_scheduler_exploits_only_markets_with_observed_yield(tmp_path):
    log = tmp_path / "crawler.jsonl"
    _write_runs(log)
    result = choose_market(
        acquisition_markets(),
        state={
            "geo_cycle_count": 1,
            "next_country_index": 0,
            "country_market_cursors": {},
        },
        source="overpass",
        log_path=log,
    )
    assert result["policy"] == "exploit_observed_yield"
    assert result["market"].metro == "Dallas, TX"
    assert result["recent_stats"]["accepted"] == 25
