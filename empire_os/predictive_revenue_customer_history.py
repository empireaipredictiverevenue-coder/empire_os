"""Transient, tenant-authenticated customer history forecast preview.

Uploaded values are customer-provided claims, not independently verified
financial actuals. The source bytes are never persisted and the preview is
never registered in EmpireDB or eligible for calibration.
"""
from __future__ import annotations

import csv
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from io import StringIO
import re
from typing import Any
from uuid import UUID

from empire_os.predictive_materializer import materialize_daily_actuals

MAX_UPLOAD_BYTES = 32_768
HISTORY_DAYS = 30
MAX_MINOR_UNITS = 1_000_000_000_000_000
_CURRENCY = re.compile(r"^[A-Z]{3}$")
_HEADER = ("date", "revenue_minor_units", "currency_code")


class CustomerHistoryInputError(ValueError):
    """Safe, bounded failure code for customer supplied history."""


def preview_customer_history_csv(
    payload: bytes, *, tenant_id: str, as_of: datetime,
    horizon_days: int = 30,
) -> dict[str, Any]:
    """Validate exactly 30 contiguous completed UTC days and forecast in memory."""
    try:
        tenant = str(UUID(tenant_id))
    except (TypeError, ValueError, AttributeError):
        raise CustomerHistoryInputError("authenticated_tenant_invalid") from None
    if tenant != tenant_id:
        raise CustomerHistoryInputError("authenticated_tenant_invalid")
    if (not isinstance(as_of, datetime) or as_of.tzinfo is None
            or as_of.utcoffset() is None):
        raise CustomerHistoryInputError("preview_clock_invalid")
    clock = as_of.astimezone(timezone.utc)
    if type(horizon_days) is not int or not 1 <= horizon_days <= 365:
        raise CustomerHistoryInputError("forecast_horizon_invalid")
    if type(payload) is not bytes or not 1 <= len(payload) <= MAX_UPLOAD_BYTES:
        raise CustomerHistoryInputError("history_upload_size_invalid")
    try:
        text = payload.decode("utf-8-sig", errors="strict")
        if "\x00" in text:
            raise ValueError
        rows = list(csv.reader(StringIO(text, newline=""), strict=True))
    except (UnicodeError, csv.Error, ValueError):
        raise CustomerHistoryInputError("history_csv_invalid") from None
    if not rows or tuple(rows[0]) != _HEADER or len(rows) != HISTORY_DAYS + 1:
        raise CustomerHistoryInputError("history_csv_schema_or_row_count_invalid")

    today = clock.date()
    expected_dates = [today - timedelta(days=offset)
                      for offset in range(HISTORY_DAYS, 0, -1)]
    observations = []
    currencies: set[str] = set()
    for row, expected_date in zip(rows[1:], expected_dates, strict=True):
        if len(row) != 3:
            raise CustomerHistoryInputError("history_csv_row_invalid")
        try:
            observed_date = date.fromisoformat(row[0])
            if observed_date.isoformat() != row[0] or observed_date != expected_date:
                raise ValueError
            amount_text = row[1]
            if not amount_text.isascii() or not amount_text.isdecimal():
                raise ValueError
            amount = int(amount_text)
            if not 0 <= amount <= MAX_MINOR_UNITS:
                raise ValueError
            currency = row[2]
            if not _CURRENCY.fullmatch(currency):
                raise ValueError
        except (TypeError, ValueError):
            raise CustomerHistoryInputError("history_csv_row_invalid_or_incomplete") from None
        observations.append({
            "observed_date": observed_date.isoformat(),
            "value": amount,
            "source": "customer_provided_csv_unverified",
        })
        currencies.add(currency)
    if len(currencies) != 1:
        raise CustomerHistoryInputError("history_currency_mixed_or_missing")

    currency = next(iter(currencies))
    materialization = materialize_daily_actuals(
        metric=f"customer_revenue_minor_units_{currency}",
        rows=observations,
        value_field="value",
        date_field="observed_date",
        horizon_days=horizon_days,
        forecast_origin_date=today,
    )
    forecast = materialization.forecast
    return {
        "schema_version": "empire.predictive_revenue.customer_history_preview.v1",
        "status": "CUSTOMER_PROVIDED_HISTORY_PREVIEW_UNVERIFIED",
        "mode": "OBSERVE",
        "history_days_required": HISTORY_DAYS,
        "history_days_observed": len(observations),
        "observed_from_utc": expected_dates[0].isoformat(),
        "observed_through_utc": expected_dates[-1].isoformat(),
        "currency_code": currency,
        "forecast_horizon_days": horizon_days,
        "forecast_available": forecast.available,
        "forecast_metric": forecast.metric,
        "predicted_revenue_minor_units": forecast.predicted_value,
        "direction": forecast.direction,
        "model_sample_count": forecast.sample_count,
        "model_r_squared": forecast.r_squared,
        "model_evidence_confidence": forecast.evidence_confidence,
        "source_file_sha256": sha256(payload).hexdigest(),
        "tenant_bound_request_authenticated": True,
        "original_source_system_authenticated": False,
        "financial_finality_verified": False,
        "upload_persisted": False,
        "forecast_registered": False,
        "calibration_authorized": False,
        "customer_delivery_authorized": False,
        "execution_authority": "none",
    }
