"""Optional, safe scientific + experience adapters for the existing flagship.

Evidently: optional offline aggregate evaluation; not a prediction verdict.
Langfuse: existing OTel event contract; no remote export by default.
PostHog: typed privacy-only client event contract.
OpenReplay: consent and tenant gate, no recording until owner enables.

We do NOT embed/fork/vendor external monorepos. Vendor installations, data
export, session recording, billing and web app changes remain separate gates.
"""
from __future__ import annotations

from datetime import datetime, timezone
from importlib.util import find_spec
from typing import Any, Mapping, Callable

from empire_os.telemetry import emit_event, new_trace_context, TelemetrySink

SCHEMA = "empire.flagship_scientific_experience_integrations.v1"
VENDORS = {
    "evidently": {
        "upstream": "https://github.com/evidentlyai/evidently",
        "license": "Apache-2.0",
        "purpose": "offline_source_quality_drift_and_scientific_evaluation",
    },
    "langfuse": {
        "upstream": "https://github.com/langfuse/langfuse",
        "license": "MIT_CORE_ENTERPRISE_SEPARATELY_LICENSED",
        "purpose": "existing_opentelemetry_agent_traces_evaluations_latency",
    },
    "posthog": {
        "upstream": "https://github.com/PostHog/posthog-foss",
        "license": "MIT_FOSS_MIRROR",
        "purpose": "manual_product_funnels_and_customer_task_success",
    },
    "openreplay": {
        "upstream": "https://github.com/openreplay/openreplay",
        "license": "AGPLv3_MOST_MIT_SOME_ENTERPRISE_SEPARATE",
        "purpose": "consent_limited_diagnostic_session_replay",
    },
}
EVENT_KINDS = frozenset({
    "source_quality_review",
    "scientific_evaluation_hold",
    "evidence_pathway_review",
    "customer_results_explanation",
})
STATUS = frozenset({"OBSERVED", "HELD", "MISSING", "STALE", "UNKNOWN"})
CATEGORIES = ("OBSERVED", "HELD", "MISSING", "STALE", "UNKNOWN")
MAX_SAMPLES_PER_CLASS = 200


def _utc(at: datetime) -> datetime:
    if not isinstance(at, datetime) or at.utcoffset() is None:
        raise ValueError("aware evaluation time required")
    return at.astimezone(timezone.utc)


def _safe_categories(data: Mapping[str, int]) -> dict[str, int]:
    if not isinstance(data, Mapping) or set(data) != set(CATEGORIES):
        raise ValueError("only aggregate fixed-category source quality counts")
    if any(type(value) is not int or value < 0 or value > MAX_SAMPLES_PER_CLASS
           for value in data.values()):
        raise ValueError("invalid bounded aggregate counts")
    return {category: data[category] for category in CATEGORIES}


def quality_distribution_preflight(
    reference: Mapping[str, int], current: Mapping[str, int],
    *, as_of: datetime,
) -> dict[str, Any]:
    """Non-statistical source-status observation, not sample-level drift proof."""
    ref = _safe_categories(reference)
    cur = _safe_categories(current)
    now = _utc(as_of)
    total_ref = sum(ref.values())
    total_cur = sum(cur.values())
    if not total_ref or not total_cur:
        return {
            "schema_version": "empire.flagship_quality.preflight.v1",
            "status": "INSUFFICIENT_REFERENCE_OR_CURRENT_AGGREGATE",
            "evaluated_at": now.isoformat(),
            "reference_n": total_ref, "current_n": total_cur,
            "category_counts_current": cur,
            "absolute_proportion_changes": None,
            "evidently_drift_test_executed": False,
            "statistical_significance_established": False,
            "source_quality_evidence_verified": False,
            "execution_authority": "none",
        }
    changes = {
        category: round(abs(cur[category] / total_cur -
                            ref[category] / total_ref), 6)
        for category in CATEGORIES
    }
    return {
        "schema_version": "empire.flagship_quality.preflight.v1",
        "status": "BOUNDED_QUALITY_DISTRIBUTION_REVIEW",
        "evaluated_at": now.isoformat(),
        "reference_n": total_ref, "current_n": total_cur,
        "category_counts_current": cur,
        "absolute_proportion_changes": changes,
        "evidently_drift_test_executed": False,
        "statistical_significance_established": False,
        "source_quality_evidence_verified": False,
        "commercial_conversion_calibrated": False,
        "execution_authority": "none",
    }


