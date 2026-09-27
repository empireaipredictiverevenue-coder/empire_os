from pathlib import Path
from types import SimpleNamespace
import json

from empire_os.opportunity_ai_planner import plan_radar_opportunities


class FakeCoder:
    created = []

    def __init__(self, *args, **kwargs):
        pass

    def create_task(self, objective):
        self.__class__.created.append(objective)
        return SimpleNamespace(
            id=f"coder_task_{len(self.__class__.created)}"
        )


class FakeQueue:
    enqueued = []

    def __init__(self, *args, **kwargs):
        pass

    def enqueue(self, **kwargs):
        self.__class__.enqueued.append(kwargs)
        return SimpleNamespace(
            id=f"coder_job_{len(self.__class__.enqueued)}"
        )


def _write_inputs(root: Path):
    radar_path = root / "runtime/opportunity_radar/latest.json"
    research_path = root / "runtime/opportunity_radar/research_latest.json"
    radar_path.parent.mkdir(parents=True)
    radar_path.write_text(json.dumps({
        "candidates": [
            {
                "opportunity_key": "market:roofing:denver",
                "opportunity_class": "market_research",
                "title": "Roofing / Denver",
                "trigger": "observed_market_evidence",
                "observed_priority_score": 72,
                "evidence_refs": [
                    "canonical:one",
                    "canonical:two",
                ],
                "factory_blockers": [
                    "normalized_economics_required"
                ],
                "recommended_next_actions": [
                    "deepen_market_research"
                ],
            },
            {
                "opportunity_key": "community_pain:search_visibility",
                "opportunity_class": "community_pain",
                "title": "Search Visibility",
                "trigger": "observed_public_pain",
                "observed_priority_score": 65,
                "evidence_refs": ["https://example.com/1"],
                "factory_blockers": [
                    "canonical_buyer_intent_required"
                ],
                "recommended_next_actions": [
                    "collect_serp_evidence"
                ],
            },
        ]
    }))
    research_path.write_text(json.dumps({
        "actions": [{
            "opportunity_key": "market:roofing:denver",
            "observation_count": 2,
            "evidence_urls": [
                "https://example.com/market-1",
                "https://example.com/market-2",
            ],
        }]
    }))


def test_planner_queues_bounded_plan_jobs_and_no_execution(tmp_path):
    FakeCoder.created = []
    FakeQueue.enqueued = []
    _write_inputs(tmp_path)

    result = plan_radar_opportunities(
        tmp_path,
        limit=1,
        coder_factory=FakeCoder,
        queue_factory=FakeQueue,
    )

    assert result["queued_count"] == 1
    assert result["automatic_research_planning"] is True
    assert result["automatic_production_execution"] is False
    assert result["execution_authority"] == "none"
    assert result["research_observation_count"] == 2
    assert FakeQueue.enqueued[0]["kind"].value == "PLAN"
    assert "Do NOT send outreach" in FakeCoder.created[0]
    assert "public_search_observation_count=2" in FakeCoder.created[0]
    assert "market-1" in FakeCoder.created[0]


def test_unchanged_opportunity_is_not_requeued(tmp_path):
    FakeCoder.created = []
    FakeQueue.enqueued = []
    _write_inputs(tmp_path)

    first = plan_radar_opportunities(
        tmp_path,
        limit=10,
        coder_factory=FakeCoder,
        queue_factory=FakeQueue,
    )
    second = plan_radar_opportunities(
        tmp_path,
        limit=10,
        coder_factory=FakeCoder,
        queue_factory=FakeQueue,
    )

    assert first["queued_count"] == 2
    assert second["queued_count"] == 0
    assert second["skipped_unchanged"] == 2


def test_new_research_evidence_requeues_changed_opportunity(tmp_path):
    FakeCoder.created = []
    FakeQueue.enqueued = []
    _write_inputs(tmp_path)

    first = plan_radar_opportunities(
        tmp_path,
        limit=10,
        coder_factory=FakeCoder,
        queue_factory=FakeQueue,
    )
    assert first["queued_count"] == 2

    research_path = (
        tmp_path / "runtime/opportunity_radar/research_latest.json"
    )
    payload = json.loads(research_path.read_text())
    payload["actions"][0]["observation_count"] = 3
    payload["actions"][0]["evidence_urls"].append(
        "https://example.com/market-3"
    )
    research_path.write_text(json.dumps(payload))

    second = plan_radar_opportunities(
        tmp_path,
        limit=10,
        coder_factory=FakeCoder,
        queue_factory=FakeQueue,
    )

    assert second["queued_count"] == 1
    assert second["planned"][0]["opportunity_key"] == (
        "market:roofing:denver"
    )
