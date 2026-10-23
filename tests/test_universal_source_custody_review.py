"""Source custody boundary regression: no new ingestion, false revenue, PII or tenant authority."""
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlsplit

import pytest

from empire_os.economic_signal_fabric import (
    EconomicSignalError,
    validate_economic_signal,
)
from empire_os.universal_source_custody_review import (
    SOURCE_CATALOG,
    gdelt_doc_query_url,
    review_universal_observations,
    sec_submissions_url,
)

NOW = datetime(2026, 10, 24, 12, tzinfo=timezone.utc)


def source(**updates):
    row = {
        "provider": "gdelt_doc",
        "provider_record_id": "gdelt-001",
        "provider_url": "https://api.gdeltproject.org/api/v2/doc/doc?mode=artlist",
        "event_kind": "NEWS_MENTION",
        "published_at": (NOW - timedelta(hours=3)).isoformat(),
        "observed_at": (NOW - timedelta(hours=2)).isoformat(),
        "data_classification": "public_nonpersonal",
        "rights_claim": "public_reference",
    }
    row.update(updates)
    return row


def test_review_contract_stays_offline_and_does_not_promote_source():
    result = review_universal_observations([source()], as_of=NOW)
    assert result["source_count_structurally_reviewed"] == 1
    assert result["category_counts"] == {"NEWS": 1}
    assert result["source_count_rejected"] == 0
    assert result["redis_stream_written"] is False
    assert result["empiredb_write"] is False
    assert result["empiredb_tables_created"] is False
    assert result["source_connections_activated"] is False
    assert result["vector_embeddings_created"] is False
    assert result["crm_prospects_created"] is False
    assert result["recognized_revenue_cents"] is None
    assert result["gpu_spend_cents"] == 0
    assert result["execution_authority"] == "none"
    row = result["reviewed_sources"][0]
    assert row["stage"] == "SOURCE_REFERENCE_REVIEW_ONLY"
    assert row["source_host"] == "api.gdeltproject.org"
    assert row["licensed_for_downstream_use"] is False
    assert row["buyer_intent_verified"] is False
    assert row["revenue_verified"] is False


def test_review_does_not_expose_raw_provider_url_or_data_fields():
    secret = "should-not-be-echoed"
    row = source(provider_record_id="opaque-news-123")
    row["provider_url"] = (
        "https://api.gdeltproject.org/api/v2/doc/doc?secret=" + secret
    )
    out = review_universal_observations([row], as_of=NOW)
    assert secret not in str(out)
    assert "opaque-news-123" not in str(out)


def test_untrusted_claimed_revenue_cannot_enter_source_contract():
    row = source()
    row["amount_usd"] = 888888
    out = review_universal_observations([row], as_of=NOW)
    assert out["source_count_rejected"] == 1
    assert out["source_count_structurally_reviewed"] == 0
    assert out["recognized_revenue_cents"] is None


def test_untrusted_pii_raw_body_and_tenant_binding_fields_rejected():
    for key in ("email", "contact", "raw", "tenant_id", "buyer_id", "payload"):
        row = source()
        row[key] = {"sensitive": "person@example.com"}
        out = review_universal_observations([row], as_of=NOW)
        assert out["source_count_rejected"] == 1
        assert "person@example.com" not in str(out)


def test_disputed_rights_and_personal_data_remain_blocked():
    out = review_universal_observations([
        source(data_classification="personal_data", rights_claim="licence_claimed")
    ], as_of=NOW)
    row = out["reviewed_sources"][0]
    assert "PERSONAL_DATA_CLASSIFICATION_REQUIRES_REVIEW" in row["blockers"]
    assert row["licensed_for_downstream_use"] is False
    assert row["independent_source_verified"] is False


def test_duplicate_provider_record_is_not_counted_twice():
    out = review_universal_observations([source(), source()], as_of=NOW)
    assert out["source_count_structurally_reviewed"] == 1
    assert out["source_count_rejected"] == 1
    assert "duplicate source observation" in out["rejections"][0]["reason"]


def test_gdelt_api_query_uses_encoded_parameters_without_network():
    url = gdelt_doc_query_url("(roofing OR solar)", timespan_hours=3)
    parts = urlsplit(url)
    qs = parse_qs(parts.query)
    assert parts.hostname == "api.gdeltproject.org"
    assert qs["query"] == ["(roofing OR solar)"]
    assert qs["mode"] == ["artlist"]
    assert qs["format"] == ["json"]
    assert qs["timespan"] == ["3h"]
    assert qs["maxrecords"] == ["100"]


