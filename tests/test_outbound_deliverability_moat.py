from datetime import date

import pytest

from empire_os.outbound_reputation_graph import build_dependency_graph, blast_radius
from empire_os.outbound_provider_policy_registry import (
    ProviderPolicySnapshot,
    evaluate_provider_policy,
)
from empire_os.outbound_transport_benchmark import compare_seed_transports
from empire_os.outbound_commercial_feedback import commercial_signal_score


def test_blast_radius_finds_dependent_mailboxes():
    graph = build_dependency_graph([
        {"upstream": "transport:a", "downstream": "domain:x"},
        {"upstream": "domain:x", "downstream": "mailbox:1"},
        {"upstream": "domain:x", "downstream": "mailbox:2"},
    ])
    result = blast_radius(graph, ["transport:a"])
    assert result["impact_count"] == 3
    assert "mailbox:2" in result["impacted_nodes"]


def test_provider_policy_is_dated_and_fail_closed_when_unknown():
    snapshots = [
        ProviderPolicySnapshot(
            provider="example",
            effective_date=date(2026, 1, 1),
            reviewed_date=date(2026, 10, 1),
            allowed_traffic_classes=frozenset({"transactional"}),
            source_url="https://example.invalid/policy",
        )
    ]
    result = evaluate_provider_policy(
        snapshots,
        provider="example",
        traffic_class="prospecting",
        as_of=date(2026, 10, 3),
    )
    assert result["status"] == "PROHIBITED"


def test_transport_benchmark_rejects_non_seed_recipient():
    with pytest.raises(ValueError, match="empire_seed"):
        compare_seed_transports([{
            "transport": "a",
            "recipient_class": "prospect",
            "provider_policy_compatible": True,
            "placement": "inbox",
        }])


def test_transport_benchmark_prefers_better_seed_placement():
    result = compare_seed_transports([
        {
            "transport": "a",
            "recipient_class": "empire_seed",
            "provider_policy_compatible": True,
            "placement": "inbox",
            "latency_ms": 100,
        },
        {
            "transport": "b",
            "recipient_class": "empire_seed",
            "provider_policy_compatible": True,
            "placement": "spam",
            "latency_ms": 50,
        },
    ])
    assert result["preferred_transport"] == "a"


def test_commercial_feedback_penalises_optouts_and_bounces():
    result = commercial_signal_score([
        {"kind": "positive_reply"},
        {"kind": "opt_out"},
        {"kind": "hard_bounce"},
    ])
    assert result["signal"] == "NEGATIVE"
    assert result["uses_open_tracking"] is False
