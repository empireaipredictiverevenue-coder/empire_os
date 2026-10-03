from pathlib import Path

from empire_os.solar_sku_premarket import build_solar_sku_premarket_status


ROOT = Path(__file__).resolve().parents[1]


def test_all_13_localized_solar_skus_are_classified():
    rows = build_solar_sku_premarket_status(repo_root=ROOT)
    assert len(rows) == 13
    assert len({row.product_code for row in rows}) == 13


def test_current_gb_has_real_artifacts_but_retained_provenance_gate_remains_closed():
    rows = build_solar_sku_premarket_status(repo_root=ROOT)
    gb = next(row for row in rows if row.country_code == "GB")
    assert gb.source_pack_configured is True
    assert gb.solar_specific_source_configured is True
    assert gb.selected_source == "gb_recc_solar"
    assert gb.exact_product_artifact_count >= 2
    assert gb.retained_source_provenance_verified is False
    assert gb.campaign_smoke_ready is False
    assert "retained_source_provenance_missing" in gb.blockers


def test_us_source_pack_is_explicitly_blocked():
    rows = build_solar_sku_premarket_status(repo_root=ROOT)
    us = next(row for row in rows if row.country_code == "US")
    assert us.source_pack_configured is False
    assert "source_pack_missing" in us.blockers
    assert us.campaign_smoke_ready is False


def test_only_known_countries_have_solar_specific_source_contracts_today():
    rows = build_solar_sku_premarket_status(repo_root=ROOT)
    configured = {
        row.country_code
        for row in rows
        if row.solar_specific_source_configured
    }
    assert configured == {"GB", "AU", "IE", "DE", "FR"}


def test_no_solar_sku_is_campaign_ready_without_exact_artifact_and_provenance():
    rows = build_solar_sku_premarket_status(repo_root=ROOT)
    assert not any(row.campaign_smoke_ready for row in rows)


def test_explicit_provenance_cannot_bypass_missing_artifact_or_source():
    rows = build_solar_sku_premarket_status(
        repo_root=ROOT,
        retained_source_provenance={
            "GB": True,
            "AU": True,
            "US": True,
        },
    )
    gb = next(row for row in rows if row.country_code == "GB")
    au = next(row for row in rows if row.country_code == "AU")
    us = next(row for row in rows if row.country_code == "US")
    assert gb.campaign_smoke_ready is True
    assert au.campaign_smoke_ready is False
    assert "exact_product_artifact_missing" in au.blockers
    assert us.campaign_smoke_ready is False
    assert "source_pack_missing" in us.blockers
