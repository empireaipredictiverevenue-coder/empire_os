from datetime import datetime, timezone

from empire_os.outbound_telemetry_sla import evaluate_telemetry_sla


NOW = datetime(2026, 10, 3, 20, 30, tzinfo=timezone.utc)


def heartbeat(source, observed_at, *, success=True, coverage=True, details=None):
    return {
        "source": source,
        "observed_at": observed_at,
        "success": success,
        "coverage": coverage,
        "details": details or {},
    }


def test_all_required_observers_current_even_with_zero_email_activity():
    result = evaluate_telemetry_sla(
        required_sources=[
            "provider_metrics",
            "provider_event_ingest",
            "dns_auth",
        ],
        critical_sources=[
            "provider_metrics",
            "provider_event_ingest",
        ],
        heartbeats=[
            heartbeat(
                "provider_metrics",
                "2026-10-03T20:20:00+00:00",
                details={"events_seen": 0},
            ),
            heartbeat(
                "provider_event_ingest",
                "2026-10-03T20:25:00+00:00",
                details={"events_seen": 0},
            ),
            heartbeat(
                "dns_auth",
                "2026-10-03T20:10:00+00:00",
            ),
        ],
        now=NOW,
        default_max_age_minutes=30,
    )
    assert result["posture"] == "CURRENT"
    assert result["critical_blind"] is False
    assert result["send_authorized"] is False


def test_missing_critical_provider_event_heartbeat_is_blind():
    result = evaluate_telemetry_sla(
        required_sources=[
            "provider_metrics",
            "provider_event_ingest",
        ],
        critical_sources=[
            "provider_metrics",
            "provider_event_ingest",
        ],
        heartbeats=[
            heartbeat(
                "provider_metrics",
                "2026-10-03T20:20:00+00:00",
            ),
        ],
        now=NOW,
    )
    assert result["posture"] == "BLIND"
    assert result["critical_blind"] is True
    assert result["critical_missing_sources"] == ["provider_event_ingest"]


def test_old_observer_heartbeat_is_stale_not_missing():
    result = evaluate_telemetry_sla(
        required_sources=["provider_metrics"],
        critical_sources=["provider_metrics"],
        heartbeats=[
            heartbeat(
                "provider_metrics",
                "2026-10-03T18:00:00+00:00",
            ),
        ],
        now=NOW,
        default_max_age_minutes=30,
    )
    assert result["posture"] == "STALE"
    assert result["critical_stale"] is True
    assert result["critical_blind"] is False


def test_failed_observer_is_blind_even_when_recent():
    result = evaluate_telemetry_sla(
        required_sources=["provider_event_ingest"],
        critical_sources=["provider_event_ingest"],
        heartbeats=[
            heartbeat(
                "provider_event_ingest",
                "2026-10-03T20:29:00+00:00",
                success=False,
            ),
        ],
        now=NOW,
    )
    assert result["posture"] == "BLIND"
    assert result["critical_failed_sources"] == ["provider_event_ingest"]


def test_partial_seed_coverage_is_partial_not_silently_current():
    result = evaluate_telemetry_sla(
        required_sources=["seed_placement"],
        critical_sources=[],
        heartbeats=[
            heartbeat(
                "seed_placement",
                "2026-10-03T20:25:00+00:00",
                coverage=False,
                details={"missing_mx_families": ["YAHOO", "APPLE"]},
            ),
        ],
        now=NOW,
    )
    assert result["posture"] == "PARTIAL"
    assert result["partial_sources"] == ["seed_placement"]


def test_source_specific_age_override_is_respected():
    result = evaluate_telemetry_sla(
        required_sources=["dmarc_aggregate", "provider_metrics"],
        heartbeats=[
            heartbeat(
                "dmarc_aggregate",
                "2026-10-03T18:00:00+00:00",
            ),
            heartbeat(
                "provider_metrics",
                "2026-10-03T20:20:00+00:00",
            ),
        ],
        now=NOW,
        default_max_age_minutes=30,
        source_max_age_minutes={"dmarc_aggregate": 240},
    )
    assert result["posture"] == "CURRENT"


def test_newest_heartbeat_wins_deterministically():
    result = evaluate_telemetry_sla(
        required_sources=["provider_metrics"],
        heartbeats=[
            heartbeat(
                "provider_metrics",
                "2026-10-03T18:00:00+00:00",
                success=False,
            ),
            heartbeat(
                "provider_metrics",
                "2026-10-03T20:29:00+00:00",
                success=True,
            ),
        ],
        now=NOW,
    )
    assert result["posture"] == "CURRENT"
    assert result["sources"]["provider_metrics"]["success"] is True


def test_future_or_malformed_heartbeat_never_counts_as_current():
    result = evaluate_telemetry_sla(
        required_sources=["provider_metrics"],
        critical_sources=["provider_metrics"],
        heartbeats=[
            heartbeat(
                "provider_metrics",
                "2099-01-01T00:00:00+00:00",
            ),
            heartbeat(
                "provider_metrics",
                "not-a-time",
            ),
        ],
        now=NOW,
    )
    assert result["posture"] == "BLIND"
    assert result["critical_blind"] is True
    assert result["malformed_heartbeats"]
