"""Opt-in internal product bridge from the existing EmpireOS Revenue CRM.

Existing authenticated resolver -> existing PostgresRevenueCrmRepository
-> scoped, bounded CRM view -> non-PII diagnostic observation/report.

No public endpoint, separate database, new role, ingestion service, outgoing
communications, self-attested tenant authorization or commercial approval.
The repository's original DB session_user tenant binding must succeed.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from empire_os.predictive_revenue_enterprise_report import (
    build_enterprise_diagnostic_report,
)

MAX_CRM_OBSERVATIONS = 500
CRM_SOURCE = "existing_empiredb_revenue_crm_prospects_view"


class CrmDiagnosticEvidenceUnavailable(RuntimeError):
    """Safe exception; no original rows, credential details or customer ID."""


def _uuid(value: Any) -> str:
    try:
        if type(value) not in (str, UUID):
            raise ValueError("not uuid text")
        canonical = str(UUID(str(value)))
        if canonical != str(value).lower():
            raise ValueError("noncanonical uuid")
        return canonical
    except (ValueError, TypeError, AttributeError):
        raise CrmDiagnosticEvidenceUnavailable("CRM_ROW_IDENTITY_INVALID") from None


def _aware(value: Any) -> datetime:
    if (not isinstance(value, datetime) or value.tzinfo is None
        or value.utcoffset() is None):
        raise ValueError("timezone-aware CRM as_of required")
    return value.astimezone(timezone.utc)


def _when(value: Any) -> datetime:
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            raise CrmDiagnosticEvidenceUnavailable("CRM_EVENT_TIMESTAMP_INVALID") from None
    if (not isinstance(value, datetime) or value.tzinfo is None
        or value.utcoffset() is None):
        raise CrmDiagnosticEvidenceUnavailable("CRM_EVENT_TIMESTAMP_INVALID")
    return value.astimezone(timezone.utc)


def _positive_price(value: Any) -> bool:
    if value is None:
        return False
    if type(value) not in (int, Decimal):
        raise CrmDiagnosticEvidenceUnavailable("CRM_PRICE_FORMAT_UNSUPPORTED")
    if isinstance(value, Decimal) and not value.is_finite():
        raise CrmDiagnosticEvidenceUnavailable("CRM_PRICE_FORMAT_UNSUPPORTED")
    if int(value) != value or not 0 <= value <= 9_000_000_000_000_000:
        raise CrmDiagnosticEvidenceUnavailable("CRM_PRICE_FORMAT_UNSUPPORTED")
    return bool(value)


def _observations(
    rows: Sequence[Mapping[str, Any]], *,
    tenant_id: str, as_of: datetime, limit: int,
) -> dict[str, Any]:
    if type(rows) not in (tuple, list) or len(rows)>limit:
        raise CrmDiagnosticEvidenceUnavailable("CRM_SOURCE_ROW_LIMIT_OR_SHAPE_INVALID")
    seen=set()
    counts={
        "observed_records":len(rows),
        "conversation_reference_missing":0,
        "closer_reference_missing":0,
        "buyer_reference_missing":0,
        "fulfilment_order_reference_missing":0,
        "quoted_price_positive_records":0,
        "quoted_price_absent_or_zero_records":0,
        "deal_probability_missing_records":0,
    }
    for row in rows:
        if not isinstance(row, Mapping):
            raise CrmDiagnosticEvidenceUnavailable("CRM_SOURCE_ROW_SHAPE_INVALID")
        if str(row.get("tenant_id") or "")!=tenant_id:
            raise CrmDiagnosticEvidenceUnavailable("CRM_TENANT_SCOPE_MISMATCH")
        identifier=_uuid(row.get("prospect_id"))
        if identifier in seen:
            raise CrmDiagnosticEvidenceUnavailable("CRM_DUPLICATE_PROSPECT")
        seen.add(identifier)
        for field in ("conversation_id","closer_case_id",
                      "buyer_id","fulfilment_order_id"):
            value=row.get(field)
            if value in (None,""):
                key={
                    "conversation_id":"conversation_reference_missing",
                    "closer_case_id":"closer_reference_missing",
                    "buyer_id":"buyer_reference_missing",
                    "fulfilment_order_id":"fulfilment_order_reference_missing",
                }[field]
                counts[key]+=1
            else:
                _uuid(str(value))
        for field in ("conversation_updated_at","closer_updated_at",
                      "fulfilment_updated_at"):
            item=row.get(field)
            if item is not None and _when(item)>as_of:
                raise CrmDiagnosticEvidenceUnavailable("CRM_FUTURE_SOURCE_RECORD")
        if _positive_price(row.get("price_cents")):
            counts["quoted_price_positive_records"]+=1
        else:
            counts["quoted_price_absent_or_zero_records"]+=1
        if row.get("deal_probability") is None:
            counts["deal_probability_missing_records"]+=1
    truncated = len(rows)>=limit
    empty = len(rows)==0
    return {
        "schema_version":"empire.predictive_revenue.crm_case_observation.v1",
        "status":("CRM_SOURCE_SNAPSHOT_BOUND_REACHED_HOLD" if truncated else
                  "CRM_SOURCE_EMPTY_UNKNOWN_COVERAGE_HOLD" if empty else
                  "CRM_SOURCE_SNAPSHOT_OBSERVED"),
        "existing_source":CRM_SOURCE,
        "tenant_bound_existing_repository_read":True,
        "source_row_limit_reached":truncated,
        "bounded_observations":counts,
        "investigation_priorities":[
            {
                "code":"REVIEW_CONVERSATION_IDENTITY_COVERAGE",
                "observed_missing_count":counts["conversation_reference_missing"],
                "action":"Reconcile original CRM conversations and stage definitions",
            },
            {
                "code":"REVIEW_BUYER_ASSIGNMENT_COVERAGE",
                "observed_missing_count":counts["buyer_reference_missing"],
                "action":"Review expected buyer assignment by product and stage",
            },
            {
                "code":"REVIEW_OFFER_PRICE_COVERAGE",
                "observed_missing_count":counts["quoted_price_absent_or_zero_records"],
                "action":"Check original buyer-approved offers and contract pricing",
            },
            {
                "code":"REVIEW_FORECAST_INPUT_COVERAGE",
                "observed_missing_count":counts["deal_probability_missing_records"],
                "action":"Validate forecast inputs against historic closed outcomes",
            },
        ],
        "source_view_has_independent_financial_finality":False,
        "snapshot_is_full_tenant_census":False,
        "observed_quote_value_is_recognized_revenue":False,
        "pipeline_conversion_rates_calculated":False,
        "source_row_details_exported":False,
        "original_tenant_identifier_exported":False,
        "authorized_client_report_release":False,
        "customer_delivery_enabled":False,
        "mode":"OBSERVE",
        "execution_authority":"none",
    }


def observe_existing_authenticated_crm(
    *, request:Any,
    resolve_authenticated_crm:Callable[[Any],Any],
    as_of:datetime,
    limit:int=MAX_CRM_OBSERVATIONS,
)->dict[str,Any]:
    """Consume ONLY a trusted server-configured resolver from existing CRM.

    Caller must not create this resolver from tenant query parameters, headers,
    or client-submitted credentials. This module never grants authorisation.
    The existing PostgresRevenueCrmRepository rechecks the tenant bound to
    PostgreSQL session_user with empire_current_tenant_id().
    """
    when=_aware(as_of)
    if type(limit) is not int or not 1<=limit<=MAX_CRM_OBSERVATIONS:
        raise ValueError("bounded CRM review limit required")
    if not callable(resolve_authenticated_crm):
        raise ValueError("existing trusted CRM resolver required")
    from empire_os.revenue_crm_api import AuthenticatedRevenueCrmRead
    from empire_os.revenue_crm_transport import PostgresRevenueCrmRepository
    try:
        access=resolve_authenticated_crm(request)
    except Exception:
        raise CrmDiagnosticEvidenceUnavailable("CRM_AUTHENTICATED_ACCESS_UNAVAILABLE") from None
    if (type(access) is not AuthenticatedRevenueCrmRead
        or type(access.repository) is not PostgresRevenueCrmRepository):
        raise CrmDiagnosticEvidenceUnavailable("CRM_TRUSTED_REPOSITORY_REQUIRED")
    tenant=_uuid(access.tenant_id)
    if access.repository.tenant_id!=tenant:
        raise CrmDiagnosticEvidenceUnavailable("CRM_TENANT_REPOSITORY_MISMATCH")
    try:
        records=access.repository.prospects(limit=limit)
    except Exception:
        raise CrmDiagnosticEvidenceUnavailable("CRM_READ_ONLY_SOURCE_UNAVAILABLE") from None
    return _observations(records,tenant_id=tenant,as_of=when,limit=limit)


def build_authenticated_crm_diagnostic_report(
    repo_root:Any, *, request:Any,
    resolve_authenticated_crm:Callable[[Any],Any],
    as_of:datetime, case_ref:str="CASE_CRM_OBSERVATION",
    limit:int=MAX_CRM_OBSERVATIONS,
)->dict[str,Any]:
    """Report integration, opt-in, no new HTTP API route or client data write."""
    observed=observe_existing_authenticated_crm(
        request=request,resolve_authenticated_crm=resolve_authenticated_crm,
        as_of=as_of,
        limit=limit,
    )
    report=build_enterprise_diagnostic_report(
        repo_root,case={"case_ref":case_ref,"findings":[]},as_of=as_of,
    )
    report["existing_crm_observation_review"]=observed
    # A scoped view may expose some records, but cannot establish source
    # completeness, commercial causal impact or accepted customer results.
    assert report["release_gate"]["customer_delivery_enabled"] is False
    return report
