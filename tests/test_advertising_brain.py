import pytest

from empire_os.advertising_brain import normalise_ad_observation


def test_observation_computes_roas_and_profit_roas():
    observation = normalise_ad_observation({
        "platform": "google",
        "campaign_id": "campaign-1",
        "creative_id": "creative-1",
        "spend_cents": 10000,
        "attributed_revenue_cents": 30000,
        "attributed_gross_profit_cents": 15000,
        "impressions": 10000,
        "clicks": 500,
        "conversions": 20,
        "observed_at": "2026-09-19T18:00:00+00:00",
        "source": "google_ads_read_adapter",
    })
    assert observation.roas == 3.0
    assert observation.profit_roas == 1.5


def test_unknown_revenue_stays_unknown():
    observation = normalise_ad_observation({
        "platform": "meta",
        "campaign_id": "campaign-1",
        "spend_cents": 2500,
        "attributed_revenue_cents": None,
        "attributed_gross_profit_cents": None,
        "observed_at": "2026-09-19T18:00:00+00:00",
        "source": "meta_ads_read_adapter",
    })
    assert observation.roas is None
    assert observation.profit_roas is None


def test_zero_spend_does_not_invent_infinite_roas():
    observation = normalise_ad_observation({
        "platform": "google",
        "campaign_id": "campaign-1",
        "spend_cents": 0,
        "attributed_revenue_cents": 1000,
        "observed_at": "2026-09-19T18:00:00+00:00",
        "source": "google_ads_read_adapter",
    })
    assert observation.roas is None


def test_negative_spend_is_rejected():
    with pytest.raises(ValueError, match="nonnegative"):
        normalise_ad_observation({
            "platform": "google",
            "campaign_id": "campaign-1",
            "spend_cents": -1,
            "observed_at": "2026-09-19T18:00:00+00:00",
            "source": "google_ads_read_adapter",
        })


def test_unknown_platform_fails_closed():
    with pytest.raises(ValueError, match="unsupported ad platform"):
        normalise_ad_observation({
            "platform": "mystery",
            "campaign_id": "campaign-1",
            "spend_cents": 0,
            "observed_at": "2026-09-19T18:00:00+00:00",
            "source": "adapter",
        })


def test_observed_at_requires_timezone():
    with pytest.raises(ValueError, match="include timezone"):
        normalise_ad_observation({
            "platform": "google",
            "campaign_id": "campaign-1",
            "spend_cents": 100,
            "observed_at": "2026-09-19T20:55:00",
            "source": "google_ads_read_adapter",
        })


def test_observed_at_requires_iso_timestamp():
    with pytest.raises(ValueError, match="ISO-8601"):
        normalise_ad_observation({
            "platform": "google",
            "campaign_id": "campaign-1",
            "spend_cents": 100,
            "observed_at": "not-a-time",
            "source": "google_ads_read_adapter",
        })
