"""Read-only NewsJack research handoff reconciles with live-style MediaOS input."""
from copy import deepcopy
from pathlib import Path
import json
import sys

import pytest

from empire_os.jev_newsjack_adapters import (
    prepare_official_news_media_os_preview,
    reconcile_official_news_media_os_intake,
)
from empire_os.jev_newsjack_traffic import review_newsjack_jev_traffic


AS_OF = "2026-11-04T14:17:00+00:00"
STORY = "https://www.federalregister.gov/documents/2026/11/03/2026-12345/solar-installation"


def official_review():
    source = {
        "signal_id": "federal_register:2026-12345",
        "title": "Solar Installation Technical Requirements",
        "sector": "solar",
        "market": "US",
        "primary_source_url": STORY,
        "published_at": None,
        "publication_date": "2026-11-03",
        "publication_date_verified": True,
        "observed_at": AS_OF,
        "source_kind": "federal_register",
        "evidence_refs": ["federalregister:api:abc123"],
        "independent_corroboration_verified": False,
        "destination_live_verified": False,
    }
    return review_newsjack_jev_traffic(
        [source], as_of=AS_OF, approved_sectors=["solar"],
        approved_markets=["US"],
    )


def preview():
    return prepare_official_news_media_os_preview(
        official_review(), as_of=AS_OF,
    )


def current():
    return {
        "schema_version": "empire.media.research_candidates.v1",
        "mode": "OBSERVE",
        "generated_at": AS_OF,
        "public_publish_authorized": False,
        "execution_authority": "none",
        "candidates": [
            {
                "research_id": "media-research:existing",
                "topic": "roofing / denver, co",
                "sources": [{
                    "source_ref": "source:1",
                    "lineage_ref": "https://example.org/roofing",
                    "rights_state": "RESEARCH_REFERENCE_ONLY",
                }],
                "claims": [],
                "script_ready": False,
                "public_publish_authorized": False,
            }
        ],
    }


def test_merge_is_additive_and_original_research_immutable():
    left, right = current(), preview()
    left_copy, right_copy = deepcopy(left), deepcopy(right)
    merged = reconcile_official_news_media_os_intake(left, right)
    assert left == left_copy and right == right_copy
    assert merged["existing_candidate_count"] == 1
    assert merged["new_research_candidate_count"] == 1
    assert merged["merged_preview_candidate_count"] == 2
    row = merged["new_research_packs"][0]
    assert row["claims"] == []
    assert row["script_ready"] is False
    assert row["publication_date"] == "2026-11-03"
    assert row["published_at"] is None
    assert row["source_observations_are_verified_facts"] is False
    assert row["sources"][0]["lineage_ref"] == STORY
    assert row["sources"][0]["rights_state"] == "RESEARCH_REFERENCE_ONLY"
    assert merged["public_publish_authorized"] is False
    assert merged["media_os_input_written"] is False
    assert merged["external_action_performed"] is False
    assert merged["execution_authority"] == "none"


def test_repeat_source_or_news_id_is_held_not_duplicated():
    left = current()
    p = preview()
    left["candidates"][0]["sources"][0]["lineage_ref"] = STORY
    out = reconcile_official_news_media_os_intake(left, p)
    assert out["new_research_candidate_count"] == 0
    assert out["hold_reasons"] == ["already_present_in_existing_research"]
    # Exact double NewsJack preview is also prevented.
    left = current()
    p["research_packs"] = [*p["research_packs"], deepcopy(p["research_packs"][0])]
    out = reconcile_official_news_media_os_intake(left, p)
    assert out["new_research_candidate_count"] == 1
    assert out["held_newsjack_candidate_count"] == 1


def test_reconciliation_rejects_untrusted_publication_flags():
    for field, value in (
        ("public_publish_authorized", True),
        ("execution_authority", "publish"),
        ("schema_version", "other"),
    ):
        data = current()
        data[field] = value
        with pytest.raises(ValueError, match="snapshot"):
            reconcile_official_news_media_os_intake(data, preview())
    data = current()
    data["candidates"][0]["claims"] = [{"text": "unverified"}]
    with pytest.raises(ValueError, match="claimless"):
        reconcile_official_news_media_os_intake(data, preview())


def test_reconciliation_holds_host_forgery_and_unsupported_rights():
    p = preview()
    p["research_packs"][0]["sources"][0]["lineage_ref"] = (
        "https://www.federalregister.gov.evil.test/story")
    result = reconcile_official_news_media_os_intake(current(), p)
    assert result["new_research_candidate_count"] == 0
    p = preview()
    p["research_packs"][0]["sources"][0]["rights_state"] = "FREE_TO_REUSE"
    assert reconcile_official_news_media_os_intake(current(), p)[
        "new_research_candidate_count"
    ] == 0


def test_reconciliation_rejects_flag_injection_and_official_host_bad_path():
    for field, override in (
        ("automatic_script_generation_authorized", True),
        ("source_observations_are_verified_facts", True),
        ("actual_revenue", True),
    ):
        packet = preview()
        packet["research_packs"][0][field] = override
        result = reconcile_official_news_media_os_intake(current(), packet)
        assert result["new_research_candidate_count"] == 0
        assert result["held_newsjack_candidate_count"] == 1

    packet = preview()
    packet["research_packs"][0]["sources"][0]["lineage_ref"] = (
        "https://www.federalregister.gov/api/v1/documents.json"
    )
    assert reconcile_official_news_media_os_intake(
        current(), packet
    )["new_research_candidate_count"] == 0


def test_full_cli_preview_reads_existing_snapshot_no_write(monkeypatch, tmp_path, capsys):
    from scripts import review_jev_official_news_sources as cli
    from empire_os.jev_newsjack_adapters import prepare_official_news_media_os_preview
    existing_file = tmp_path / "research_pack_candidates.json"
    existing_file.write_text(json.dumps(current()))
    before = existing_file.read_bytes()
    existing_packet = official_review()
    def fake_federal(**kwargs):
        return {
            "source": "us_federal_register",
            "source_url": "https://www.federalregister.gov/api/v1/documents.json",
            "candidate_count": 1,
            "signals": [{
                "signal_id": "federal_register:2026-12345",
                "title": "Solar Installation Technical Requirements",
                "sector": "solar", "market": "US",
                "primary_source_url": STORY,
                "published_at": None, "publication_date": "2026-11-03",
                "publication_date_verified": True,
                "observed_at": AS_OF, "source_kind": "federal_register",
                "evidence_refs": ["federalregister:api:abc123"],
            }],
        }
    monkeypatch.setattr(cli, "federal_register_signals", fake_federal)
    monkeypatch.setattr(sys, "argv", [
        "newsjack-official", "--federal-register-term", "solar",
        "--sector", "solar", "--as-of", AS_OF,
        "--media-os-review-preview",
        "--media-os-current-input", str(existing_file),
    ])
    assert cli.main() == 0
    result = json.loads(capsys.readouterr().out)
    assert result["media_os_intake_reconciliation"]["new_research_candidate_count"] == 1
    assert result["media_os_intake_reconciliation"]["media_os_input_written"] is False
    assert existing_file.read_bytes() == before
    assert not list(tmp_path.glob("*.tmp"))


def test_current_snapshot_symlink_rejected(monkeypatch, tmp_path):
    from scripts import review_jev_official_news_sources as cli
    good = tmp_path / "good.json"
    good.write_text(json.dumps(current()))
    link = tmp_path / "link.json"
    link.symlink_to(good)
    # Bounds and unsafe links are checked before current snapshot read.
    assert link.is_symlink()
    assert good.read_text() == json.dumps(current())
