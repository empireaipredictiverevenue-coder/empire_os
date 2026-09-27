from pathlib import Path


def _source(relative: str) -> str:
    root = Path(__file__).resolve().parents[1]
    return root.joinpath(relative).read_text(encoding="utf-8")


def test_idle_asset_agent_has_no_database_vendor_transport():
    source = _source("empire_os/agents/idle_asset_sniper_agent.py")

    assert "SUPABASE_URL" not in source
    assert "SUPABASE_SERVICE_KEY" not in source
    assert "supabase.co" not in source
    assert "/rest/v1/" not in source


def test_telephony_webhook_has_no_database_vendor_transport():
    source = _source("empire_os/telephony_webhook.py")

    assert "SUPABASE_URL" not in source
    assert "SUPABASE_KEY" not in source
    assert "supabase.co" not in source
    assert "/rest/v1/" not in source
