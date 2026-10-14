"""V18 REAL dataset/Economic Memory sink guards for partner provenance."""
from copy import deepcopy
import pytest

from empire_os.company_partner_sink_enforcement_v18 import (
    PartnerSinkRightsError,assert_partner_rights_at_sink,
)
from empire_os.typed_decision_dataset import freeze_dataset
from empire_os.economic_memory import build_economic_memory_snapshot
from test_economic_memory import _verified_packet,_work


def case(source_ref="own:collected:1",inputs=None):
    return {
        "case_id":"case_1",
        "task_key":"source_quality",
        "inputs":inputs or {"source_ref":"own:1","evidence_summary":"normal"},
        "ground_truth":"review",
        "label_source":"founder-labelled",
        "source_ref":source_ref,
        "synthetic_test_fixture":True,
    }


def memory(*,source_ref=None,feed=None):
    packet=_verified_packet()
    if source_ref is not None:
        packet["label"]["evidence_refs"].append(source_ref)
    work=_work()
    if feed is not None:
        work.update(feed)
    return build_economic_memory_snapshot(
        executive_evaluation={},department_work=[work],
        cortex_learning={"packets":[packet]},
    )


@pytest.mark.parametrize("ref",[
    "https://astoriacompany.com/buyer-terms",
    "https://www.astoriacompany.com/buyer-terms",
    "https://publisher.astoriacompany.com/traffic",
    "http://buythecalls.com/pay-per-call/",
    "partner:rvnu.com",
    "RvNu.Com",
])
def test_real_typed_dataset_freeze_rejects_known_partner_origin(ref):
    with pytest.raises(PartnerSinkRightsError,
                       match="KNOWN_PARTNER_DATA_USE_RIGHTS_NOT_GRANTED"):
        freeze_dataset([case(source_ref=ref)],dataset_id="safe",version="v1")


@pytest.mark.parametrize("ref",[
    "https://astoriacompany.com/buyer-terms",
    "https://buythecalls.com/pay-per-call/",
    "https://rvnu.com/",
])
def test_economic_memory_existing_outcome_creation_denies_partner_evidence(ref):
    with pytest.raises(PartnerSinkRightsError,
                       match="KNOWN_PARTNER_DATA_USE_RIGHTS_NOT_GRANTED"):
        memory(source_ref=ref)


def test_partner_domain_can_be_nested_in_economic_memory_work_refs():
    with pytest.raises(PartnerSinkRightsError):
        memory(feed={"result_evidence_refs":["https://astoriacompany.com/buyer-terms"]})


def test_partner_domain_in_verified_training_input_not_only_case_source_ref():
    with pytest.raises(PartnerSinkRightsError):
        freeze_dataset([
            case(inputs={
                "source_ref":"own:1",
                "evidence_summary":"some label",
                "source_url":"https://buythecalls.com/pay-per-call/",
            })
        ],dataset_id="safe",version="v1")


def test_self_declared_data_rights_cannot_override_restriction():
    payload={
        "source_ref":"https://astoriacompany.com/buyer-terms",
        "model_training_data_rights_verified":True,
        "signed_contract_ref":"claimed:yes",
    }
    with pytest.raises(PartnerSinkRightsError):
        assert_partner_rights_at_sink(
            payload,purpose="MODEL_TRAINING_OR_BENCHMARK")


def test_nested_shared_cortex_packet_is_not_rejected_without_partner():
    packet=_verified_packet()
    # Original outcome and feedback often legitimately refer to same packet.
    result=assert_partner_rights_at_sink({
        "original":packet,
        "feedback":{"cortex_packet":packet},
    },purpose="ECONOMIC_MEMORY_PARTNER_DATA")
    assert result is None


def test_nested_shared_ref_under_identity_key_is_scanned_regardless_of_order():
    refs=["https://rvnu.com/"]
    payload={
        "source_refs":refs,
        "non_identity_copy":refs,
    }
    with pytest.raises(PartnerSinkRightsError):
        assert_partner_rights_at_sink(
            payload,purpose="MODEL_TRAINING_OR_BENCHMARK")


def test_data_use_purpose_is_explicit_and_unrecognised_purpose_denied():
    with pytest.raises(PartnerSinkRightsError,
                       match="SUPPORTED_PURPOSE_REQUIRED"):
        assert_partner_rights_at_sink({},purpose="ANY_PURPOSE")


def test_bounded_source_reference_prevents_truncation_bypass():
    with pytest.raises(PartnerSinkRightsError,
                       match="BOUNDED_SOURCE_REFERENCE_REQUIRED"):
        assert_partner_rights_at_sink({
            "source_url":"x"*1300+"https://astoriacompany.com/",
        },purpose="MODEL_TRAINING_OR_BENCHMARK")


def test_lookalike_domain_does_not_block_unrelated_own_research():
    result=assert_partner_rights_at_sink({
        "source_ref":"https://notastoriacompany.com/article",
        "evidence_refs":["canonical:commercial_events:real-1"],
    },purpose="ECONOMIC_MEMORY_PARTNER_DATA")
    assert result is None


def test_existing_non_partner_typed_dataset_and_economic_memory_remain_intact():
    manifest=freeze_dataset([case()],dataset_id="own",version="v1")
    assert manifest["case_count"]==1
    assert manifest["commercial_evidence"] is False
    snapshot=memory()
    assert snapshot["outcome_conditioned_memory_count"]==1
    assert snapshot["model_weight_mutation_authorized"] is False


def test_known_partner_rights_error_contains_no_raw_evidence():
    url="https://astoriacompany.com/buyer-terms"
    with pytest.raises(PartnerSinkRightsError) as err:
        memory(source_ref=url)
    assert url not in str(err.value)


def test_true_no_provenance_is_not_misrepresented_as_authenticated_rights():
    assert_partner_rights_at_sink({
        "source_ref":"canonical:commercial_outcomes:1"
    },purpose="ECONOMIC_MEMORY_PARTNER_DATA")
    # Known-domain guard cannot establish that this unscoped source is owned
    # or legally usable; independent source-custodian checks remain required.

def test_nested_source_ref_mapping_preserves_origin_context():
    payload={"source_refs":{"primary":{
        "source":"https://buythecalls.com/pay-per-call/",
    }}}
    with pytest.raises(PartnerSinkRightsError,
                       match="KNOWN_PARTNER_DATA_USE_RIGHTS_NOT_GRANTED"):
        assert_partner_rights_at_sink(
            payload,purpose="ECONOMIC_MEMORY_PARTNER_DATA")


def test_untyped_nested_ref_is_rejected_not_ignored():
    with pytest.raises(PartnerSinkRightsError,
                       match="SOURCE_REFERENCE_MUST_BE_TYPED"):
        assert_partner_rights_at_sink(
            {"result_evidence_refs":[19]},purpose="ECONOMIC_MEMORY_PARTNER_DATA")
