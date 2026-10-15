"""Data Exchange buyer-proof sample; synthetic fixtures are test-only."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from empire_os.data_exchange_evidence_dossier import (
    build_internal_construction_dossier, FIELD_RIGHTS_HOLDS,
    PLANNING_RIGHTS, PROCUREMENT_RIGHTS,
)
from test_data_exchange_agi_bridge import (
    NOW, source, procurement as procurement_fixture,
)


def review(*, changed=False, proc=None, max_sample=8, observed_at=NOW):
    return build_internal_construction_dossier(
        snapshots=source(changed=changed),
        procurement=proc,
        reviewed_at=observed_at,
        max_sample=max_sample,
    )


def test_internal_dossier_is_evidence_report_not_saleable_list():
    d = review()
    assert d["purpose"] == "INTERNAL_BUYER_VALUE_VALIDATION_ONLY"
    assert d["planning_records_available"] == 1
    assert d["planning_records_in_sample"] == 1
    assert d["sample_is_complete"] is True
    assert d["source_change_count"] == 0
    assert d["procurement_notices_in_sample"] == 0
    assert d["cross_source_project_match_count"] == 0
    assert d["rights_catalogue"] == [PLANNING_RIGHTS]
    assert d["rights_blockers"] == list(FIELD_RIGHTS_HOLDS)
    assert d["licence_review_status"] == (
        "SOURCE_LICENCE_IDENTIFIED_FIELD_RIGHTS_HELD"
    )
    assert d["customer_delivery_enabled"] is False
    assert d["data_resale_authorized"] is False
    assert d["buyer_interest_verified"] is False
    assert d["paid_pilot_verified"] is False
    assert d["predictive_accuracy_verified"] is False
    assert d["realised_revenue_verified"] is False
    assert d["execution_authority"] == "NONE"
    r = d["planning_records"][0]
    assert r["source_record_id"] == "1739547"
    assert r["source_url"] == "https://www.planning.data.gov.uk/entity/1739547"
    assert r["project_commencement_verified"] is False
    assert r["buyer_intent_verified"] is False
    assert r["commercial_distribution_permitted"] is False


def test_real_change_is_source_change_not_new_buyer():
    d = review(changed=True)
    assert d["source_change_count"] == 1
    assert d["planning_records"][0]["observed_history_change"] is True
    assert d["planning_records"][0]["buyer_intent_verified"] is False
    assert d["predictive_accuracy_verified"] is False


def test_two_official_sources_remain_separate_not_false_linkage():
    d = review(proc=procurement_fixture())
    assert d["procurement_notices_in_sample"] == 1
    assert d["cross_source_relation"] == "NOT_ESTABLISHED"
    assert d["cross_source_project_match_count"] == 0
    assert d["rights_catalogue"] == [PLANNING_RIGHTS, PROCUREMENT_RIGHTS]
    assert d["rights_catalogue"][0]["required_attribution"] == (
        "© Crown copyright and database right 2026"
    )
    notice = d["procurement_notices"][0]
    assert notice["release_id"] == "096757-2026"
    assert notice["cross_source_site_link_verified"] is False
    assert "PRIVATE-TENDER-DESCRIPTION" not in str(d)
    assert "private@example.org" not in str(d)


@pytest.mark.parametrize("edit", [
    lambda d: d["notices"][0].update({"contact_email": "private@example.org"}),
    lambda d: d.update({"cross_source_entity_link": "VERIFIED"}),
    lambda d: d.update({"data_resale_authorized": True}),
    lambda d: d.update({"source_rights_status": "CLEARED"}),
    lambda d: d["notices"][0].update({"source_url": "https://evil.example"}),
])
def test_procurement_tampering_rejected_before_report(edit):
    data = deepcopy(procurement_fixture())
    edit(data)
    with pytest.raises(ValueError):
        review(proc=data)


def test_source_preview_private_contact_is_rejected_before_report():
    snapshots = source(changed=True)
    snapshots[1]["records"][0]["email"] = "private@example.org"
    with pytest.raises(ValueError):
        build_internal_construction_dossier(
            snapshots=snapshots, procurement=None, reviewed_at=NOW,
        )


def test_aged_source_observation_cannot_be_dressed_as_current():
    with pytest.raises(ValueError, match="coverage or freshness"):
        review(observed_at=NOW + timedelta(days=96))


def test_bounds_and_time_scope():
    for sample in [0, 9, -1, True, 1.1]:
        with pytest.raises(ValueError, match="sample bounds"):
            review(max_sample=sample)
    with pytest.raises(ValueError, match="timezone"):
        review(observed_at=datetime(2026, 10, 14))


def test_identical_inputs_generate_same_report():
    assert review(changed=True, proc=procurement_fixture()) == review(
        changed=True, proc=procurement_fixture()
    )


def test_forged_customer_eligibility_does_not_remove_rights_blockers():
    samples = source()
    samples[1]["rights_review_eligible"] = True
    # Upstream approval spoof is rejected by history validator.
    # Even explicit upstream approvals cannot grant external delivery.
    from empire_os.data_exchange_evidence_dossier import (
        build_internal_construction_dossier,
    )
    with pytest.raises(ValueError):
        build_internal_construction_dossier(
            snapshots=samples, procurement=None, reviewed_at=NOW,
        )


def test_dossier_operator_no_network_no_writes_and_internal_only(
    tmp_path, capsys,
):
    import json
    from scripts.preview_data_exchange_evidence_dossier import main

    snapshots = source()
    paths = [tmp_path / "a.json", tmp_path / "b.json"]
    for path, sample in zip(paths, snapshots):
        path.write_text(json.dumps(sample), encoding="utf-8")
    notice = tmp_path / "public_procurement.json"
    notice.write_text(json.dumps(procurement_fixture()), encoding="utf-8")
    original_names = sorted(p.name for p in tmp_path.iterdir())
    code = main([
        "--snapshots", *(str(p) for p in paths),
        "--procurement", str(notice), "--limit", "1",
    ])
    result = json.loads(capsys.readouterr().out)
    assert code == 0
    assert result["planning_records_in_sample"] == 1
    assert result["procurement_notices_in_sample"] == 1
    assert result["customer_preview_not_distributable"] is True
    assert result["execution_authority"] == "NONE"
    assert sorted(p.name for p in tmp_path.iterdir()) == original_names


def test_dossier_operator_bad_file_holds_without_echoing_secret(tmp_path, capsys):
    import json
    from scripts.preview_data_exchange_evidence_dossier import main

    payload = tmp_path / "untrusted.json"
    payload.write_text('{"secret":"DONOTLEAKCUSTOMER"}', encoding="utf-8")
    assert main([
        "--snapshots", str(payload), str(payload),
    ]) == 2
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "HOLD"
    assert "DONOTLEAKCUSTOMER" not in str(result)
    assert result["customer_delivery_enabled"] is False
    assert result["execution_authority"] == "NONE"
