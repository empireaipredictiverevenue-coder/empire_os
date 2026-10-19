from scripts.run_resilient_buyer_scout_20261019 import reviewed_seed_records

def test_bounded_rotation_across_company_shortlist():
    snapshot = {
        "schema_version": "empire.buyer_qualification_actions.v1",
        "mode": "OBSERVE",
        "outbound_enabled": False,
        "outbound_sent": False,
        "targets": [
            {"domain": f"business{i}.example.org",
             "outbound_authorized": False,
             "existing_first_party_source_urls": []}
            for i in range(25)
        ],
    }
    batches = [
        reviewed_seed_records(snapshot, limit=8, rotation=i)
        for i in range(4)
    ]
    assert all(len(batch) == 8 for batch in batches)
    assert len({row["domain"] for batch in batches for row in batch}) == 25
    assert all(row["target_buyer_pools"] == ["direct_demand_buyers"]
               for batch in batches for row in batch)

def test_unapproved_outbound_contract_rejected():
    import pytest
    bad = {
        "schema_version": "empire.buyer_qualification_actions.v1",
        "mode": "OBSERVE", "outbound_enabled": True,
        "outbound_sent": False, "targets": [],
    }
    with pytest.raises(ValueError):
        reviewed_seed_records(bad, limit=8)


def test_technical_host_and_external_references_filtered():
    snapshot = {
        "schema_version": "empire.buyer_qualification_actions.v1",
        "mode": "OBSERVE", "outbound_enabled": False,
        "outbound_sent": False,
        "targets": [
            {"domain": "event.ingest.us.sentry.io", "outbound_authorized": False},
            {"domain": "solarbuyer.example.org", "outbound_authorized": False,
             "existing_first_party_source_urls": [
                 "https://unrelated.example.org/private",
                 "https://solarbuyer.example.org/partner",
                 "https://solarbuyer.example.org@evil.example.org/capture",
             ]},
        ],
    }
    seeds = reviewed_seed_records(snapshot, limit=8)
    assert [x["domain"] for x in seeds] == ["solarbuyer.example.org"]
    assert seeds[0]["source_refs"] == ["https://solarbuyer.example.org/partner"]
