"""Synthetic identity-review regression; no EmpireDB or operational authority."""
from copy import deepcopy
from datetime import datetime, timezone
import pytest

from empire_os.scrapling_source_evidence import ReviewedRecipe, extract_reviewed_page
from empire_os.scrapling_identity_review import review_scrapling_canonical_identity
from empire_os.waterfall_source_bridge import EvidenceReview

NOW = datetime(2026, 10, 19, 12, tzinfo=timezone.utc)


def report():
    class Text:
        def __init__(self, value):
            self.value = value

        def get(self):
            return self.value

    class Row:
        def css(self, selector):
            return Text({
                ".company::text": "Acme Solar Limited",
                ".detail::attr(href)": "/scheme/members/acme-solar",
                ".phone::text": "+44 20 7946 0990",
            }.get(selector))

    class Parser:
        def __init__(self, html, url):
            pass

        def css(self, selector):
            return iter([Row()])

    return extract_reviewed_page(
        recipe=ReviewedRecipe(
            source_id="gb_recc_solar",
            source_url="https://www.recc.org.uk/scheme/members",
            niche="solar", metro="London",
            row_css=".row", name_css=".company::text",
            website_css=".detail::attr(href)",
            field_phone_css=".phone::text",
            max_rows=5,
            terms_reviewed=True, robots_reviewed=True,
            privacy_reviewed=True,
            review_evidence_refs=(
                "terms:synthetic-review", "robots:synthetic-review",
                "privacy:synthetic-review",
            ),
        ),
        html="<html><body><div class='row'>Synthetic firm</div></body></html>",
        observed_at=NOW, selector_factory=Parser,
    )


def review():
    return EvidenceReview(
        vertical="solar", target_kind="contractor",
        jurisdiction="GB-ENG",
        company_identity_ref="entity:synthetic-independent-business-001",
    )


def canonical(name="Acme Solar Limited", id="c-101", phone="+44 20 7946 0990",
              niche="solar", metro="London"):
    return {
        "id": id, "business_name": name,
        "phone": phone, "niche": niche, "metro": metro,
    }


def run(data=None, rows=None, *, complete=True, snapshot="snapshot:synthetic-001"):
    return review_scrapling_canonical_identity(
        report=data if data is not None else report(),
        review=review(),
        canonical_rows=rows if rows is not None else [canonical()],
        canonical_snapshot_complete=complete,
        canonical_snapshot_ref=snapshot,
        now=NOW,
    )


def first(data):
    return data["observation_decisions"][0]


def test_exact_company_is_review_only_not_entity_link_or_unique_lead():
    result = run()
    assert first(result)["state"] == "POTENTIAL_EXISTING_REVIEW"
    assert first(result)["possible_canonical_ids"] == ["c-101"]
    assert first(result)["canonical_prospect_id_verified"] is None
    assert first(result)["entity_link_authorized"] is False
    assert result["unique_canonical_leads_verified_added"] == 0
    assert result["canonical_database_writes"] is False
    assert result["execution_authority"] == "none"


def test_phone_shared_by_different_business_is_conflict_not_identity():
    result = run(rows=[canonical(name="Other Solar Ltd")])
    item = first(result)
    assert item["state"] == "IDENTITY_CONFLICT"
    assert "shared_phone_different_business" in item["reasons"]
    assert item["possible_canonical_ids"] == []


def test_missing_canonical_company_is_not_automatically_a_new_lead():
    result = run(rows=[])
    assert first(result)["state"] == "NOT_FOUND_IN_COMPLETE_SNAPSHOT"
    assert first(result)["new_prospect_insert_authorized"] is False
    assert result["unique_canonical_leads_verified_added"] == 0


def test_census_projection_without_company_identity_fields_fails_closed():
    result = run(rows=[{"id": "c-101", "niche": "solar", "metro": "London", "status": "new"}])
    assert first(result)["state"] == "HOLD"
    assert "canonical_identity_fields_missing" in first(result)["reasons"]
    assert result["canonical_snapshot_complete_asserted"] is False


def test_partial_snapshot_must_not_claim_no_existing_identity():
    result = run(rows=[], complete=False)
    assert first(result)["state"] == "HOLD"
    assert "complete_authorised_canonical_snapshot_required" in first(result)["reasons"]


def test_missing_snapshot_ref_cannot_be_complete():
    result = run(snapshot="")
    assert first(result)["state"] == "HOLD"


def test_duplicate_canonical_ids_fail_closed():
    result = run(rows=[canonical(), canonical(name="Another Company")])
    assert first(result)["state"] == "HOLD"
    assert "duplicate_canonical_ids_in_snapshot" in first(result)["reasons"]


