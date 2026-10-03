from empire_os.outbound_open_source_health import evaluate_open_source_evidence


def test_invalid_dmarc_from_checkdmarc_is_hold():
    result = evaluate_open_source_evidence({
        "checkdmarc": {
            "domain": "example.com",
            "spf": {"valid": True, "record": "v=spf1 -all"},
            "dmarc": {"valid": False, "error": "invalid record"},
        }
    })
    assert result["posture"] == "HOLD"
    assert "dmarc_record_invalid" in result["hard_holds"]
    assert result["mutation_authorized"] is False


def test_low_dmarc_alignment_with_enough_volume_is_remediate():
    result = evaluate_open_source_evidence({
        "parsedmarc": {
            "domain": "example.com",
            "records": [
                {
                    "count": 18,
                    "alignment": {"spf": True, "dkim": True, "dmarc": True},
                },
                {
                    "count": 2,
                    "alignment": {"spf": False, "dkim": False, "dmarc": False},
                },
            ],
        }
    })
    assert result["posture"] == "REMEDIATE"
    assert "dmarc_alignment_rate_degraded" in result["warnings"]


def test_dnscontrol_delete_requires_approval_but_does_not_authorize_it():
    result = evaluate_open_source_evidence({
        "dnscontrol_preview": [
            {"action": "DELETE", "record_type": "TXT", "name": "old.example.com"},
        ]
    })
    assert result["posture"] == "REMEDIATE"
    assert "dns_destructive_change_requires_approval" in result["warnings"]
    assert result["mutation_authorized"] is False
