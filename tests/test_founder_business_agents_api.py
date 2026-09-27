from empire_os.control_fabric import default_registry
from empire_os.founder_business_agents_api import build_business_agents_status


def test_batch1_business_agents_registered_in_control_fabric():
    by_name = {row.name: row for row in default_registry()}
    assert "buyer_reply_operations_agent" in by_name
    assert "deliverability_sender_reputation_agent" in by_name
    assert "source_reliability_agent" in by_name

    assert by_name["buyer_reply_operations_agent"].authority == "internal_write"
    assert by_name["deliverability_sender_reputation_agent"].authority == "observe"
    assert by_name["source_reliability_agent"].authority == "observe"


def test_founder_business_agents_status_is_read_only_and_non_authoritative():
    payload = build_business_agents_status()
    assert payload["read_only"] is True
    assert payload["execution_authority"] == "none"

    reply = payload["buyer_reply_operations"]
    assert reply["outbound_send_authority"] is False
    assert reply["payment_authority"] is False

    delivery = payload["deliverability_sender_reputation"]
    assert delivery["outbound_send_authority"] is False
    assert delivery["dns_mutation_authority"] is False

    source = payload["source_reliability"]
    assert source["canonical_delete_authority"] is False
    assert source["permanent_retirement_allowed"] is False
