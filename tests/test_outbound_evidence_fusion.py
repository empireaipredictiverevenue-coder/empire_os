from datetime import datetime, timedelta, timezone

from empire_os.outbound_evidence_fusion import fuse_evidence


NOW = datetime(2026, 10, 3, 19, 0, tzinfo=timezone.utc)


def test_independent_auth_sources_reach_consensus():
    result = fuse_evidence([
        {
            "signal": "dmarc_valid",
            "value": True,
            "source": "checkdmarc",
            "observed_at": NOW.isoformat(),
            "confidence": 0.9,
        },
        {
            "signal": "dmarc_valid",
            "value": True,
            "source": "parsedmarc",
            "observed_at": NOW.isoformat(),
            "confidence": 0.8,
        },
    ], now=NOW)
    assert result["posture"] == "CONSENSUS"
    assert result["signals"]["dmarc_valid"]["value"] is True


def test_critical_auth_disagreement_is_investigation_not_silent_override():
    result = fuse_evidence([
        {
            "signal": "dkim_aligned",
            "value": True,
            "source": "provider",
            "observed_at": NOW.isoformat(),
        },
        {
            "signal": "dkim_aligned",
            "value": False,
            "source": "parsedmarc",
            "observed_at": NOW.isoformat(),
        },
    ], now=NOW)
    assert result["posture"] == "INVESTIGATE"
    assert "dkim_aligned" in result["critical_conflicts"]
    assert result["mutation_authorized"] is False


def test_stale_evidence_does_not_override_fresh_evidence():
    result = fuse_evidence([
        {
            "signal": "spf_aligned",
            "value": False,
            "source": "old-observer",
            "observed_at": (NOW - timedelta(days=3)).isoformat(),
        },
        {
            "signal": "spf_aligned",
            "value": True,
            "source": "fresh-observer",
            "observed_at": NOW.isoformat(),
        },
    ], now=NOW, max_age_hours=24)
    assert result["signals"]["spf_aligned"]["status"] == "CONSENSUS"
    assert result["signals"]["spf_aligned"]["value"] is True
    assert result["signals"]["spf_aligned"]["stale_observations"] == 1
