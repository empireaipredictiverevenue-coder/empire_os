from empire_os.private_capital_snapshot import fetch_private_capital_snapshot


def test_private_capital_snapshot_counts_only_explicit_domain_evidence():
    data = {
        "/rest/v1/intelligence_signals": [
            {
                "id": "s1",
                "signal_domain": "private_capital",
                "signal_type": "rollup_cluster",
                "observed_at": "2026-09-21T10:00:00+00:00",
            }
        ],
        "/rest/v1/intelligence_facts": [
            {
                "id": "f1",
                "fact_key": "private_capital.sponsor",
                "last_seen_at": "2026-09-21T11:00:00+00:00",
            }
        ],
        "/rest/v1/intelligence_segments": [
            {
                "id": "seg1",
                "segment_key": "private_capital_sponsors",
                "intelligence_domain": "private_capital",
                "active": True,
                "created_at": "2026-09-20T10:00:00+00:00",
            }
        ],
        "/rest/v1/intelligence_segment_membership": [
            {
                "entity_id": "e1",
                "segment_id": "seg1",
                "scored_at": "2026-09-21T12:00:00+00:00",
            }
        ],
    }

    calls = []

    def reader(path, params):
        calls.append((path, params))
        return data.get(path, [])

    result = fetch_private_capital_snapshot(
        reader,
        generated_at="2026-09-21T13:00:00+00:00",
    )

    assert result["canonical_signal_count"] == 1
    assert result["canonical_fact_count"] == 1
    assert result["private_capital_segment_count"] == 1
    assert result["segment_membership_count"] == 1
    assert result["evidence_state"] == "EVIDENCE_AVAILABLE"
    assert result["latest_observed_at"] == "2026-09-21T12:00:00+00:00"
    assert result["deal_intent_observed"] is False
    assert result["opportunity_count"] is None
    assert result["actual_revenue"] is False

    signal_call = next(params for path, params in calls if path.endswith("signals"))
    assert signal_call["signal_domain"] == "eq.private_capital"
    fact_call = next(params for path, params in calls if path.endswith("facts"))
    assert fact_call["fact_key"] == "like.private_capital.%"


def test_private_capital_snapshot_preserves_zero_as_unknown():
    def reader(_path, _params):
        return []

    result = fetch_private_capital_snapshot(
        reader,
        generated_at="2026-09-21T13:00:00+00:00",
    )

    assert result["canonical_signal_count"] == 0
    assert result["canonical_fact_count"] == 0
    assert result["segment_membership_count"] == 0
    assert result["evidence_state"] == "UNKNOWN"
    assert result["latest_observed_at"] is None
    assert result["deal_intent_observed"] is False
    assert result["opportunity_count"] is None