def run_offline_evidently_report(
    reference: Mapping[str, int], current: Mapping[str, int],
    *, as_of: datetime, report_factory: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    """Explicit offline Evidently (>=0.7) report on synthetic category rows.

    Aggregate data only; no PII or original buyer records. A diagnostic with
    underpowered cohorts is NOT a statistically established drift test.
    report_factory allows dependency-free contract/injection testing.
    """
    preflight = quality_distribution_preflight(
        reference, current, as_of=as_of,
    )
    if preflight["status"] != "BOUNDED_QUALITY_DISTRIBUTION_REVIEW":
        return dict(preflight, evidently_run_status="HELD_INSUFFICIENT_COHORT")
    if report_factory is None:
        try:
            import pandas as pd
            from evidently import Report, Dataset, DataDefinition
            from evidently.presets import DataDriftPreset
        except ImportError:
            return dict(preflight, evidently_run_status="OPTIONAL_EVIDENTLY_DEPENDENCY_NOT_INSTALLED")
        def make_report():
            ref_frame = pd.DataFrame({
                "source_status": [
                    c for c in CATEGORIES for _ in range(reference[c])
                ]
            })
            cur_frame = pd.DataFrame({
                "source_status": [
                    c for c in CATEGORIES for _ in range(current[c])
                ]
            })
            definition = DataDefinition(categorical_columns=["source_status"])
            ref_dataset = Dataset.from_pandas(ref_frame, data_definition=definition)
            cur_dataset = Dataset.from_pandas(cur_frame, data_definition=definition)
            return Report([DataDriftPreset()]).run(cur_dataset, ref_dataset)
        report_factory = make_report
    try:
        snapshot = report_factory()
        if snapshot is None:
            raise ValueError("evaluation snapshot unavailable")
    except Exception:
        # Provider error details could expose original source payloads.
        return dict(preflight, evidently_run_status="OFFLINE_EVALUATION_HELD")
    return dict(
        preflight,
        evidently_run_status="OFFLINE_EVALUATION_EXECUTED",
        evidently_drift_test_executed=True,
        evidently_metrics_published=False,
        statistical_significance_established=False,
        # The report might estimate drift, but aggregation violates the
        # original observations' sampling independence assumption.
        source_quality_evidence_verified=False,
        report_stored_or_uploaded=False,
    )


def emit_flagship_quality_trace(
    sink: TelemetrySink, *, kind: str, status: str,
    duration_ms: int, as_of: datetime,
) -> dict[str, Any]:
    """Minimal existing OpenTelemetry/Langfuse-compatible local span.

    The function cannot take arbitrary text, identifiers, prompts or URLs.
    The supplied sink can be the existing local-only telemetry sink. An
    actual remote OTel exporter remains a separate opt-in configuration.
    """
    _utc(as_of)
    if kind not in EVENT_KINDS or status not in STATUS:
        raise ValueError("unrecognized flagship telemetry event")
    if type(duration_ms) is not int or not 0 <= duration_ms <= 600_000:
        raise ValueError("invalid event duration")
    event = emit_event(
        sink, name="empire.flagship." + kind,
        trace=new_trace_context(),
        attributes={
            "empire.flagship.evaluation_status": status,
            "empire.flagship.duration_ms": duration_ms,
            "empire.flagship.customer_contact_included": False,
            "empire.flagship.claims_verified": False,
            "empire.execution_authority": "none",
        },
        observed_at=as_of.astimezone(timezone.utc).isoformat(),
    )
    return {
        "schema_version": "empire.flagship_observability.event.v1",
        "event_kind": kind, "status": status,
        "telemetry_event": event.name,
        "external_export_verified": False,
        "execution_authority": "none",
    }


def flagship_vendor_readiness(*, as_of: datetime) -> dict[str, Any]:
    now = _utc(as_of)
    has_evidently = find_spec("evidently") is not None
    return {
        "schema_version": SCHEMA,
        "generated_at": now.isoformat(),
        "status": "FEATURE_ADAPTERS_STAGED_NO_REMOTE_ACTIVATION",
        "integrations": {
            "evidently": {
                **VENDORS["evidently"],
                "optional_dependency_importable": has_evidently,
                "status": ("OFFLINE_ADAPTER_AVAILABLE_NOT_RUN"
                           if has_evidently else "OPTIONAL_DEPENDENCY_NOT_INSTALLED"),
                "provider_fork_created": False,
                "remote_upload_enabled": False,
            },
            "langfuse": {
                **VENDORS["langfuse"],
                "status": "EXISTING_OTEL_EXPORTER_REUSED_NOT_ACTIVATED",
                "provider_fork_created": False,
                "remote_export_enabled_by_this_feature": False,
            },
            "posthog": {
                **VENDORS["posthog"],
                "status": "CONSENT_GATED_FRONTEND_ADAPTER_STAGED",
                "provider_fork_created": False,
                "sdk_installed_by_this_feature": False,
                "autocapture_enabled": False,
                "replay_enabled": False,
                "network_enabled": False,
            },
            "openreplay": {
                **VENDORS["openreplay"],
                "status": "REPLAY_POLICY_ADAPTER_STAGED_LICENSE_PRIVACY_REVIEW_PENDING",
                "provider_fork_created": False,
                "sdk_installed_by_this_feature": False,
                "session_recording_enabled": False,
                "network_enabled": False,
            },
        },
        "external_customer_data_transmitted": False,
        "source_custody_verified_by_vendor": False,
        "actual_model_calibration_performed": False,
        "external_execution_authorized": False,
        "execution_authority": "none",
    }
