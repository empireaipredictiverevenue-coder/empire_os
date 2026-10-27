import json
from pathlib import Path

import pytest

from empire_os.media_last30days_search_profiles import (
    SEARCH_BY_TOPIC, ENABLED_TOPIC_PROFILES, enabled_plan_json, plan_for_approved_topic, plan_json,
)
from empire_os.media_last30days_cycle import _run_keyless


def test_all_four_original_topics_have_bounded_single_source_queries():
    assert len(SEARCH_BY_TOPIC) == 4
    for topic in SEARCH_BY_TOPIC:
        plan = plan_for_approved_topic(topic)
        assert plan["intent"] == "concept"
        assert len(plan["subqueries"]) == 1
        sq = plan["subqueries"][0]
        assert sq["sources"] == ["reddit", "hackernews"]
        assert len(sq["search_query"]) <= 68
        assert sq["ranking_query"] == topic
        assert "--" not in sq["search_query"]
        assert json.loads(plan_json(topic)) == plan


@pytest.mark.parametrize("topic", [
    "", "roofing", "AI agent", "AI lead generation for roofing contractors ",
    None, object(),
])
def test_fail_closed_unknown_topics_never_form_search_plan(topic):
    with pytest.raises(ValueError):
        plan_json(topic)


def test_keyless_runner_passes_explicit_plan_without_secrets_or_browser(tmp_path, monkeypatch):
    import empire_os.media_last30days_cycle as cycle
    script = tmp_path / "empire_os/skills_library/last30days/scripts/last30days.py"
    script.parent.mkdir(parents=True)
    script.write_text("# marker only")
    calls = []

    def run(command, *, cwd, capture_output, text, timeout, env, check):
        calls.append((command, cwd, capture_output, timeout, env))
        class R:
            returncode = 0
            stdout = '{"engine":"last30days","fixture":true}'
        return R()

    monkeypatch.setattr(cycle.subprocess, "run", run)
    monkeypatch.setenv("DO_NOT_LEAK_API_KEY", "TOPSECRET")
    topic = "AI lead generation for roofing contractors"
    result = _run_keyless(tmp_path, topic)
    assert result["fixture"] is True
    command, cwd, capture_output, timeout, env = calls[0]
    assert command[command.index("--plan") + 1] == plan_json(topic)
    assert command[command.index("--search") + 1] == "reddit,hackernews"
    assert "--quick" in command and "--no-browser-cookies" in command
    assert "--store" not in command and "--publish" not in command
    assert timeout <= 55 and cwd == str(tmp_path)
    assert "DO_NOT_LEAK_API_KEY" not in env
    assert env["HOME"] == "/nonexistent"


def test_current_engine_sanitizer_keeps_exact_search_and_source_caps():
    import sys
    root = Path(__file__).resolve().parents[1]
    src = root / "empire_os/skills_library/last30days/scripts"
    sys.path.insert(0, str(src))
    try:
        from lib import planner
        for topic in SEARCH_BY_TOPIC:
            plan = planner._sanitize_plan(
                plan_for_approved_topic(topic),
                topic, ["reddit", "hackernews"],
                ["reddit", "hackernews"], "quick",
            )
            assert len(plan.subqueries) == 1
            assert plan.subqueries[0].search_query == SEARCH_BY_TOPIC[topic]
            assert plan.subqueries[0].sources == ["reddit", "hackernews"]
    finally:
        sys.path.remove(str(src))


def test_only_live_improved_roofing_profile_enabled():
    assert ENABLED_TOPIC_PROFILES == frozenset({"AI lead generation for roofing contractors"})
    assert enabled_plan_json("AI lead generation for roofing contractors")
    assert enabled_plan_json("AI sales avatars and digital sales agents") is None
    assert enabled_plan_json("first-party revenue intelligence and attribution") is None
    assert enabled_plan_json("AI agents for small businesses") is None