@pytest.mark.parametrize("bad", ["AAPL", "TSLA", "", "0", "99999999999", "A/1", "１２"])
def test_edgar_ticker_or_bad_cik_rejected(bad):
    with pytest.raises(ValueError, match="CIK"):
        sec_submissions_url(bad)


def test_edgar_official_numeric_cik_url_only():
    assert sec_submissions_url("320193") == (
        "https://data.sec.gov/submissions/CIK0000320193.json"
    )
    out = review_universal_observations([source(
        provider="sec_edgar", event_kind="SEC_FILING",
        provider_record_id="320193", provider_url=sec_submissions_url("320193"),
    )], as_of=NOW)
    assert out["source_count_structurally_reviewed"] == 1
    assert out["category_counts"]["LEGAL"] == 1
    bad = source(
        provider="sec_edgar", event_kind="SEC_FILING",
        provider_record_id="320193",
        provider_url="https://data.sec.gov/submissions/CIKAAPL.json",
    )
    assert review_universal_observations([bad], as_of=NOW)[
        "source_count_rejected"
    ] == 1


def test_spoofed_official_hostname_rejected():
    for url in (
        "http://api.gdeltproject.org/doc",
        "https://api.gdeltproject.org.evil.invalid/doc",
        "https://user@api.gdeltproject.org/doc",
        "https://api.gdeltproject.org:444/doc",
        "https://127.0.0.1/doc",
    ):
        out = review_universal_observations([source(provider_url=url)], as_of=NOW)
        assert out["source_count_rejected"] == 1, url


def test_future_and_impossible_events_rejected():
    for changed in (
        {"observed_at": (NOW + timedelta(seconds=1)).isoformat()},
        {"published_at": NOW.isoformat()},
        {"published_at": "2026-10-24T11:00:00"},  # naive
    ):
        assert review_universal_observations(
            [source(**changed)], as_of=NOW
        )["source_count_rejected"] == 1


def test_historical_events_not_mistaken_for_fresh_intent():
    row = source(
        published_at=(NOW - timedelta(days=365)).isoformat(),
        observed_at=(NOW - timedelta(days=1)).isoformat(),
    )
    out = review_universal_observations([row], as_of=NOW)
    assert "HISTORICAL_EVIDENCE_REQUIRES_FRESHNESS_REVIEW" in out[
        "reviewed_sources"
    ][0]["blockers"]


def test_no_unreviewed_paid_or_licensed_provider_can_enter():
    for provider in ("pacer", "licensed_property", "licensed_markets"):
        entry = SOURCE_CATALOG[provider]
        row = source(
            provider=provider,
            event_kind=sorted(entry["kinds"])[0],
            provider_url="https://pacer.uscourts.gov/" if provider == "pacer" else "https://example.com/",
        )
        result = review_universal_observations([row], as_of=NOW)
        if provider == "pacer":
            assert "PROVIDER_ACCESS_NOT_AUTHORISED" in result["reviewed_sources"][0]["blockers"]
        else:
            assert result["source_count_rejected"] == 1


def test_source_stage_cannot_pass_original_economic_signal_contract():
    out = review_universal_observations([source()], as_of=NOW)
    with pytest.raises(EconomicSignalError):
        validate_economic_signal(
            out["reviewed_sources"][0],
            expected_tenant_id="a5f7cba7-4cf1-4f03-9a53-a88e9c0b412e",
            as_of=NOW,
        )


def test_scoping_and_limits_fail_closed():
    with pytest.raises(ValueError, match="bounded"):
        review_universal_observations([source()] * 101, as_of=NOW)
    with pytest.raises(ValueError, match="timezone"):
        review_universal_observations([], as_of=datetime(2026, 10, 24))
    with pytest.raises(ValueError, match="1-24h"):
        gdelt_doc_query_url("x", timespan_hours=25)


def test_supported_sources_are_declared_but_not_connected():
    out = review_universal_observations([], as_of=NOW)
    assert len(SOURCE_CATALOG) >= 14
    assert out["source_count_structurally_reviewed"] == 0
    assert out["source_connections_activated"] is False
    assert out["next_stage"] == "CANONICAL_SOURCE_RIGHTS_AND_ENTITY_BINDING_REVIEW"
