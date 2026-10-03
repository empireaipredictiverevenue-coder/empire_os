import json

from empire_os.canonical_data_gateway import DataGatewayUnavailable
from empire_os.digital_avatar import (
    AvatarMeetingMode,
    AvatarMeetingSession,
    DigitalAvatarIdentity,
)
from empire_os.digital_avatar_authority import (
    AvatarCloseProposal,
    AvatarCommercialAuthorityPolicy,
)
from empire_os.digital_avatar_close_readiness_service import (
    process_close_readiness_once,
)
from empire_os.recall_shadow_session import (
    RecallShadowSessionManifest,
    save_recall_shadow_session,
)


TERMS_ID = "22222222-2222-4222-8222-222222222222"
TERMS_REF = f"commercial_terms_review:{TERMS_ID}"
PRICE_ID = "11111111-1111-4111-8111-111111111111"
PRICE_REF = f"commercial_evidence:{PRICE_ID}"
PRODUCT_CODE = "PREDICTIVE-REVENUE-PILOT"
PRODUCT_REF = f"commercial_product_code:{PRODUCT_CODE}"


def manifest(*, commercial=True):
    policy = None
    proposal = None
    terms_ref = None
    if commercial:
        terms_ref = TERMS_REF
        policy = AvatarCommercialAuthorityPolicy(
            allowed_product_codes=(PRODUCT_CODE,),
            approved_terms_refs=(TERMS_REF,),
            allowed_currencies=("USD",),
            max_discount_bps=1000,
            max_contract_months=3,
        )
        proposal = AvatarCloseProposal(
            product_code=PRODUCT_CODE,
            list_price_cents=500000,
            proposed_price_cents=475000,
            currency="USD",
            contract_months=1,
            terms_ref=TERMS_REF,
            evidence_refs=(PRODUCT_REF, PRICE_REF),
        )
    return RecallShadowSessionManifest(
        identity=DigitalAvatarIdentity(
            avatar_id="avatar-phil-v1",
            owner_name="Phil Livesley",
            display_name="Phil — Empire AI Digital Avatar",
            organisation_name="Empire AI",
            disclosure_text="I am Phil's authorised Empire AI Digital Avatar.",
            owner_consent_evidence_ref="consent:phil:avatar:v1",
        ),
        session=AvatarMeetingSession(
            meeting_id="meeting-001",
            avatar_id="avatar-phil-v1",
            provider="recall",
            mode=AvatarMeetingMode.SHADOW,
        ),
        account_name="Example Buyer",
        objective="qualify fit and agree next step",
        recording_consent_evidence_ref="consent:meeting:001",
        commercial_terms_ref=terms_ref,
        commercial_policy=policy,
        close_proposal=proposal,
    )


class Gateway:
    def query(self, table, columns, **kwargs):
        if table == "commercial_evidence_registry":
            return [{
                "id": PRICE_ID,
                "evidence_kind": "price",
                "niche": "predictive_revenue",
                "metro": "global",
                "amount_cents": 500000,
                "currency": "USD",
                "unit": "flat",
                "source_type": "founder_approved",
                "status": "verified",
                "valid_until": "2027-01-01T00:00:00+00:00",
                "verified_at": "2026-10-02T12:00:00+00:00",
            }]
        return []

    def rpc(self, name, params=None):
        if name == "get_commercial_terms_review":
            return {
                "review_id": TERMS_ID,
                "status": "approved",
                "commercial_terms_sha256": "a" * 64,
                "decided_at": "2026-10-02T12:00:00+00:00",
                "decided_by": "Phil Livesley",
                "price_cents": 475000,
                "terms": {
                    "currency": "USD",
                    "product_code": PRODUCT_CODE,
                    "price_cents": 475000,
                    "verified_price_evidence_ref": PRICE_REF,
                },
            }
        if name == "get_commercial_product_catalog":
            return [{
                "product_id": "66666666-6666-4666-8666-666666666666",
                "product_code": PRODUCT_CODE,
                "product_name": "Predictive Revenue Pilot",
                "product_family": "predictive_revenue",
                "active": True,
                "catalog_state": "VERIFIED",
                "currency": "USD",
                "version_id": "77777777-7777-4777-8777-777777777777",
                "version": 3,
                "version_state": "VERIFIED",
                "billing_model": "flat",
                "price_basis": {
                    "state": "VERIFIED",
                    "amount_cents": 500000,
                    "unit": "flat",
                    "currency": "USD",
                },
                "acquisition_cost_basis": {
                    "state": "VERIFIED",
                    "amount_cents": 100000,
                    "unit": "flat",
                    "currency": "USD",
                },
                "fulfilment_cost_basis": {
                    "state": "VERIFIED",
                    "amount_cents": 75000,
                    "unit": "flat",
                    "currency": "USD",
                },
                "margin_policy": {
                    "state": "VERIFIED",
                    "minimum_margin_bps": 3000,
                },
                "binding_terms_ready": True,
            }]
        return None