def test_multiple_exact_names_need_review_without_auto_merge():
    rows = [canonical(id="c-1"), canonical(id="c-2")]
    result = run(rows=rows)
    assert first(result)["state"] == "AMBIGUOUS"
    assert set(first(result)["possible_canonical_ids"]) == {"c-1", "c-2"}


def test_same_company_different_phone_is_conflict_not_match():
    result = run(rows=[canonical(phone="+44 20 7946 0100")])
    assert first(result)["state"] == "IDENTITY_CONFLICT"
    assert "observed_phone_disagrees_with_canonical" in first(result)["reasons"]


def test_same_name_other_corridor_must_be_reviewed():
    result = run(rows=[canonical(metro="Manchester")])
    assert first(result)["state"] == "CROSS_MARKET_MANUAL_REVIEW"
    assert first(result)["new_prospect_insert_authorized"] is False


def test_duplicate_source_observation_cannot_be_counted_twice():
    data = report()
    data["records"].append(deepcopy(data["records"][0]))
    data["records_observed"] = 2
    result = run(data)
    assert first(result)["state"] == "POTENTIAL_EXISTING_REVIEW"
    assert result["observation_decisions"][1]["state"] == "HOLD"
    assert "duplicate_observation_in_report" in result["observation_decisions"][1]["reasons"]


def test_source_report_tampering_fails_closed():
    data = report()
    data["records"][0]["commercial_resale_authorized"] = True
    result = run(data)
    assert first(result)["state"] == "HOLD"
    assert "record_resale_claim_forbidden" in first(result)["reasons"]


def test_scope_mismatch_other_niche_is_not_a_match():
    result = run(rows=[canonical(niche="insurance")])
    assert first(result)["state"] == "CROSS_MARKET_MANUAL_REVIEW"


def test_invalid_report_size_is_rejected():
    data = report()
    data["records"] = data["records"] * 26
    with pytest.raises(ValueError, match="bounded"):
        run(data)


def test_phone_shared_in_other_vertical_blocks_no_match():
    result = run(rows=[canonical(name="Different Company",
                                 niche="insurance")])
    assert first(result)["state"] == "CROSS_MARKET_MANUAL_REVIEW"
    assert "phone_seen_in_different_market_or_vertical" in first(result)["reasons"]


def test_cli_runs_with_only_reviewed_local_files(tmp_path, capsys):
    from datetime import datetime, timezone
    from scripts.review_scrapling_canonical_identity_20261019 import main
    import json

    data = report()
    data["observed_at"] = datetime.now(timezone.utc).isoformat()
    source = tmp_path / "source.json"
    database = tmp_path / "snapshot.json"
    source.write_text(json.dumps(data))
    database.write_text(json.dumps([canonical()]))
    flags = [
        "--read-only", "--source-report", str(source),
        "--canonical-identity-snapshot", str(database),
        "--snapshot-ref", "read-only:synthetic-snapshot",
        "--vertical", "solar", "--target-kind", "contractor",
        "--jurisdiction", "GB-ENG",
        "--identity-ref", "manual-review:synthetic-001",
    ]
    assert main(flags) == 2
    held = json.loads(capsys.readouterr().out)
    assert held["observation_decisions"][0]["state"] == "HOLD"
    assert main(flags + ["--complete-snapshot"]) == 0
    accepted = json.loads(capsys.readouterr().out)
    assert accepted["observation_decisions"][0]["state"] == "POTENTIAL_EXISTING_REVIEW"
    assert accepted["canonical_database_writes"] is False
    assert accepted["unique_canonical_leads_verified_added"] == 0


def test_cli_invalid_json_never_leaks_snapshot_details(tmp_path, capsys):
    from scripts.review_scrapling_canonical_identity_20261019 import main
    import json
    source = tmp_path / "source.json"
    source.write_text("confidential invalid snapshot content")
    snapshot = tmp_path / "snapshot.json"
    snapshot.write_text("[]")
    assert main([
        "--read-only", "--source-report", str(source),
        "--canonical-identity-snapshot", str(snapshot),
        "--snapshot-ref", "snapshot:testing",
        "--complete-snapshot",
        "--vertical", "solar", "--target-kind", "contractor",
        "--jurisdiction", "GB-ENG",
        "--identity-ref", "manual:synthetic-ref",
    ]) == 2
    output = capsys.readouterr().out
    assert "confidential" not in output
    assert json.loads(output)["canonical_database_writes"] is False
