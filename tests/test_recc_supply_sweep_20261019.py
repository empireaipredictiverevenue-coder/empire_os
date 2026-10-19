"""Real source contract + rotating private research ledger, no live network."""
from datetime import datetime, timezone
import json
from pathlib import Path
import pytest

from empire_os.lead_sources import LeadCandidate
from empire_os.recc_supply_sweep import sweep_recc_members, BASE
from scripts.run_bounded_recc_solar_sweep_20261019 import main

NOW = datetime(2026, 10, 19, 14, tzinfo=timezone.utc)


def html():
    return '<html><body>' + ''.join(
        f'<a href="/scheme/members/member-{i}">Company {i} Solar Ltd</a>'
        for i in range(24)
    ) + '</body></html>'


def fake_fetch(url):
    if url.endswith("/robots.txt"):
        return "User-agent: *\nAllow: /\n"
    assert url.startswith(BASE + "/scheme/members?")
    return html()


def fake_detail(name, url):
    return LeadCandidate(
        name=name, phone="+442079460234", niche="solar",
        metro="United Kingdom", country_code="GB",
        source="recc_solar", lead_score=95, url=url,
        raw={
            "business_website": "https://business.example/",
            "recc_member_url": url,
            "sector": "Solar PV",
            "raw_resale_allowed": False,
        }
    )


def test_rotating_scans_add_distinct_private_research_not_exchange(tmp_path):
    results = [
        sweep_recc_members(
            tmp_path, now=NOW, fetch=fake_fetch,
            detail=fake_detail, sleep=lambda sec: None, batch_size=8
        ) for i in range(3)
    ]
    assert [r["unique_research_observations"] for r in results] == [8, 16, 24]
    assert [r["new_unique_research_observations"] for r in results] == [8, 8, 8]
    assert [r["next_cursor"] for r in results] == [8, 16, 0]
    assert all(r["verified_canonical_prospect_additions"] == 0 for r in results)
    assert all(r["commercial_exchange_inventory_added"] == 0 for r in results)
    assert all(r["outbound_authorized"] is False for r in results)
    data = json.loads((tmp_path / "internal_observations.json").read_text())
    assert len(data["observations"]) == 24
    assert all(x["verified_canonical_prospect_id"] is None for x in data["observations"])
    assert all(x["source_raw_resale_allowed"] is False for x in data["observations"])
    assert tmp_path.stat().st_mode & 0o777 == 0o700
    assert (tmp_path / "internal_observations.json").stat().st_mode & 0o777 == 0o600


def test_daily_cap_refuses_fifth_sweep(tmp_path):
    counts = [
        sweep_recc_members(
            tmp_path, now=NOW, fetch=fake_fetch,
            detail=fake_detail, sleep=lambda sec: None
        ) for _ in range(5)
    ]
    assert counts[-2]["details_today"] == 32
    assert counts[-1]["state"] == "DAILY_SOURCE_BUDGET_EXHAUSTED"
    assert counts[-1]["existing_unique_research_observations"] == 24
    assert len(json.loads((tmp_path / "internal_observations.json").read_text())["observations"]) == 24


def test_next_utc_day_resets_request_budget_not_ledger(tmp_path):
    from datetime import timedelta
    for _ in range(4):
        sweep_recc_members(tmp_path, now=NOW, fetch=fake_fetch,
                           detail=fake_detail, sleep=lambda sec: None)
    new_day = sweep_recc_members(
        tmp_path, now=NOW + timedelta(days=1),
        fetch=fake_fetch, detail=fake_detail, sleep=lambda sec: None,
    )
    assert new_day["details_today"] == 8
    assert new_day["unique_research_observations"] == 24
    assert new_day["new_unique_research_observations"] == 0


def test_robots_disallow_holds_without_state_files(tmp_path):
    def denied(url):
        if url.endswith("/robots.txt"):
            return "User-agent: *\nDisallow: /scheme/members\n"
        return html()
    with pytest.raises(ValueError, match="robots_disallowed"):
        sweep_recc_members(tmp_path, now=NOW, fetch=denied,
                           detail=fake_detail, sleep=lambda sec: None)
    assert not (tmp_path / "internal_observations.json").exists()
    assert not (tmp_path / "latest.json").exists()
    reserved = json.loads((tmp_path / "state.json").read_text())
    assert reserved["details_today"] == 8


def test_no_detail_exception_leaks_and_budget_counts_attempt(tmp_path):
    def failing(name, url):
        raise RuntimeError("private data should never leak")
    result = sweep_recc_members(tmp_path, now=NOW, fetch=fake_fetch,
                                detail=failing, sleep=lambda sec: None)
    assert result["state"] == "COMPLETED_WITH_SOURCE_ERRORS"
    assert result["source_detail_failures_this_sweep"] == 8
    assert result["new_unique_research_observations"] == 0
    assert "private data" not in json.dumps(result)
    assert result["details_today"] == 8


def test_source_contract_rejects_unknown_business_rows(tmp_path):
    def consumer_record(name, url):
        return LeadCandidate(name="Individual claimant", source="reddit",
                             niche="solar", metro="London", url=url)
    result = sweep_recc_members(tmp_path, now=NOW, fetch=fake_fetch,
                                detail=consumer_record, sleep=lambda sec: None)
    assert result["unique_research_observations"] == 0
    assert result["commercial_exchange_inventory_added"] == 0


def test_cli_is_not_implicitly_activated(tmp_path, capsys):
    with pytest.raises(SystemExit) as err:
        main(["--root", str(tmp_path)])
    assert err.value.code == 2


def test_fetch_blocks_unregistered_hosts():
    from empire_os.recc_supply_sweep import _fetch
    with pytest.raises(ValueError):
        _fetch("https://evil.example/robots.txt")
    with pytest.raises(ValueError):
        _fetch("http://www.recc.org.uk/robots.txt")


def test_interrupted_directory_fetch_reserves_daily_budget(tmp_path):
    calls = []
    def fail_after_robots(url):
        calls.append(url)
        if url.endswith("/robots.txt"):
            return "User-agent: *\\nAllow: /\\n"
        raise TimeoutError("simulated interrupted member page fetch")
    for expected_count in (8, 16, 24, 32):
        with pytest.raises(TimeoutError):
            sweep_recc_members(
                tmp_path, now=NOW, fetch=fail_after_robots,
                detail=fake_detail, sleep=lambda sec: None
            )
        saved = json.loads((tmp_path / "state.json").read_text())
        assert saved["details_today"] == expected_count
    result = sweep_recc_members(
        tmp_path, now=NOW, fetch=fail_after_robots,
        detail=fake_detail, sleep=lambda sec: None
    )
    assert result["state"] == "DAILY_SOURCE_BUDGET_EXHAUSTED"
    assert len(calls) == 8
    assert not (tmp_path / "internal_observations.json").exists()
