from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping
import re

from empire_os.quant_brain import brier_score


SCHEMA_VERSION = (
    "empire.lead_smart.ringba_call_evidence.v1"
)

CALIBRATION_SCHEMA_VERSION = (
    "empire.lead_smart."
    "ringba_payable_calibration.v1"
)

EXPECTED_CAMPAIGN_ID = (
    "CA8278ed3f26e9495b881fe3833174d007"
)

EXPECTED_TRACKING_NUMBER = "+18883579305"

ALLOWED_ROUTE_CLASSES = {
    "DURATION",
    "APPOINTMENT_CPL",
}

ALLOWED_VERIFICATION_METHODS = {
    "ringba_authenticated_api",
    "ringba_verified_webhook",
}


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _number(
    value: Any,
    name: str,
) -> float:
    if isinstance(value, bool):
        raise ValueError(
            f"{name} must be numeric"
        )

    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"{name} must be numeric"
        ) from exc

    return result


def _timestamp(
    value: Any,
    name: str,
) -> datetime:
    raw = _clean(value)

    if not raw:
        raise ValueError(
            f"{name} required"
        )

    try:
        result = datetime.fromisoformat(
            raw.replace("Z", "+00:00")
        )
    except ValueError as exc:
        raise ValueError(
            f"{name} must be ISO-8601"
        ) from exc

    if result.tzinfo is None:
        raise ValueError(
            f"{name} must be timezone-aware"
        )

    return result.astimezone(timezone.utc)


def _optional_bool(
    value: Any,
    name: str,
) -> bool | None:
    if value is None:
        return None

    if type(value) is not bool:
        raise ValueError(
            f"{name} must be boolean or null"
        )

    return value


def _zip(
    value: Any,
) -> str | None:
    raw = _clean(value)

    if not raw:
        return None

    if re.fullmatch(r"\d{5}", raw) is None:
        raise ValueError(
            "zip must be exactly five digits"
        )

    return raw


def evidence_contract() -> dict[str, Any]:
    """
    Contract for the trusted Ringba ingestion boundary.

    The normalizer does not authenticate Ringba itself.  It accepts
    evidence only after a trusted upstream boundary has independently
    verified the provider source using one of the explicit methods.
    """

    return {
        "schema_version":
            "empire.lead_smart."
            "ringba_evidence_contract.v1",

        "provider": "Ringba",

        "campaign_id":
            EXPECTED_CAMPAIGN_ID,

        "tracking_number":
            EXPECTED_TRACKING_NUMBER,

        "allowed_verification_methods":
            sorted(
                ALLOWED_VERIFICATION_METHODS
            ),

        "required_identity": [
            "tenant_id",
            "ringba_call_id",
            "campaign_id",
            "tracking_number",
            "started_at",
            "verification",
        ],

        "calibration_features": [
            "zip",
            "intent_class",
            "route_class",
            "connected_seconds",
            "appointment_event",
            "duplicate_within_30d",
            "payout_amount",
            "payout_currency",
            "payout_observed_at",
        ],

        "payout_value_authority":
            "RINGBA_REALISED_EVENT",

        "provider_payout_is_recognized_revenue":
            False,

        "provider_payout_is_cash_settlement":
            False,

        "economic_memory_requires_later_"
        "canonical_outcome":
            True,

        "prediction_promotion_allowed":
            False,

        "execution_authority":
            "NONE",
    }


