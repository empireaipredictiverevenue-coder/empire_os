from datetime import datetime, timezone
import json
import pytest

from empire_os.community_intent_learning import (
    load_history, record_episode, select_source, snapshot, source_id,
    write_snapshot,
)

NOW = datetime(2026, 10, 9, 22, tzinfo=timezone.utc)
SOURCES = (
    ("Roofing", "need more leads", "roofing", "US"),
    ("HVAC", "lead generation", "hvac", "US"),
    ("LawFirm", "marketing clients", "law", "US"),
)


def observation(url, title, text="", pains=None, evidence=None):
    return {
        "url": url, "title": title, "text": text,
        "pain_points": pains or ["lead_generation"],
        "evidence_urls": evidence or [],
    }


def run(episodes, *, source=SOURCES[0], slot=100, ok=True, observations=(), previous=()):
    return record_episode(
        episodes, source=source, slot=slot, retrieval_ok=ok,
        observations=observations, previously_observed_urls=set(previous), now=NOW,
    )


def test_cold_start_samples_all_icp_communities():
    episodes = []
    chosen = []
    for slot in range(100, 103):
        src = select_source(SOURCES, episodes, slot=slot)
        assert src not in chosen
        chosen.append(src)
        episodes, _ = run(episodes, source=src, slot=slot)
    assert set(chosen) == set(SOURCES)


def test_source_learning_recognizes_operator_request_without_conversion():
    episodes, event = run([], observations=[
        observation("https://reddit.com/r/Roofing/abc",
                    "Looking for a roofing lead company",
                    "We run a roofing company and need more qualified appointments"),
    ])
    assert event["unique_new_posts"] == 1
    assert event["explicit_requests"] == 1
    assert event["next_research_task"] == "FOUNDER_REVIEW_UNATTRIBUTED_REQUESTS"
    report = snapshot(episodes, SOURCES, now=NOW, latest=event,
                      next_source=SOURCES[1])
    assert report["recognized_revenue_cents"] is None
    assert report["verified_buyer_conversions"] == 0
    assert report["outbound_execution"] is False
    assert report["self_modifying_code"] is False


def test_generic_marketing_seller_cannot_create_a_buying_signal():
    _, event = run([], observations=[
        observation("https://reddit.com/r/Roofing/abcd",
                    "We help roofing companies sell leads. DM me today"),
    ])
    assert event["seller_pitches"] == 1
    assert event["explicit_requests"] == 0
    assert event["next_research_task"] == "RESEARCH_NEXT_ICP_SOURCE"


def test_de_duplicate_web_observations_and_cycle_replay():
    rows = [
        observation("https://reddit.com/r/roofing/x", "Need customers"),
        observation("https://reddit.com/r/roofing/x", "Need customers"),
        observation("https://reddit.com/r/roofing/previous", "More calls"),
    ]
    first, a = run([], observations=rows, previous={"https://reddit.com/r/roofing/previous"})
    assert a["unique_new_posts"] == 1
    second, b = run(first, observations=rows)
    assert second == first
    assert b == a
    assert len(second) == 1
    third, c = run(first, slot=101, observations=rows,
                   previous={"https://reddit.com/r/roofing/x",
                             "https://reddit.com/r/roofing/previous"})
    assert len(third) == 2
    assert c["unique_new_posts"] == 0


def test_failure_generates_repair_task_not_an_outbound_action():
    _, event = run([], ok=False)
    assert event["next_research_task"] == "REPAIR_OR_DEFER_SOURCE"
    assert event["buyer_identity_verified"] is False
    assert event["outbound_authorized"] is False


def test_fairness_prevents_one_noisy_source_from_monopolizing():
    episodes = []
    for slot, src in ((100,SOURCES[0]),(101,SOURCES[1]),(102,SOURCES[2])):
        rows = ([observation(f"https://reddit.com/{slot}",
                 "Looking for sales automation recommendations",
                 "Need help with marketing and calls")] if src==SOURCES[0] else [])
        episodes, _ = run(episodes, source=src,slot=slot, observations=rows)
    for slot in range(103,147):
        src = select_source(SOURCES,episodes,slot=slot)
        episodes, _ = run(episodes,source=src,slot=slot)
    checked = {r["source_id"] for r in episodes[-15:]}
    assert checked == {source_id(s) for s in SOURCES}


