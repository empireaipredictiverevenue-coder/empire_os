from empire_os.outbound_open_source_evidence import (
    normalize_checkdmarc_result,
    normalize_dnscontrol_preview,
    summarize_parsedmarc_aggregate,
)


def test_checkdmarc_adapter_is_evidence_only():
    result = normalize_checkdmarc_result({
        "domain": "example.com",
        "spf": {"record": "v=spf1 -all", "valid": True},
        "dmarc": {"record": "v=DMARC1; p=reject", "valid": True},
        "mx": {"hosts": [{"hostname": "mx.example.com", "starttls": True}]},
    })
    assert result["spf_valid"] is True
    assert result["dmarc_valid"] is True
    assert result["mx_starttls_ready"] is True
    assert result["mutation_authorized"] is False


def test_parsedmarc_summary_weights_alignment_by_message_count():
    result = summarize_parsedmarc_aggregate({
        "domain": "example.com",
        "records": [
            {
                "count": 9,
                "alignment": {"spf": True, "dkim": True, "dmarc": True},
            },
            {
                "count": 1,
                "alignment": {"spf": False, "dkim": False, "dmarc": False},
            },
        ],
    })
    assert result["messages"] == 10
    assert result["dmarc_pass_rate"] == 0.9
    assert result["mutation_authorized"] is False


def test_dnscontrol_preview_never_authorizes_push():
    result = normalize_dnscontrol_preview([
        {"action": "CHANGE", "record_type": "TXT", "name": "_dmarc.example.com"},
        {"action": "DELETE", "record_type": "TXT", "name": "old.example.com"},
    ])
    assert result["posture"] == "APPROVAL_REQUIRED"
    assert result["delete_count"] == 1
    assert result["dns_push_authorized"] is False
    assert result["mutation_authorized"] is False
