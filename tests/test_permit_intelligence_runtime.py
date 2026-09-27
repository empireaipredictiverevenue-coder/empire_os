import json

from empire_os.permit_intelligence_runtime import (
    build_permit_intelligence_runtime,
)


def test_permit_runtime_preserves_real_signal_truth(tmp_path):
    path = tmp_path / "runtime/acquisition/signal_inbox.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({
        "one": {
            "source": "permits_nyc",
            "status": "resolved",
            "metro": "NYC",
            "url": "https://example.test/permit/1",
            "created_at": "2026-09-20T10:00:00+00:00",
            "last_seen_at": "2026-09-21T10:00:00+00:00",
            "raw": {"job__": "1"},
        },
        "two": {
            "source": "permits_nyc",
            "status": "unresolved",
            "metro": "NYC",
            "created_at": "2026-09-21T11:00:00+00:00",
            "raw": {},
        },
        "other": {
            "source": "courtlistener",
            "status": "resolved",
        },
    }))

    result = build_permit_intelligence_runtime(tmp_path)

    assert result["signal_count"] == 2
    assert result["resolved_count"] == 1
    assert result["unresolved_count"] == 1
    assert result["by_source"] == {"permits_nyc": 2}
    assert result["by_metro"] == {"NYC": 2}
    assert result["latest_seen_at"] == "2026-09-21T11:00:00+00:00"
    assert result["with_source_url"] == 1
    assert result["with_raw_reference"] == 1
    assert result["evidence_state"] == "EVIDENCE_AVAILABLE"
    assert result["read_surface_ready"] is True
    assert result["pricing_observed"] is False
    assert result["actual_revenue"] is False
    assert result["execution_authority"] == "none"


def test_permit_runtime_keeps_missing_evidence_unknown(tmp_path):
    result = build_permit_intelligence_runtime(tmp_path)

    assert result["signal_count"] == 0
    assert result["evidence_state"] == "UNKNOWN"
    assert result["read_surface_ready"] is False
    assert result["latest_seen_at"] is None
    assert result["binding_terms_ready"] is False
