import json
from pathlib import Path

from empire_os.competitor_audience_runtime import (
    build_competitor_audience_runtime,
    summarize_competitor_audience_rows,
    write_competitor_audience_snapshot,
)


def _row(*, signal_id, entity_id, name, source_refs):
    return {
        "id": signal_id,
        "entity_id": entity_id,
        "canonical_name": name,
        "canonical_website": "https://goldenspikeroofing.com",
        "observed_at": "2026-09-22T10:55:05+00:00",
        "strength": 1.0,
        "confidence": 0.9,
        "payload": {
            "research_candidate": True,
            "buyer_intent": False,
            "commercial_intent": False,
            "outreach_enabled": False,
            "evidence": [
                {
                    "competitor_key": "elite-roofing-solar",
                    "evidence_type": "comparison_mention",
                    "source_ref": ref,
                    "summary": "Observed on the same public comparison page.",
                    "observed_at": "2026-09-22T10:55:05+00:00",
                    "confidence": 0.9,
                }
                for ref in source_refs
            ],
        },
    }


def test_summary_dedupes_overlapping_snapshot_evidence():
    rows = [
        _row(
            signal_id="signal-1",
            entity_id="entity-1",
            name="Golden Spike Roofing Inc",
            source_refs=["https://comparison.example/a"],
        ),
        _row(
            signal_id="signal-2",
            entity_id="entity-1",
            name="Golden Spike Roofing Inc",
            source_refs=[
                "https://comparison.example/a",
                "https://comparison.example/b",
                "https://comparison.example/c",
            ],
        ),
    ]

    result = summarize_competitor_audience_rows(
        rows,
        generated_at="2026-09-22T11:00:00+00:00",
    )

    assert result["canonical_signal_row_count"] == 2
    assert result["company_count"] == 1
    assert result["competitor_count"] == 1
    assert result["unique_evidence_count"] == 3
    assert result["stacked_company_count"] == 1
    assert result["max_evidence_stack"] == 3

    company = result["companies"][0]
    assert company["signal_rows"] == 2
    assert company["unique_evidence_count"] == 3
    assert company["stack_strength"] == 1.0


def test_summary_preserves_observe_only_invariants():
    result = summarize_competitor_audience_rows([
        _row(
            signal_id="signal-1",
            entity_id="entity-1",
            name="Golden Spike Roofing Inc",
            source_refs=["https://comparison.example/a"],
        )
    ])

    assert result["mode"] == "OBSERVE"
    assert result["execution_authority"] == "none"
    assert result["buyer_intent_inferred"] is False
    assert result["commercial_intent_inferred"] is False
    assert result["outreach_enabled"] is False

    company = result["companies"][0]
    assert company["research_candidate"] is True
    assert company["buyer_intent"] is False
    assert company["commercial_intent"] is False
    assert company["outreach_enabled"] is False
    assert company["execution_authority"] == "none"


def test_runtime_reports_unavailable_when_snapshot_missing(tmp_path):
    result = build_competitor_audience_runtime(tmp_path)

    assert result["available"] is False
    assert result["company_count"] == 0
    assert result["unique_evidence_count"] == 0
    assert result["execution_authority"] == "none"


def test_runtime_reads_atomic_snapshot(tmp_path):
    payload = summarize_competitor_audience_rows([
        _row(
            signal_id="signal-1",
            entity_id="entity-1",
            name="Golden Spike Roofing Inc",
            source_refs=["https://comparison.example/a"],
        )
    ])

    path = write_competitor_audience_snapshot(tmp_path, payload)
    assert path.exists()

    result = build_competitor_audience_runtime(tmp_path)

    assert result["available"] is True
    assert result["company_count"] == 1
    assert result["unique_evidence_count"] == 1
    assert result["companies"][0]["company_name"] == "Golden Spike Roofing Inc"



def test_runtime_includes_omega_cortex_context():
    result = summarize_competitor_audience_rows([
        _row(
            signal_id="signal-1",
            entity_id="entity-1",
            name="Golden Spike Roofing Inc",
            source_refs=[
                "https://comparison.example/a",
                "https://comparison.example/b",
                "https://comparison.example/c",
            ],
        )
    ])

    context = result["omega_cortex_context"][0]

    assert context["research_rank"] == 1
    assert context["next_best_research_action"] == "deep_account_research"
    assert context["omega"]["lead_qualification_mutation"] is False
    assert context["omega"]["score_persistence_authorized"] is False
    assert context["cortex"]["verified_outcome"] is False
    assert context["buyer_intent"] is False
    assert context["commercial_intent"] is False
    assert context["outreach_enabled"] is False