def normalize_verified_ringba_event(
    raw: Mapping[str, Any],
) -> dict[str, Any]:
    """
    Normalize independently verified Ringba call evidence.

    Critical distinction:

      Ringba payout observation
          != cash settlement
          != canonical recognized revenue.

    Duration is NEVER used to infer a payout by itself because
    the Lead Smart program has route-dependent qualification.
    """

    data = dict(raw or {})

    tenant_id = _clean(
        data.get("tenant_id")
    )

    if not tenant_id:
        raise ValueError(
            "tenant_id required"
        )

    call_id = _clean(
        data.get("ringba_call_id")
    )

    if not call_id:
        raise ValueError(
            "ringba_call_id required"
        )

    campaign_id = _clean(
        data.get("campaign_id")
    )

    if campaign_id != EXPECTED_CAMPAIGN_ID:
        raise ValueError(
            "Ringba campaign mismatch"
        )

    tracking_number = _clean(
        data.get("tracking_number")
    )

    if (
        tracking_number
        != EXPECTED_TRACKING_NUMBER
    ):
        raise ValueError(
            "Ringba tracking number mismatch"
        )

    verification = dict(
        data.get("verification") or {}
    )

    if (
        verification.get("verified")
        is not True
    ):
        raise ValueError(
            "independently verified "
            "Ringba evidence required"
        )

    method = _clean(
        verification.get("method")
    )

    if (
        method
        not in ALLOWED_VERIFICATION_METHODS
    ):
        raise ValueError(
            "unsupported Ringba "
            "verification method"
        )

    evidence_ref = _clean(
        verification.get("evidence_ref")
    )

    if not evidence_ref:
        raise ValueError(
            "Ringba evidence_ref required"
        )

    started_at = _timestamp(
        data.get("started_at"),
        "started_at",
    )

    finalized = data.get(
        "provider_event_finalized"
    )

    if type(finalized) is not bool:
        raise ValueError(
            "provider_event_finalized "
            "must be boolean"
        )

    zip_code = _zip(
        data.get("zip")
    )

    intent_class = (
        _clean(
            data.get("intent_class")
        )
        or None
    )

    route_raw = _clean(
        data.get("route_class")
    ).upper()

    route_class = (
        route_raw
        if route_raw
        else None
    )

    if (
        route_class is not None
        and route_class
        not in ALLOWED_ROUTE_CLASSES
    ):
        raise ValueError(
            "unsupported route_class"
        )

    connected_raw = data.get(
        "connected_seconds"
    )

    connected_seconds = None

    if connected_raw is not None:
        if (
            isinstance(
                connected_raw,
                bool,
            )
            or not isinstance(
                connected_raw,
                int,
            )
            or connected_raw < 0
        ):
            raise ValueError(
                "connected_seconds must "
                "be nonnegative integer or null"
            )

        connected_seconds = (
            connected_raw
        )

    appointment_event = _optional_bool(
        data.get("appointment_event"),
        "appointment_event",
    )

    duplicate = _optional_bool(
        data.get(
            "duplicate_within_30d"
        ),
        "duplicate_within_30d",
    )

    payout_raw = data.get(
        "payout_amount"
    )

    payout_amount = None
    payout_currency = None
    payout_observed_at = None

    if payout_raw is not None:
        payout_amount = _number(
            payout_raw,
            "payout_amount",
        )

        if payout_amount < 0:
            raise ValueError(
                "payout_amount must "
                "be nonnegative"
            )

        payout_currency = _clean(
            data.get("payout_currency")
        ).upper()

        if payout_currency != "USD":
            raise ValueError(
                "Lead Smart Ringba payout "
                "currency must be USD"
            )

        payout_observed_at = _timestamp(
            data.get(
                "payout_observed_at"
            ),
            "payout_observed_at",
        )

        if (
            payout_observed_at
            < started_at
        ):
            raise ValueError(
                "payout cannot predate call"
            )

    elif data.get(
        "payout_currency"
    ) is not None:
        raise ValueError(
            "payout_currency without "
            "payout_amount"
        )

    payable_label = None

    if (
        finalized
        and payout_amount is not None
    ):
        payable_label = (
            1
            if payout_amount > 0
            else 0
        )

    provider_credit_observed = (
        payable_label == 1
    )

    provider_nonpayable_observed = (
        payable_label == 0
    )

    calibration_blockers = []

    if payable_label is None:
        calibration_blockers.append(
            "final_payable_label_unavailable"
        )

    if zip_code is None:
        calibration_blockers.append(
            "zip_unknown"
        )

    if intent_class is None:
        calibration_blockers.append(
            "intent_class_unknown"
        )

    if route_class is None:
        calibration_blockers.append(
            "route_class_unknown"
        )

    if connected_seconds is None:
        calibration_blockers.append(
            "connected_seconds_unknown"
        )

    if appointment_event is None:
        calibration_blockers.append(
            "appointment_event_unknown"
        )

    if duplicate is None:
        calibration_blockers.append(
            "duplicate_window_status_unknown"
        )

    calibration_ready = (
        not calibration_blockers
    )

    return {
        "schema_version":
            SCHEMA_VERSION,

        "provider":
            "Ringba",

        "buyer":
            "Lead Smart",

        "vertical":
            "Roofing",

        "tenant_id":
            tenant_id,

        "ringba_call_id":
            call_id,

        "campaign_id":
            campaign_id,

        "tracking_number":
            tracking_number,

        "zip":
            zip_code,

        "intent_class":
            intent_class,

        "route_class":
            route_class,

        "started_at":
            started_at.isoformat(),

        "connected_seconds":
            connected_seconds,

        "appointment_event":
            appointment_event,

        "duplicate_within_30d":
            duplicate,

        "provider_event_finalized":
            finalized,

        "verification": {
            "verified": True,
            "method": method,
            "evidence_ref":
                evidence_ref,
        },

        "payout": {
            "amount":
                payout_amount,

            "currency":
                payout_currency,

            "observed_at":
                (
                    payout_observed_at
                    .isoformat()
                    if payout_observed_at
                    else None
                ),

            "value_authority":
                "RINGBA_REALISED_EVENT",

            "final_payable_label":
                payable_label,
        },

        "provider_credit_observed":
            provider_credit_observed,

        "provider_nonpayable_observed":
            provider_nonpayable_observed,

        "duration_threshold_inferred":
            False,

        "route_inferred_from_duration":
            False,

        "calibration_ready":
            calibration_ready,

        "calibration_blockers":
            sorted(
                set(
                    calibration_blockers
                )
            ),

        # These remain FALSE until later
        # settlement/revenue truth exists.
        "cash_settlement_observed":
            False,

        "revenue_recognized":
            False,

        "actual_revenue":
            False,

        "economic_memory_eligible":
            False,

        "commercial_outcome_terminal":
            False,

        "learning_stage":
            "PROVIDER_EVIDENCE_ONLY",

        "model_weight_mutation":
            False,

        "execution_authority":
            "NONE",
    }


