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


def test_scheduler_explores_on_every_fifth_cycle(tmp_path):
    log = tmp_path / "crawler.jsonl"
    _write_runs(log)
    markets = acquisition_markets()
    result = choose_market(
        markets,
        state={"geo_cycle_count": 5, "next_market_index": 3},
        source="overpass",
        log_path=log,
    )
    assert result["policy"] == "explore"
    assert result["market"] == markets[3]
    assert result["next_market_index"] == 4


def test_scheduler_exploits_proven_yield_between_exploration_cycles(tmp_path):
    log = tmp_path / "crawler.jsonl"
    _write_runs(log)
    result = choose_market(
        acquisition_markets(),
        state={"geo_cycle_count": 1, "next_market_index": 0},
        source="overpass",
        log_path=log,
    )
    assert result["policy"] == "exploit"
    assert result["market"].metro == "Dallas, TX"
    assert result["recent_stats"]["accepted"] == 25
