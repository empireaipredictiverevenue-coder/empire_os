"""Data fabric code-edge inventory is descriptive, never an activation."""
from pathlib import Path

from empire_os.revenue_data_fabric_edges import EDGES, inspect_code_edges


def test_manifest_never_implies_runtime_authority(tmp_path):
    result = inspect_code_edges(tmp_path)
    assert len(result["edges"]) == len(EDGES)
    assert result["runtime_linkages_verified"] == 0
    assert result["database_writes"] is False
    assert result["outbound"] is False
    assert result["network_access"] is False
    assert all(not item["runtime_linkage_verified"] for item in result["edges"])
    assert all(item["status"] == "SOURCE_OR_SINK_MISSING" for item in result["edges"])


def test_source_file_presence_does_not_prove_connection(tmp_path):
    first = EDGES[0]
    dest = tmp_path / first.source_file
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("module exists")
    other = tmp_path / first.sink_file
    other.parent.mkdir(parents=True, exist_ok=True)
    other.write_text("module exists")
    item = inspect_code_edges(tmp_path)["edges"][0]
    assert item["code_complete"] is True
    assert item["runtime_linkage_verified"] is False
    assert item["status"] == "CODE_PRESENT_RUNTIME_UNVERIFIED"


def test_current_repo_manifest_has_code():
    root = Path(__file__).resolve().parents[1]
    report = inspect_code_edges(root)
    assert report["canonical_database"] == "EmpireDB PostgreSQL"
    assert report["edges"][0]["code_complete"] is True


def test_existing_waterfall_and_regulated_verticals_are_explicit():
    names = {edge.layer for edge in EDGES}
    assert {
        "empire_owned_contact_waterfall",
        "legal_mass_tort_firm_intelligence",
        "claims_insurance_buyer_governance",
        "insurance_distribution_b2b_demand",
    } <= names
    result = inspect_code_edges(Path(__file__).resolve().parents[1])
    audited = {item["layer"]: item for item in result["edges"]}
    for layer in (
        "empire_owned_contact_waterfall",
        "legal_mass_tort_firm_intelligence",
        "claims_insurance_buyer_governance",
        "insurance_distribution_b2b_demand",
    ):
        assert audited[layer]["code_complete"]
        assert audited[layer]["runtime_linkage_verified"] is False