def paths(tmp_path):
    return {
        "session_root": tmp_path / "sessions",
        "output_root": tmp_path / "close",
        "guidance_root": tmp_path / "guidance",
        "runtime_state_root": tmp_path / "runtime",
        "meeting_state_root": tmp_path / "meeting_state",
    }


def test_canonical_close_enrichment_materializes_private_ready_state(tmp_path):
    p = paths(tmp_path)
    save_recall_shadow_session(
        root=p["session_root"],
        manifest=manifest(),
    )
    result = process_close_readiness_once(
        **p,
        gateway_factory=lambda _env: Gateway(),
        environ={"EMPIRE_DATA_BACKEND": "empiredb"},
    )
    assert result["scanned"] == 1
    assert result["configured"] == 1
    assert result["ready"] == 1
    assert result["failed"] == 0
    assert result["execution_authority"] == "none"

    close = json.loads(
        (p["output_root"] / "meeting-001.json").read_text()
    )
    assert close["canonical_grounded"] is True
    assert close["conversational_close_ready"] is True
    assert close["binding_execution_allowed"] is False
    assert close["commercial_execution"] is False
    assert close["payment_execution"] is False

    meeting = json.loads(
        (p["meeting_state_root"] / "meeting-001.json").read_text()
    )
    assert meeting["conversational_close_ready"] is True
    assert meeting["binding_execution_allowed"] is False
    assert meeting["close_readiness"]["private_to_owner"] is True
    assert meeting["execution_authority"] == "none"


def test_no_close_envelope_never_constructs_canonical_gateway(tmp_path):
    p = paths(tmp_path)
    save_recall_shadow_session(
        root=p["session_root"],
        manifest=manifest(commercial=False),
    )
    calls = []

    def gateway_factory(_env):
        calls.append(True)
        raise AssertionError("gateway must not be constructed")

    result = process_close_readiness_once(
        **p,
        gateway_factory=gateway_factory,
        environ={},
    )
    assert result["configured"] == 0
    assert result["ready"] == 0
    assert calls == []
    close = json.loads(
        (p["output_root"] / "meeting-001.json").read_text()
    )
    assert close["commercial_envelope_configured"] is False
    assert close["canonical_grounding_attempted"] is False


def test_missing_empiredb_fails_closed_to_human_takeover(tmp_path):
    p = paths(tmp_path)
    save_recall_shadow_session(
        root=p["session_root"],
        manifest=manifest(),
    )

    def gateway_factory(_env):
        raise DataGatewayUnavailable("not configured")

    result = process_close_readiness_once(
        **p,
        gateway_factory=gateway_factory,
        environ={},
    )
    assert result["configured"] == 1
    assert result["canonical_unavailable"] == 1
    assert result["takeover_required"] == 1
    assert result["failed"] == 0

    close = json.loads(
        (p["output_root"] / "meeting-001.json").read_text()
    )
    assert close["canonical_grounding_available"] is False
    assert close["conversational_close_ready"] is False
    assert close["binding_execution_allowed"] is False
    assert close["human_takeover_required"] is True
    assert close["blockers"] == [
        "canonical_commercial_evidence_unavailable"
    ]
