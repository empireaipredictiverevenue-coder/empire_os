"""NewsJack official-source intake may propose MediaOS research, never claims."""
import json

import pytest

from empire_os.jev_newsjack_adapters import (
    prepare_official_news_media_os_preview,
)
from empire_os.jev_newsjack_traffic import review_newsjack_jev_traffic


AS_OF = "2026-11-04T11:35:00+00:00"


def signal(*, source="federal", day="2026-11-03"):
    if source == "federal":
        return {
            "signal_id": "federal_register:2026-12345",
            "title": "Solar Installation Technical Requirements",
            "sector": "solar", "market": "US",
            "primary_source_url":
                "https://www.federalregister.gov/documents/2026/11/03/2026-12345/solar-installation",
            "published_at": None,
            "publication_date": day,
            "publication_date_verified": True,
            "observed_at": AS_OF,
            "source_kind": "federal_register",
            "evidence_refs": ["federalregister:api:abc123"],
            "independent_corroboration_verified": False,
            "destination_live_verified": False,
        }
    return {
        "signal_id": "govuk:sample",
        "title": "Solar Installer Policy Guidance",
        "sector": "solar", "market": "GB",
        "primary_source_url":
            "https://www.gov.uk/guidance/solar-installer-guidance",
        "published_at": "2026-11-03T12:00:00+00:00",
        "observed_at": AS_OF,
        "source_kind": "govuk_content_api",
        "evidence_refs": ["govuk:content_api:ref123"],
        "independent_corroboration_verified": False,
        "destination_live_verified": False,
    }


def review(signals, markets=("GB", "US")):
    return review_newsjack_jev_traffic(
        signals, as_of=AS_OF, approved_sectors=("solar",),
        approved_markets=markets,
    )


def test_official_federal_date_only_and_govuk_instant_preserved():
    packet = review([signal(), signal(source="govuk")])
    assert packet["status_counts"] == {"RESEARCH_REVIEW": 2}
    output = prepare_official_news_media_os_preview(packet, as_of=AS_OF)
    assert output["candidate_count"] == 2
    by_id = {p["newsjack_signal_id"]: p for p in output["research_packs"]}
    federal = by_id["federal_register:2026-12345"]
    govuk = by_id["govuk:sample"]
    assert federal["published_at"] is None
    assert federal["publication_date"] == "2026-11-03"
    assert federal["publication_precision"] == "day"
    assert govuk["publication_precision"] == "instant"
    assert federal["sources"][0]["rights_state"] == "RESEARCH_REFERENCE_ONLY"
    assert federal["sources"][0]["source_type"] == "official_news_metadata_reference"
    assert federal["claims"] == []
    assert federal["script_ready"] is False
    assert federal["claim_verification_required"] is True
    assert federal["public_publish_authorized"] is False
    assert output["media_os_queue_written"] is False
    assert output["verified_claim_count"] == 0
    assert output["execution_authority"] == "none"


def test_stale_future_and_unapproved_signals_never_enter_media():
    packet = review([signal(day="2026-10-14"),
                     signal(source="govuk")], markets=("US",))
    output = prepare_official_news_media_os_preview(packet, as_of=AS_OF)
    assert output["candidate_count"] == 0
    assert output["held_count"] == 2
    assert output["research_packs"] == []


def test_false_earned_proof_and_nonofficial_host_not_promoted():
    a = signal()
    a["primary_source_url"] = "https://example.org/solar-story"
    b = signal(source="govuk")
    b["evidence_refs"] = ["source:untrusted"]
    out = prepare_official_news_media_os_preview(
        review([a, b]), as_of=AS_OF)
    assert out["candidate_count"] == 0
    assert out["held_count"] == 2


def test_cannot_launder_untrusted_review_or_claims():
    r = review([signal()])
    r["publishing_enabled"] = True
    with pytest.raises(ValueError, match="trusted"):
        prepare_official_news_media_os_preview(r, as_of=AS_OF)
    r["publishing_enabled"] = False
    r["candidates"][0]["actual_revenue"] = True
    assert prepare_official_news_media_os_preview(
        r, as_of=AS_OF)["candidate_count"] == 0


def test_official_cli_media_os_preview_without_network(monkeypatch, capsys):
    import sys
    from scripts import review_jev_official_news_sources as cli

    def local_only(**kwargs):
        assert kwargs["term"] == "solar"
        return {
            "schema_version": "empire.organic.official_source_intake.v1",
            "source": "us_federal_register",
            "source_url": "https://www.federalregister.gov/api/v1/documents.json",
            "candidate_count": 1,
            "signals": [signal()],
        }

    monkeypatch.setattr(cli, "federal_register_signals", local_only)
    monkeypatch.setattr(sys, "argv", [
        "newsjack-official", "--federal-register-term", "solar",
        "--sector", "solar", "--as-of", AS_OF,
        "--media-os-review-preview",
    ])
    assert cli.main() == 0
    response = json.loads(capsys.readouterr().out)
    assert response["media_os_research_preview"]["candidate_count"] == 1
    assert response["media_os_research_preview"]["media_os_queue_written"] is False
    assert response["source_claims_fully_verified"] is False
    assert response["publications_made"] == 0
    assert response["outbound_sent"] is False
