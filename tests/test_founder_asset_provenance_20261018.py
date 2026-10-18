"""Founder-origin proof is a file-integrity receipt, not a forged credential."""
from copy import deepcopy
from pathlib import Path
import json
import pytest

from empire_os.founder_asset_provenance import (
    build_founder_asset_receipt, verify_founder_asset_receipt,
)


def original(tmp_path, *, suffix=".png"):
    p = tmp_path / ("founder_input" + suffix)
    p.write_bytes(b"ORIGINAL_EMPIRE_AI_USER_DIRECTED_ASSET\x00\x01")
    return p


def create(path, **updates):
    args = {
        "asset_id": "empire-founder-globe-v1",
        "origin_class": "FOUNDER_ORIGINAL",
        "ai_assistance": "NONE_DECLARED",
        "founder_ownership_declared": True,
        "third_party_components_declared": False,
    }
    args.update(updates)
    return build_founder_asset_receipt(path, **args)


def test_original_founder_declaration_documents_bytes_not_absolute_authorship(tmp_path):
    path=original(tmp_path)
    before=path.read_bytes()
    receipt=create(path)
    assert receipt["origin_class"]=="FOUNDER_ORIGINAL"
    assert receipt["founder_ownership_declared"] is True
    assert receipt["founder_ownership_independently_verified"] is False
    assert receipt["third_party_component_rights_verified"] is False
    assert receipt["c2pa_content_credentials_validated"] is False
    assert receipt["public_release_authorized"] is False
    assert receipt["watermark_removed_or_obscured"].startswith("NOT_ATTESTED")
    assert receipt["provenance_integrity_current_asset"]=="LOCAL_SHA256_CAPTURED"
    assert receipt["production_asset_modified"] is False
    assert receipt["paid_service_used"] is False
    assert receipt["file_bytes"]==len(before)
    assert len(receipt["file_sha256"])==64
    assert path.read_bytes()==before
    check=verify_founder_asset_receipt(path, receipt)
    assert check["hash_and_length_match"] is True
    assert check["receipt_origin_independently_verified"] is False
    assert check["source_bytes_modified_by_verifier"] is False


def test_mutation_detected_without_editing_or_erasing_watermarks(tmp_path):
    path=original(tmp_path)
    receipt=create(path)
    path.write_bytes(path.read_bytes()+b"EDITED")
    output=verify_founder_asset_receipt(path,receipt)
    assert output["hash_and_length_match"] is False
    assert output["watermark_changed"]=="NOT_ANALYZED"


def test_ai_assisted_asset_declared_with_parent_file_lineage(tmp_path):
    parent=original(tmp_path)
    first=create(parent)
    next_asset=tmp_path/"generated_revision.webp"
    next_asset.write_bytes(b"AUTHENTIC_AI_ASSISTED_REVISION_CONTENT\x00")
    receipt=build_founder_asset_receipt(
        next_asset,
        asset_id="empire-globe-ai-assist-v2",
        origin_class="FOUNDER_DIRECTED_AI_ASSISTED",
        ai_assistance="AI_ASSISTED_DECLARED",
        founder_ownership_declared=True,
        third_party_components_declared=False,
        parent_file_sha256=first["file_sha256"],
        transformation_label="Founder directed AI visual enhancement",
        synthetic_person=False,
        synthetic_event_or_place=False,
    )
    assert receipt["input_parent_sha256"]==first["file_sha256"]
    assert receipt["ai_assistance"]=="AI_ASSISTED_DECLARED"
    assert receipt["transformation"]=="Founder directed AI visual enhancement"
    assert receipt["lineage_mode"].endswith("NOT_SIGNED")
    assert receipt["synthetic_media_disclosure"]["platform_disclosure_review_required"] is False
    assert not receipt["public_release_authorized"]


@pytest.mark.parametrize("updates", [
    {"founder_ownership_declared":False},
    {"origin_class":"THIRD_PARTY_LICENSED"},
    {"origin_class":"FOUNDER_DIRECTED_AI_ASSISTED","ai_assistance":"NONE_DECLARED"},
    {"asset_id":"bad/../../etc/passwd"},
    {"parent_file_sha256":"123"},
    {"parent_file_sha256":"a"*64},
    {"third_party_components_declared":"no"},
    {"origin_class":"FOUNDER_ORIGINAL","ai_assistance":"secret"},
    {"transformation_label":"remove\nwatermark"},  # unsafe free text
])
def test_forged_or_ambiguous_origin_fails_closed(tmp_path, updates):
    path=original(tmp_path)
    with pytest.raises(ValueError):
        create(path,**updates)


def test_third_party_origin_never_implied_owner(tmp_path):
    path=original(tmp_path)
    receipt=build_founder_asset_receipt(
        path,asset_id="third-party-asset",
        origin_class="THIRD_PARTY_LICENSED",
        ai_assistance="UNKNOWN",
        founder_ownership_declared=False,
        third_party_components_declared=True,
    )
    assert receipt["commercial_use_preflight"]=="HOLD_SOURCE_OR_EMBEDDED_COMPONENT_RIGHTS"
    assert receipt["third_party_resale_authorized"] is False


def test_unknown_embedded_fonts_or_media_prevents_automatic_rights_clearance(tmp_path):
    path=original(tmp_path)
    receipt=create(path,third_party_components_declared=None)
    assert receipt["commercial_use_preflight"]=="HOLD_SOURCE_OR_EMBEDDED_COMPONENT_RIGHTS"


def test_symlink_and_wrong_file_type_are_not_read(tmp_path):
    orig=original(tmp_path)
    link=tmp_path/"link.png"
    link.symlink_to(orig)
    with pytest.raises(ValueError,match="symlink"):
        create(link)
    other=tmp_path/"source.zip"
    other.write_bytes(b"DO_NOT_READ_ARCHIVE")
    with pytest.raises(ValueError,match="unsupported"):
        create(other)


def test_malformed_receipt_cannot_be_verified(tmp_path):
    path=original(tmp_path)
    receipt=create(path)
    for key,value in (("file_sha256","bad"),("file_bytes","unknown"),
                      ("schema_version","different"),("asset_id","../../bad")):
        modified=deepcopy(receipt)
        modified[key]=value
        with pytest.raises(ValueError):
            verify_founder_asset_receipt(path,modified)


def test_synthetic_people_need_platform_disclosure_review(tmp_path):
    path=original(tmp_path)
    receipt=create(path,synthetic_person=True)
    assert receipt["synthetic_media_disclosure"]["platform_disclosure_review_required"] is True
    assert receipt["synthetic_media_disclosure"]["present_as_unaltered_real_event_authorized"] is False