def build_payable_calibration_candidate(
    *,
    prediction: Mapping[str, Any],
    evidence: Mapping[str, Any],
    as_of: datetime | str,
) -> dict[str, Any]:
    """
    Score an explicit pre-call payability prediction against a
    finalized, independently verified Ringba payable label.

    Uses the existing Quant Brier implementation.

    This is SHADOW calibration only and must NOT enter Economic
    Memory as a verified commercial outcome.
    """

    if (
        evidence.get("schema_version")
        != SCHEMA_VERSION
    ):
        raise ValueError(
            "normalized Ringba evidence required"
        )

    if (
        evidence.get(
            "calibration_ready"
        )
        is not True
    ):
        raise ValueError(
            "Ringba evidence not "
            "calibration ready"
        )

    if (
        evidence.get(
            "revenue_recognized"
        )
        is not False
    ):
        raise ValueError(
            "provider payout evidence "
            "must not claim recognized revenue"
        )

    data = dict(prediction or {})

    if (
        data.get(
            "prediction_type"
        )
        != "ringba_payable_probability"
    ):
        raise ValueError(
            "unsupported prediction_type"
        )

    tenant_id = _clean(
        data.get("tenant_id")
    )

    if (
        not tenant_id
        or tenant_id
        != evidence.get("tenant_id")
    ):
        raise ValueError(
            "prediction/evidence tenant mismatch"
        )

    prediction_ref = _clean(
        data.get("prediction_ref")
    )

    if not prediction_ref:
        raise ValueError(
            "prediction_ref required"
        )

    opportunity_key = _clean(
        data.get("opportunity_key")
    )

    if not opportunity_key:
        raise ValueError(
            "opportunity_key required"
        )

    prediction_evidence_refs = [
        _clean(value)
        for value in (
            data.get("evidence_refs")
            or []
        )
        if _clean(value)
    ]

    if not prediction_evidence_refs:
        raise ValueError(
            "prediction evidence required"
        )

    probability = _number(
        data.get(
            "predicted_probability"
        ),
        "predicted_probability",
    )

    if not 0 <= probability <= 1:
        raise ValueError(
            "predicted_probability must "
            "be between 0 and 1"
        )

    predicted_at = _timestamp(
        data.get("predicted_at"),
        "predicted_at",
    )

    horizon_until = _timestamp(
        data.get("horizon_until"),
        "horizon_until",
    )

    started_at = _timestamp(
        evidence.get("started_at"),
        "evidence.started_at",
    )

    payout_observed_at = _timestamp(
        (
            evidence.get("payout")
            or {}
        ).get("observed_at"),
        "evidence.payout.observed_at",
    )

    now = (
        as_of
        if isinstance(
            as_of,
            datetime,
        )
        else _timestamp(
            as_of,
            "as_of",
        )
    )

    if now.tzinfo is None:
        raise ValueError(
            "as_of must be timezone-aware"
        )

    now = now.astimezone(
        timezone.utc
    )

    if not (
        predicted_at
        < started_at
        <= payout_observed_at
        <= horizon_until
    ):
        raise ValueError(
            "Ringba outcome outside "
            "prediction window"
        )

    if payout_observed_at > now:
        raise ValueError(
            "future Ringba payout evidence"
        )

    prediction_zip = _zip(
        data.get("zip")
    )

    if (
        prediction_zip
        != evidence.get("zip")
    ):
        raise ValueError(
            "prediction/evidence ZIP mismatch"
        )

    campaign_id = _clean(
        data.get("campaign_id")
    )

    if (
        campaign_id
        != evidence.get("campaign_id")
    ):
        raise ValueError(
            "prediction/evidence campaign mismatch"
        )

    label = (
        evidence["payout"][
            "final_payable_label"
        ]
    )

    if type(label) is not int:
        raise ValueError(
            "binary final payable label required"
        )

    metric = brier_score(
        [probability],
        [label],
    )

    provider_ref = (
        evidence["verification"][
            "evidence_ref"
        ]
    )

    return {
        "schema_version":
            CALIBRATION_SCHEMA_VERSION,

        "tenant_id":
            tenant_id,

        "opportunity_key":
            opportunity_key,

        "prediction_ref":
            prediction_ref,

        "prediction_type":
            "ringba_payable_probability",

        "ringba_call_id":
            evidence["ringba_call_id"],

        "campaign_id":
            campaign_id,

        "zip":
            evidence["zip"],

        "route_class":
            evidence["route_class"],

        "predicted_value":
            probability,

        "actual_value":
            label,

        "signed_error":
            round(
                label - probability,
                6,
            ),

        "brier_score":
            metric["brier_score"],

        "predicted_at":
            predicted_at.isoformat(),

        "actual_at":
            payout_observed_at.isoformat(),

        "horizon_until":
            horizon_until.isoformat(),

        "evidence_refs":
            list(
                dict.fromkeys([
                    *prediction_evidence_refs,
                    provider_ref,
                ])
            ),

        "provider_payout_amount":
            evidence["payout"]["amount"],

        "provider_payout_currency":
            evidence["payout"][
                "currency"
            ],

        "calibration_ready":
            True,

        "learning_stage":
            "SHADOW_LEARNING",

        "shadow_only":
            True,

        "commercial_outcome":
            False,

        "recognized_revenue":
            False,

        "actual_revenue":
            False,

        "economic_memory_eligible":
            False,

        "model_weight_mutation":
            False,

        "promoted_learning":
            False,

        "execution_authority":
            "NONE",
    }