def test_persisted_learning_is_bounded_private_and_rejects_mutation(tmp_path):
    episodes, event = run([],observations=[])
    data=snapshot(episodes,SOURCES,now=NOW,latest=event,
                  next_source=SOURCES[1])
    path=tmp_path/"source_learning_latest.json"
    write_snapshot(path,data)
    assert load_history(path)==episodes
    data2=json.loads(path.read_text())
    data2["episodes"][0]["slot"]="malicious"
    path.write_text(json.dumps(data2))
    with pytest.raises(ValueError,match="invalid_learning_slot"):
        load_history(path)


def test_bad_source_cannot_buy_or_mutate_models():
    episodes, event=run([],ok=True)
    report=snapshot(episodes,SOURCES,now=NOW,latest=event,
                    next_source=SOURCES[2])
    assert report["execution_authority"] == "NONE"
    assert report["actual_revenue_learning"] == "REQUIRES_VERIFIED_CORTEX_AND_ECONOMIC_MEMORY"
    assert report["spend_execution"] is False


def test_running_existing_community_cycle_twice_in_one_slot_is_idempotent(
    tmp_path, monkeypatch,
):
    import json
    from scripts import run_community_intent_cycle as cycle
    from empire_os.community_intent import normalize_search_result

    root=tmp_path/"runtime/community_intent"
    root.mkdir(parents=True)
    monkeypatch.setattr(cycle,"HISTORY",root/"observations.json")
    monkeypatch.setattr(cycle,"OUTPUT",root/"latest.json")
    monkeypatch.setattr(cycle,"LEARNING",root/"source_learning_latest.json")

    row=normalize_search_result(
        platform="reddit", query="roofing leads", niche="roofing",
        result={
            "title":"Looking for qualified leads for roofers",
            "link":"https://www.reddit.com/r/Roofing/comments/proven/need_leads/",
            "snippet":"We run a roofing company and need more qualified appointments.",
        },
    )
    assert row is not None
    monkeypatch.setattr(
        cycle, "collect_reddit_rss_intent",
        lambda **kwargs: {"ok":True,"status_code":200,"reason":None,
                          "observations":[row]},
    )
    monkeypatch.setattr(cycle,"_collect_linkedin",
                        lambda *args:([],{
                            "ok":False,"error":"CIRCUIT_OPEN",
                            "search_state":"PROVIDER_DEGRADED",
                        }))
    monkeypatch.setattr(cycle,"enqueue_observation",
                        lambda row:{"decision":"queued","authority":"none"})
    monkeypatch.setattr(cycle,"build_pain_solution_briefs",lambda observations:[])
    assert cycle.main()==0
    first=json.loads((root/"latest.json").read_text())
    assert first["new_observations"]==1
    assert first["fetched_observations"]==1
    assert first["icp_research_learning"]["episode_count"]==1
    assert first["icp_research_learning"]["execution_authority"]=="NONE"
    assert first["jev_client_pain_discovery"]["execution_authority"]=="none"
    assert first["jev_client_pain_discovery"]["outbound_sent"]==0
    assert "items" not in first["jev_client_pain_discovery"]
    private = root/"jev_client_pain_review_latest.json"
    assert private.exists()
    assert private.stat().st_mode & 0o777 == 0o600
    assert json.loads(private.read_text())["items"]

    assert cycle.main()==0
    second=json.loads((root/"latest.json").read_text())
    learning=json.loads((root/"source_learning_latest.json").read_text())
    assert second["new_observations"]==0
    assert second["fetched_observations"]==1
    assert len(learning["episodes"])==1
    assert learning["recognized_revenue_cents"] is None
    assert learning["execution_authority"]=="NONE"
