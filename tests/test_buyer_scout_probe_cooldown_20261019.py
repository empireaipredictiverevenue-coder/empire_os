"""No repeated probes on the owned fallback; no buyer/send rights granted."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json

import pytest

from empire_os.buyer_scout_probe_cooldown import (
    load_probe_history, merge_observed_probes, save_probe_history,
)
from scripts.run_resilient_buyer_scout_20261019 import reviewed_seed_records

NOW = datetime(2026, 10, 19, 19, 50, tzinfo=timezone.utc)


def scout_at(*domains, age_minutes=0, score=0.8):
    return {
        "schema_version": "empire.buyer_acquisition_scout.v1",
        "generated_at": (NOW-timedelta(minutes=age_minutes)).isoformat(),
        "mode": "OBSERVE", "execution_authority": "none",
        "outbound_sent": False,
        "candidates": [
            {"domain": domain, "business_name_source": "first_party_site_identity",
             "site_evidence_score": score}
            for domain in domains
        ],
    }


def seeds(*names):
    return {
        "schema_version": "empire.buyer_qualification_actions.v1",
        "mode": "OBSERVE", "outbound_enabled": False,
        "outbound_sent": False,
        "targets": [
            {"domain": domain, "outbound_authorized": False,
             "existing_first_party_source_urls": []}
            for domain in names
        ],
    }


def test_first_party_evidence_cached_and_skipped_for_24h(tmp_path):
    old = scout_at("alpha.com", age_minutes=5)
    history = merge_observed_probes({}, old, now=NOW)
    assert list(history) == ["alpha.com"]
    path = tmp_path / "history.json"
    save_probe_history(path, history)
    assert path.stat().st_mode & 0o777 == 0o600
    recent = load_probe_history(path, now=NOW)
    chosen = reviewed_seed_records(
        seeds("alpha.com", "beta.com", "gamma.com"),
        limit=3, rotation=0, recently_probed_domains=set(recent))
    assert [v["domain"] for v in chosen] == ["beta.com", "gamma.com"]


def test_no_unobserved_candidate_cooldown():
    assert merge_observed_probes({}, scout_at("alpha.com", score=0), now=NOW) == {}
    old = scout_at("alpha.com")
    old["candidates"][0]["business_name_source"] = "canonical_prospect_seed"
    assert merge_observed_probes({}, old, now=NOW) == {}


def test_expired_cache_releases_research_after_24h(tmp_path):
    path = tmp_path / "cache.json"
    save_probe_history(path, {"alpha.com": (NOW - timedelta(hours=25)).isoformat()})
    assert load_probe_history(path, now=NOW) == {}


def test_no_repeat_when_all_seeds_recent():
    args=seeds("alpha.com", "beta.com")
    result=reviewed_seed_records(
        args, limit=8, rotation=4,
        recently_probed_domains={"alpha.com", "beta.com"})
    assert result == []


@pytest.mark.parametrize("bad", [
    {"schema_version":"wrong","last_probed_at":{}},
    {"schema_version":"empire.buyer_scout_probe_cooldown.v1","last_probed_at":{"not valid":NOW.isoformat()}},
    {"schema_version":"empire.buyer_scout_probe_cooldown.v1","last_probed_at":{"alpha.com":"naive"}},
])
def test_malformed_persistent_history_holds(tmp_path, bad):
    path = tmp_path / "history.json"
    path.write_text(json.dumps(bad))
    with pytest.raises(ValueError):
        load_probe_history(path, now=NOW)


def test_untrusted_scout_cannot_fill_history():
    data = scout_at("alpha.com")
    data["outbound_sent"] = True
    with pytest.raises(ValueError):
        merge_observed_probes({}, data, now=NOW)


def test_preserve_history_no_pii_in_cache(tmp_path):
    data = scout_at("alpha.com")
    data["candidates"][0]["first_party_emails"]=["private@alpha.com"]
    cache = merge_observed_probes({}, data, now=NOW)
    path = tmp_path / "history.json"
    save_probe_history(path,cache)
    assert "private@" not in path.read_text()
    assert "alpha.com" in path.read_text()
