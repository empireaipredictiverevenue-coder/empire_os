from urllib.parse import parse_qs, urlparse

import scripts.run_buyer_acquisition_scout as runner


def test_permit_seed_lane_reserves_nyc_zero_offset(monkeypatch):
    calls = []

    def fake_request(method, path):
        calls.append((method, path))
        query = parse_qs(urlparse(path).query)
        niches = query.get("niche", [""])[0]
        if "general_contractor" in niches:
            return [{
                "id": "gc-nyc",
                "business_name": "NYC Build Co",
                "niche": "general_contractor",
                "website": "https://nyc-build.example",
                "metro": "nyc",
                "status": "new",
                "created_at": "2026-09-24T00:00:00+00:00",
            }]
        return []

    monkeypatch.setattr(runner, "request_json", fake_request)

    rows = runner._canonical_seed_records(per_lane=8)

    first_query = parse_qs(urlparse(calls[0][1]).query)
    assert first_query["offset"] == ["0"]
    assert first_query["metro"] == ["ilike.NYC"]

    row = next(item for item in rows if item["id"] == "gc-nyc")
    assert row["icp_profile_key"] == "high_ticket_home_service"
    assert row["seed_buyer_pools"] == [
        "end_service_buyers",
        "local_and_smb_buyers",
    ]
    assert row["seed_product_code"] == "permit_intelligence"
    assert row["seed_corridor_key"].endswith(":general_contractor:nyc")
