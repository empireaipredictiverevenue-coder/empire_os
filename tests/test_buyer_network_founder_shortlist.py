from importlib.util import (
    module_from_spec,
    spec_from_file_location,
)
from pathlib import Path


PATH = Path(
    "scripts/materialize_buyer_network_founder_shortlist.py"
)


def module():

    spec = spec_from_file_location(
        "buyer_founder_shortlist",
        PATH,
    )

    mod = module_from_spec(
        spec
    )

    assert spec.loader is not None

    spec.loader.exec_module(
        mod
    )

    return mod


def strong_candidate():

    return {
        "domain":
            "buyer.example",

        "status":
            "READY_TO_APPROACH",

        "score":
            82,

        "already_known":
            False,

        "verticals":
            ["roofing"],

        "evidence": {
            "publisher_program":
                True,

            "active_demand":
                True,

            "integration":
                True,

            "economics":
                True,

            "compliance":
                True,

            "contactable":
                True,

            "negative_program":
                False,

            "evidence_count":
                6,
        },
    }


def test_file_exists():

    assert PATH.exists()


def test_strong_candidate_is_founder_review():

    mod = module()

    assert (
        mod.classify(
            strong_candidate()
        )
        == "A_FOUNDER_REVIEW"
    )


def test_missing_economics_is_gap():

    mod = module()

    candidate = strong_candidate()

    candidate["evidence"][
        "economics"
    ] = False

    assert (
        "verify_payout_economics"
        in mod.evidence_gaps(
            candidate
        )
    )


def test_never_invents_revenue():

    mod = module()

    result = mod.enrich(
        strong_candidate()
    )

    assert (
        result[
            "predictive_revenue"
        ]["forecast_revenue"]
        is None
    )


def test_outbound_remains_false():

    mod = module()

    result = mod.enrich(
        strong_candidate()
    )

    assert (
        result[
            "outbound_authority"
        ]
        is False
    )


def test_open_founder_research_includes_watch_without_promotion_or_old_25_cap(
    tmp_path, monkeypatch,
):
    import json
    mod = module()
    queue = tmp_path / "queue.json"
    dest = tmp_path / "shortlist.json"
    md = tmp_path / "shortlist.md"
    candidates = []
    for i in range(30):
        row = strong_candidate()
        row["domain"] = f"watch{i}.com"
        row["status"] = "WATCH"
        row["score"] = 40
        row["evidence"] = {
            "publisher_program": False,
            "active_demand": False,
            "integration": False,
            "economics": False,
            "compliance": False,
            "contactable": False,
            "negative_program": False,
            "evidence_count": 1,
            "lines": [f"https://watch{i}.com/about"],
        }
        candidates.append(row)
    ready = strong_candidate()
    ready["domain"] = "confirmedbuyer.com"
    ready["evidence"]["lines"] = ["https://confirmedbuyer.com/publishers"]
    candidates.append(ready)
    queue.write_text(json.dumps({
        "candidate_count": len(candidates), "candidates": candidates,
    }))
    monkeypatch.setattr(mod, "QUEUE", queue)
    monkeypatch.setattr(mod, "OUTPUT", dest)
    monkeypatch.setattr(mod, "MARKDOWN", md)
    monkeypatch.setattr(mod, "load_existing_logic", lambda: {})
    monkeypatch.setattr(mod, "load_context", lambda: {
        "source": "TEST", "gmail_snapshot_fresh": False,
    })
    monkeypatch.setattr(mod, "review", lambda domain, ctx: {
        "state": "NO_HISTORY_VERIFIED", "next_action": "RECONCILE",
    })
    assert mod.main() == 0
    result = json.loads(dest.read_text())
    assert result["shortlist_count"] == 31
    assert result["eligible_candidate_count"] == 31
    assert result["open_research_deferred_count"] == 0
    assert result["open_research_state_counts"] == {
        "READY_TO_APPROACH": 1, "VERIFY_REQUIREMENTS": 0, "WATCH": 30,
    }
    assert result["founder_review_not_inferred_from_watch"] is True
    assert result["automatic_outbound_for_watch"] is False
    watches = [r for r in result["shortlist"] if r["queue_status"] == "WATCH"]
    assert len(watches) == 30
    assert all(r["founder_class"] == "HOLD" for r in watches)
    assert all(r["outbound_authority"] is False for r in result["shortlist"])
