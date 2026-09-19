import pytest

from empire_os.advertising_adapters import (
    AdvertisingAdapterUnavailable,
    DisabledAdvertisingReadAdapter,
    InjectedAdvertisingReadAdapter,
)


def test_disabled_adapter_never_fetches():
    adapter = DisabledAdvertisingReadAdapter("google")
    assert adapter.status().available is False
    with pytest.raises(AdvertisingAdapterUnavailable, match="disabled"):
        adapter.observations(
            start_date="2026-09-01",
            end_date="2026-09-19",
        )


def test_google_injected_reader_returns_observations_without_network():
    calls = []

    def fetcher(account_id, start_date, end_date):
        calls.append((account_id, start_date, end_date))
        return [{
            "campaign_id": "g-campaign-1",
            "creative_id": "g-creative-1",
            "spend_cents": 10000,
            "attributed_revenue_cents": 25000,
            "impressions": 1000,
            "clicks": 50,
            "conversions": 4,
            "observed_at": "2026-09-19T22:55:00+00:00",
        }]

    adapter = InjectedAdvertisingReadAdapter(
        "google",
        "account-1",
        fetcher,
    )
    rows = adapter.observations(
        start_date="2026-09-01",
        end_date="2026-09-19",
    )
    assert calls == [("account-1", "2026-09-01", "2026-09-19")]
    assert rows[0].platform == "google"
    assert rows[0].roas == 2.5
    assert rows[0].source == "google_ads_injected_read_transport"


def test_meta_reader_preserves_unknown_attribution():
    adapter = InjectedAdvertisingReadAdapter(
        "meta",
        "account-2",
        lambda *args: [{
            "campaign_id": "m-campaign-1",
            "spend_cents": 5000,
            "attributed_revenue_cents": None,
            "observed_at": "2026-09-19T22:55:00+00:00",
        }],
    )
    row = adapter.observations(
        start_date="2026-09-01",
        end_date="2026-09-19",
    )[0]
    assert row.attributed_revenue_cents is None
    assert row.roas is None


def test_unknown_provider_is_rejected():
    with pytest.raises(ValueError, match="unsupported advertising provider"):
        InjectedAdvertisingReadAdapter(
            "mystery",
            "account-1",
            lambda *args: [],
        )


def test_invalid_transport_row_fails_closed():
    adapter = InjectedAdvertisingReadAdapter(
        "google",
        "account-1",
        lambda *args: [{"spend_cents": 1}],
    )
    with pytest.raises(
        AdvertisingAdapterUnavailable,
        match="campaign_id and observed_at",
    ):
        adapter.observations(
            start_date="2026-09-01",
            end_date="2026-09-19",
        )
