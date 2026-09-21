from empire_os import sb
from scripts.buyer_discovery_preview import (
    _load_env,
    filter_market_rows,
    load_rows,
)


def rows():
    return [
        {"id": "a", "niche": "roofing", "metro": "Austin, TX"},
        {"id": "b", "niche": "commercial roofing", "metro": "austin, tx"},
        {"id": "c", "niche": "roofing", "metro": "Dallas, TX"},
        {"id": "d", "niche": "plumbing", "metro": "Austin, TX"},
    ]


def test_filter_market_rows_uses_canonical_niche_family_and_metro():
    selected = filter_market_rows(
        rows(),
        niche="roofing",
        metro="Austin, TX",
    )
    assert [row["id"] for row in selected] == ["a", "b"]


def test_filter_market_rows_allows_single_dimension_or_unscoped():
    assert [row["id"] for row in filter_market_rows(
        rows(),
        metro="Austin, TX",
    )] == ["a", "b", "d"]
    assert [row["id"] for row in filter_market_rows(rows())] == [
        "a", "b", "c", "d",
    ]



def test_load_rows_projects_only_accepted_acquisition_site(monkeypatch):
    prospect_id = "11111111-1111-4111-8111-111111111111"
    calls = []

    def fake_select(
        table,
        columns="*",
        filters=None,
        order=None,
        limit=1000,
        offset=0,
    ):
        calls.append((table, order, offset))
        if offset:
            return []
        if table == "prospects":
            return [{
                "id": prospect_id,
                "business_name": "All Star Roofing",
                "niche": "roofing",
                "metro": "Austin, TX",
                "website": None,
            }]
        if table == "prospect_entity_links":
            return [{
                "prospect_id": prospect_id,
                "entity_id": "22222222-2222-4222-8222-222222222222",
                "match_score": 1.0,
                "active": True,
            }]
        if table == "prospect_acquisitions":
            return [{
                "prospect_id": prospect_id,
                "created_at": "2026-09-17T09:40:11Z",
                "evidence": {
                    "quality": {
                        "accepted": True,
                        "confidence": 100,
                        "source_role": "identity_or_direct",
                    },
                    "raw": {
                        "business_website": (
                            "https://www.allstarroofingtexas.com/"
                        )
                    },
                },
            }]
        raise AssertionError(table)

    monkeypatch.setattr(sb, "_configured", lambda: True)
    monkeypatch.setattr(sb, "select", fake_select)

    loaded = load_rows()
    assert len(loaded) == 1
    assert loaded[0]["entity_id"] == (
        "22222222-2222-4222-8222-222222222222"
    )
    assert loaded[0]["_acquisition_evidence"]["quality"]["accepted"] is True
    acquisition_calls = [
        call for call in calls if call[0] == "prospect_acquisitions"
    ]
    assert acquisition_calls[0][1] == "created_at.desc"


def test_load_env_uses_canonical_runtime_loader(tmp_path, monkeypatch):
    runtime_env = tmp_path / "empire.env"
    runtime_env.write_text(
        "SUPABASE_URL=https://canonical.supabase.co\n"
        "SUPABASE_SERVICE_KEY=canonical-key\n"
    )
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_KEY", raising=False)

    env = _load_env(runtime_env)

    assert env["SUPABASE_URL"] == "https://canonical.supabase.co"
    assert env["SUPABASE_SERVICE_KEY"] == "canonical-key"
    assert "SUPABASE_URL" not in __import__("os").environ
    assert "SUPABASE_SERVICE_KEY" not in __import__("os").environ


def test_default_runtime_env_path_is_user_service_secret_source():
    import scripts.buyer_discovery_preview as preview

    assert preview.ENV_PATH.endswith("/runtime/secrets/outbound.env")
