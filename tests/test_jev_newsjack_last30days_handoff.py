"""Isolated source-contract tests: no production records or network calls."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import subprocess
import sys

import pytest

from empire_os.jev_newsjack_adapters import signals_from_last30days_research_handoff
from empire_os.jev_newsjack_traffic import review_newsjack_jev_traffic

NOW = datetime(2026, 11, 16, 18, tzinfo=timezone.utc)
TOPIC = "AI agents for small businesses"


def packet():
    observation = {
        "source_ref": "last30days:source:fixture",
        "source_url": "https://news.ycombinator.com/item?id=123",
        "source_type": "hackernews",
        "published_at": (NOW - timedelta(days=1)).isoformat(),
        "rights": "PUBLIC_RESEARCH_REFERENCE_ONLY",
        **{k: False for k in ("claim_verified", "buyer_intent_verified",
            "local_geography_verified", "topic_relevance_verified", "source_text_executable")},
    }
    return {
        "schema_version": "empire.last30days.research_handoff.v1",
        "generated_at": NOW.isoformat(), "mode": "OBSERVE", "execution_authority": "none",
        **{k: False for k in ("external_action_authorized", "public_publish_authorized",
            "database_write_authorized", "revenue_recognized",
            "buyer_intent_or_search_volume_from_engagement")},
        "topic_count": 1, "source_observation_count": 1,
        "topics": [{"topic": TOPIC, "candidate_observation_count": 1,
            "review_status": "REQUIRES_INDEPENDENT_TOPIC_RELEVANCE_AND_FACT_CHECK",
            "observations": [observation]}],
    }


def intake(p, **kwargs):
    return signals_from_last30days_research_handoff(
        p, topic=kwargs.get("topic", TOPIC), sector="ai", market="GB",
        as_of=kwargs.get("as_of", NOW.isoformat()))


def test_original_citations_scope_and_replay_identity_preserved_without_mutation():
    p = packet()
    before = deepcopy(p)
    result = intake(p)
    row = result["signals"][0]
    assert row["evidence_refs"] == [p["topics"][0]["observations"][0]["source_ref"]]
    assert row["title_is_article_headline"] is False
    assert row["research_scope_verified"] is False
    assert row["independent_corroboration_verified"] is False
    assert row["destination_live_verified"] is False
    assert result["lookback_days"] == 30
    assert p == before
    p["generated_at"] = (NOW - timedelta(minutes=1)).isoformat()
    assert intake(p)["signals"][0]["signal_id"] == row["signal_id"]
    reviewed = review_newsjack_jev_traffic(result["signals"], as_of=NOW.isoformat(),
        approved_sectors=["ai"], approved_markets=["GB"])
    assert reviewed["status_counts"] == {"RESEARCH_REVIEW": 1}
    assert reviewed["candidates"][0]["actual_revenue"] is False


@pytest.mark.parametrize("field,value", [
    ("schema_version", "wrong"), ("topic_count", True),
    ("source_observation_count", 99), ("execution_authority", "publish"),
    ("revenue_recognized", True), ("public_publish_authorized", True),
    ("generated_at", (NOW + timedelta(seconds=1)).isoformat()),
    ("generated_at", (NOW - timedelta(hours=3)).isoformat()),
])
def test_untrusted_handoff_fails_closed(field, value):
    p = packet()
    p[field] = value
    with pytest.raises(ValueError):
        intake(p)


@pytest.mark.parametrize("field,value", [
    ("source_url", "http://localhost/secret"),
    ("source_url", "https://user:password@example.com/private"),
    ("published_at", NOW.date().isoformat()),
    ("published_at", (NOW + timedelta(seconds=1)).isoformat()),
    ("published_at", (NOW - timedelta(days=31)).isoformat()),
    ("source_ref", "untrusted"), ("source_type", "invented"),
    ("source_text_executable", True), ("buyer_intent_verified", True),
    ("rights", "UNKNOWN"),
])
def test_invalid_source_rows_are_counted_and_excluded(field, value):
    p = packet()
    p["topics"][0]["observations"][0][field] = value
    result = intake(p)
    assert result["signals"] == []
    assert result["rejected_count"] == 1


def test_reused_reference_deduplicated_and_unknown_topic_not_inferred():
    p = packet()
    p["topics"][0]["observations"] *= 2
    p["topics"][0]["candidate_observation_count"] = p["source_observation_count"] = 2
    result = intake(p)
    assert result["mapped_count"] == result["duplicate_count"] == 1
    with pytest.raises(ValueError):
        intake(p, topic="roofing")


def test_thirty_day_research_does_not_bypass_seven_day_news_gate():
    p = packet()
    p["topics"][0]["observations"][0]["published_at"] = (NOW - timedelta(days=20)).isoformat()
    result = intake(p)
    assert result["mapped_count"] == 1
    reviewed = review_newsjack_jev_traffic(result["signals"], as_of=NOW.isoformat(),
        approved_sectors=["ai"], approved_markets=["GB"])
    assert reviewed["status_counts"] == {"HOLD_EVIDENCE": 1}


def test_existing_cli_consumes_handoff_without_source_writes(tmp_path):
    source = tmp_path / "source.json"
    source.write_text(json.dumps(packet()))
    before = source.read_bytes()
    args = [sys.executable, "-B", "-m", "scripts.review_jev_newsjack_traffic",
        "--input", str(source), "--input-format", "last30days-handoff",
        "--topic", TOPIC, "--sector", "ai", "--market", "GB", "--as-of", NOW.isoformat()]
    run = subprocess.run(args, capture_output=True, text=True, timeout=15)
    assert run.returncode == 0, run.stderr
    assert json.loads(run.stdout)["source_intake"]["mapped_count"] == 1
    assert source.read_bytes() == before
    alias = tmp_path / "alias.json"
    alias.symlink_to(source)
    args[args.index(str(source))] = str(alias)
    assert subprocess.run(args, capture_output=True, timeout=15).returncode != 0
