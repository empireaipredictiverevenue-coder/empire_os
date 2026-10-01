import pytest

import scripts.run_acquisition_cycle as cycle
from empire_os.acquisition_source_policy import (
    SOURCE_FAMILIES,
    choose_source,
)


def test_transient_exclusion_prevents_reselection(tmp_path):
    log = tmp_path / "crawler.jsonl"
    log.write_text("")

    first = choose_source(
        {
            "next_family_index": 1,
            "geo_cycle_count": 1,
        },
        log_path=log,
    )

    second = choose_source(
        {
            "next_family_index": 1,
            "geo_cycle_count": 1,
        },
        log_path=log,
        excluded_sources={first["source"]},
    )

    assert second["source"] != first["source"]


def test_all_sources_excluded_fails_closed(tmp_path):
    log = tmp_path / "crawler.jsonl"
    log.write_text("")

    all_sources = {
        source
        for family in SOURCE_FAMILIES.values()
        for source in family
    }

    with pytest.raises(
        RuntimeError,
        match="no eligible acquisition sources remain",
    ):
        choose_source(
            {},
            log_path=log,
            excluded_sources=all_sources,
        )


def test_fallback_passes_failed_source_as_exclusion(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        cycle,
        "LATEST",
        tmp_path / "latest.json",
    )

    seen = []

    results = [
        {
            "source": "courtlistener",
            "source_family": "intent",
            "returncode": 1,
            "ok": False,
        },
        {
            "source": "permits",
            "source_family": "property",
            "returncode": 0,
            "ok": True,
            "outreach_enabled": False,
            "payment_enabled": False,
        },
    ]

    def fake_run_cycle(
        *,
        max_candidates,
        excluded_sources=(),
    ):
        seen.append(set(excluded_sources))
        return results.pop(0)

    monkeypatch.setattr(
        cycle,
        "run_cycle",
        fake_run_cycle,
    )

    result = cycle.run_cycle_with_fallback(
        max_candidates=5,
        max_attempts=2,
    )

    assert seen == [
        set(),
        {"courtlistener"},
    ]

    assert result["ok"] is True
    assert result["attempted_sources"] == [
        "courtlistener",
        "permits",
    ]


def test_reusing_failed_source_is_hard_failure(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        cycle,
        "LATEST",
        tmp_path / "latest.json",
    )

    def broken_run_cycle(
        *,
        max_candidates,
        excluded_sources=(),
    ):
        return {
            "source": "courtlistener",
            "source_family": "intent",
            "returncode": 1,
            "ok": False,
        }

    monkeypatch.setattr(
        cycle,
        "run_cycle",
        broken_run_cycle,
    )

    with pytest.raises(
        RuntimeError,
        match="reused excluded source",
    ):
        cycle.run_cycle_with_fallback(
            max_candidates=5,
            max_attempts=2,
        )

def test_run_cycle_preserves_persistent_source_states(
    tmp_path,
    monkeypatch,
):
    import json
    from types import SimpleNamespace

    monkeypatch.setattr(
        cycle,
        "RUNTIME",
        tmp_path,
    )
    monkeypatch.setattr(
        cycle,
        "STATE",
        tmp_path / "state.json",
    )
    monkeypatch.setattr(
        cycle,
        "LATEST",
        tmp_path / "latest.json",
    )
    monkeypatch.setattr(
        cycle,
        "LAST_SUCCESS",
        tmp_path / "last_success.json",
    )
    monkeypatch.setattr(
        cycle,
        "LOCK",
        tmp_path / "cycle.lock",
    )

    monkeypatch.delenv(
        "EMPIRE_ACQUISITION_COUNTRIES",
        raising=False,
    )
    monkeypatch.delenv(
        "EMPIRE_ACQUISITION_MARKET_SET",
        raising=False,
    )

    persistent_states = {
        "courtlistener": "QUARANTINED",
    }

    monkeypatch.setattr(
        cycle,
        "_load_state",
        lambda: {
            "next_family_index": 0,
            "geo_cycle_count": 0,
            "source_states": persistent_states,
        },
    )

    market = SimpleNamespace(
        market_id="US-TEST",
        country_code="US",
        region_code="TX",
        language_code="en-US",
        timezone="America/Chicago",
        metro="Test, TX",
        base_priority=1.0,
    )

    monkeypatch.setattr(
        cycle,
        "acquisition_markets",
        lambda countries=None: [market],
    )

    monkeypatch.setattr(
        cycle,
        "choose_source",
        lambda state, *, log_path, excluded_sources=(): {
            "source": "nws_alerts",
            "family": "event",
            "next_family_index": 0,
            "policy": "test",
            "recent_stats": {},
            "score": 1.0,
            "exploration": False,
            "excluded_sources": list(excluded_sources),
        },
    )

    monkeypatch.setattr(
        cycle,
        "choose_market",
        lambda markets, *, state, source, log_path: {
            "market": market,
            "market_index": 0,
            "next_market_index": 0,
            "next_country_index": 0,
            "country_market_cursors": {},
            "geo_cycle_count": 1,
            "policy": "test",
            "target_bucket": "US",
            "compatibility": {
                "compatible": True,
            },
            "score": 1.0,
            "recent_stats": {},
        },
    )

    class Completed:
        returncode = 0
        stdout = (
            '{"msg":"crawler_run_done",'
            '"accepted":0,"errors":0}\n'
        )
        stderr = ""

    monkeypatch.setattr(
        cycle.subprocess,
        "run",
        lambda *args, **kwargs: Completed(),
    )

    result = cycle.run_cycle(
        max_candidates=1,
    )

    assert result["ok"] is True

    persisted = json.loads(
        cycle.STATE.read_text()
    )

    assert persisted["source_states"] == (
        persistent_states
    )

