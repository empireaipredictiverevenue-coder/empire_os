from urllib.parse import parse_qs, urlparse

from empire_os.legacy_permit_recovery import fetch_legacy_permit_rows


def test_fetch_targets_unique_legacy_ids_without_skipping(monkeypatch):
    rows = []
    row_id = 1

    for group in range(101):
        repeat = 3 if group < 100 else 1
        for lane in range(repeat):
            rows.append({
                "id": row_id,
                "lane_id": f"lane-{group}-{lane}",
                "prospect_id": f"prospect_{group:03d}",
                "status": "pending",
                "omega_score": 70,
                "omega_tier": "silver",
                "notes": (
                    "name=Example LLC email= phone= metro=NYC state=NY "
                    "details=A2.PL permit 401975190 issued 2026-08-16: . "
                    "Address: 1 TEST STREET, Queens"
                ),
                "created_at": "2026-08-18T00:00:00+00:00",
                "buyer_id": None,
                "niche": "plumbing",
                "metro": "NYC",
            })
            row_id += 1

    def fake_request(method, path):
        query = parse_qs(urlparse(path).query)
        limit = int(query["limit"][0])
        offset = int(query["offset"][0])
        return rows[offset:offset + limit]

    monkeypatch.setattr(
        "empire_os.legacy_permit_recovery.request_json",
        fake_request,
    )

    first, next_offset, budget = fetch_legacy_permit_rows(
        batch_size=100,
        offset=0,
    )

    assert budget == 2500
    assert len({row["prospect_id"] for row in first}) == 100
    assert next_offset == 300

    second, _, _ = fetch_legacy_permit_rows(
        batch_size=100,
        offset=next_offset,
    )
    assert second[0]["prospect_id"] == "prospect_100"
