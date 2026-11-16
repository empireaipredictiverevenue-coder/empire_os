"""Scheduled research context cannot authorize or supply revenue forecasts."""
from datetime import datetime, timedelta, timezone
import json

import pytest

from scripts.run_predictive_revenue_runtime_observer import review_newsjack_research, run

NOW = datetime(2026, 11, 16, 18, tzinfo=timezone.utc)
TOPIC = "first-party revenue intelligence and attribution"
ENV = {
    "EMPIRE_PREDICTIVE_NEWSJACK_RESEARCH_ENABLED": "1",
    "EMPIRE_PREDICTIVE_NEWSJACK_RESEARCH_SECTOR": "ai",
    "EMPIRE_PREDICTIVE_NEWSJACK_RESEARCH_MARKET": "GB",
}


def source(root):
    p = root / "runtime/media_os/last30days/research_handoff_latest.json"
    p.parent.mkdir(parents=True)
    data = {
        "schema_version": "empire.last30days.research_handoff.v1",
        "generated_at": NOW.isoformat(), "mode": "OBSERVE", "execution_authority": "none",
        **{k: False for k in ("external_action_authorized", "public_publish_authorized",
            "database_write_authorized", "revenue_recognized", "buyer_intent_or_search_volume_from_engagement")},
        "topic_count": 1, "source_observation_count": 1,
        "topics": [{"topic": TOPIC, "candidate_observation_count": 1,
            "review_status": "REQUIRES_INDEPENDENT_TOPIC_RELEVANCE_AND_FACT_CHECK",
            "observations": [{"source_ref": "last30days:source:fixture",
                "source_url": "https://news.ycombinator.com/item?id=123",
                "source_type": "hackernews", "published_at": (NOW-timedelta(days=1)).isoformat(),
                "rights": "PUBLIC_RESEARCH_REFERENCE_ONLY",
                **{k: False for k in ("claim_verified", "buyer_intent_verified", "local_geography_verified",
                    "topic_relevance_verified", "source_text_executable")}}]}],
    }
    p.write_text(json.dumps(data))
    return p


def test_existing_observer_consumes_real_contract_without_forecast_or_source_write(tmp_path):
    p = source(tmp_path)
    before = p.read_bytes()
    result = run(root=tmp_path, now=NOW, write=False, producer_environment=ENV)
    research = result["newsjack_research"]
    assert research["status"] == "ORIGINAL_LAST30DAYS_NEWSJACK_RESEARCH_REVIEWED"
    assert research["topics"][0]["status_counts"] == {"RESEARCH_REVIEW": 1}
    assert research["topics"][0]["source_references"] == ["last30days:source:fixture"]
    assert research["revenue_model_input_authorized"] is False
    assert research["forecast_registered"] is False
    assert result["candidate_count"] == 0
    assert result["governance"]["db_write"] is False
    assert p.read_bytes() == before
    assert not (tmp_path/"runtime/predictive_revenue_control").exists()


@pytest.mark.parametrize("failure", ["missing", "malformed", "stale", "symlink", "forged"])
def test_research_failure_is_visible_and_does_not_break_original_observer(tmp_path, failure):
    p = source(tmp_path)
    if failure == "missing":
        p.unlink()
    elif failure == "malformed":
        p.write_text("[1,2]")
    elif failure == "stale":
        d = json.loads(p.read_text()); d["generated_at"] = (NOW-timedelta(hours=3)).isoformat()
        p.write_text(json.dumps(d))
    elif failure == "symlink":
        target = tmp_path/"original.json"; p.rename(target); p.symlink_to(target)
    else:
        d = json.loads(p.read_text()); d["revenue_recognized"] = True
        p.write_text(json.dumps(d))
    result = run(root=tmp_path, now=NOW, write=False, producer_environment=ENV)
    assert result["newsjack_research"]["status"] == "SOURCE_OR_ADAPTER_UNAVAILABLE_HOLD"
    assert result["candidate_count"] == 0
    assert result["governance"]["db_write"] is False


def test_explicit_activation_and_research_scope_required(tmp_path):
    source(tmp_path)
    assert review_newsjack_research(tmp_path, {}, now=NOW)["status"] == "DISABLED"
    assert review_newsjack_research(tmp_path, {next(iter(ENV)): "1"}, now=NOW)["status"] == "EXPLICIT_RESEARCH_SCOPE_REQUIRED"
