from pathlib import Path

import empire_os.solar_opportunity_map_automation as auto


PID = "00000000-0000-0000-0000-000000000101"


def test_review_outcome_materializes_only_solar_proposal(monkeypatch, tmp_path: Path):
    def request(method, path, payload=None, prefer=None):
        if path.startswith("/rest/v1/prospects?"):
            return [{
                "id": PID,
                "business_name": "Example Solar Ltd",
                "niche": "solar",
                "website": "https://solar.example",
            }]
        raise AssertionError(path)

    monkeypatch.setattr(
        auto,
        "build_solar_opportunity_map",
        lambda prospect_id, request=None: {
            "prospect": {
                "id": prospect_id,
                "business_name": "Example Solar Ltd",
            },
            "buyer_review": {
                "id": "review-1",
                "status": "pending",
            },
            "priority_backlog": [{"code": "x"}],
        },
    )
    monkeypatch.setattr(
        auto,
        "write_solar_opportunity_map",
        lambda payload, root=None: {
            "json_path": str(tmp_path / "x.json"),
            "markdown_path": str(tmp_path / "x.md"),
        },
    )

    result = auto.materialize_solar_maps_for_review_outcomes(
        [
            {
                "prospect_id": PID,
                "business_name": "Example Solar Ltd",
                "status": "proposed",
            },
            {
                "prospect_id": "ignored",
                "status": "deferred",
            },
        ],
        request=request,
        root=tmp_path,
    )

    assert result["candidate_count"] == 1
    assert result["materialized_count"] == 1
    assert result["error_count"] == 0
    assert result["outbound_sent"] is False
    assert result["recognized_revenue"] is False


def test_review_outcome_skips_non_solar(monkeypatch):
    def request(method, path, payload=None, prefer=None):
        return [{
            "id": PID,
            "business_name": "Example Roofing",
            "niche": "roofing",
            "website": "https://roof.example",
        }]

    result = auto.materialize_solar_maps_for_review_outcomes(
        [{
            "prospect_id": PID,
            "business_name": "Example Roofing",
            "status": "proposed",
        }],
        request=request,
    )

    assert result["materialized_count"] == 0
    assert result["skipped_count"] == 1
    assert result["skipped"][0]["reason"] == "not_solar"


def test_missing_map_backlog_skips_existing_and_retries_missing(monkeypatch, tmp_path: Path):
    existing = "00000000-0000-0000-0000-000000000201"
    missing = "00000000-0000-0000-0000-000000000202"
    (tmp_path / f"{existing}.json").write_text("{}")
    (tmp_path / f"{existing}.md").write_text("# map")

    calls = []

    def request(method, path, payload=None, prefer=None):
        if path.startswith("/rest/v1/buyer_candidate_reviews?"):
            assert "evidence-%3E%3Eniche=eq.solar" in path
            return [
                {"id": "r1", "prospect_id": existing, "status": "pending"},
                {"id": "r2", "prospect_id": missing, "status": "pending"},
            ]
        if path.startswith("/rest/v1/prospects?"):
            calls.append(path)
            return [{
                "id": missing,
                "business_name": "Missing Solar Ltd",
                "niche": "solar",
                "website": "https://missing.example",
            }]
        raise AssertionError(path)

    monkeypatch.setattr(
        auto,
        "build_solar_opportunity_map",
        lambda prospect_id, request=None: {
            "prospect": {"id": prospect_id, "business_name": "Missing Solar Ltd"},
            "buyer_review": {"id": "r2", "status": "pending"},
            "priority_backlog": [],
        },
    )
    monkeypatch.setattr(
        auto,
        "write_solar_opportunity_map",
        lambda payload, root=None: {
            "json_path": str(tmp_path / f"{missing}.json"),
            "markdown_path": str(tmp_path / f"{missing}.md"),
        },
    )

    result = auto.materialize_missing_solar_map_backlog(
        request=request,
        root=tmp_path,
        limit=20,
    )

    assert result["trigger"] == "missing_artifact_repair"
    assert result["reviews_scanned"] == 2
    assert result["skipped_existing"] == 1
    assert result["materialized_count"] == 1
    assert len(calls) == 1
