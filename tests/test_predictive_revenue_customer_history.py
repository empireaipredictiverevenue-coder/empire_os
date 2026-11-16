from datetime import datetime, timedelta, timezone

import pytest

from empire_os.predictive_revenue_customer_history import (
    CustomerHistoryInputError, preview_customer_history_csv,
)
from test_predictive_enterprise_crm_http import TENANT, fixture_client


def csv_payload(*, now=None, values=None, currency='GBP'):
    clock = now or datetime.now(timezone.utc)
    amounts = values or [index * 100 for index in range(1, 31)]
    lines = ['date,revenue_minor_units,currency_code']
    for index, amount in enumerate(amounts):
        day = clock.date() - timedelta(days=30-index)
        lines.append(f'{day.isoformat()},{amount},{currency}')
    return ('\n'.join(lines) + '\n').encode()


def test_preview_requires_complete_last_30_days_and_keeps_claims_unverified():
    now = datetime(2026, 11, 16, 12, tzinfo=timezone.utc)
    result = preview_customer_history_csv(
        csv_payload(now=now), tenant_id=TENANT, as_of=now,
    )
    assert result['status'] == 'CUSTOMER_PROVIDED_HISTORY_PREVIEW_UNVERIFIED'
    assert result['history_days_required'] == 30
    assert result['history_days_observed'] == 30
    assert result['observed_from_utc'] == '2026-10-17'
    assert result['observed_through_utc'] == '2026-11-15'
    assert result['currency_code'] == 'GBP'
    assert result['forecast_horizon_days'] == 30
    assert result['forecast_available'] is True
    assert result['tenant_bound_request_authenticated'] is True
    assert result['original_source_system_authenticated'] is False
    assert result['financial_finality_verified'] is False
    assert result['upload_persisted'] is False
    assert result['forecast_registered'] is False
    assert result['calibration_authorized'] is False


def test_preview_rejects_missing_day_currency_change_and_client_scope():
    now = datetime(2026, 11, 16, 12, tzinfo=timezone.utc)
    missing = csv_payload(now=now).decode().splitlines()
    missing.pop(2)
    with pytest.raises(CustomerHistoryInputError):
        preview_customer_history_csv(
            ('\n'.join(missing) + '\n').encode(), tenant_id=TENANT, as_of=now,
        )
    mixed = csv_payload(now=now).decode().splitlines()
    mixed[2] = mixed[2].replace(',GBP', ',USD')
    with pytest.raises(CustomerHistoryInputError):
        preview_customer_history_csv(
            ('\n'.join(mixed) + '\n').encode(), tenant_id=TENANT, as_of=now,
        )
    with pytest.raises(CustomerHistoryInputError):
        preview_customer_history_csv(
            csv_payload(now=now), tenant_id='client-supplied', as_of=now,
        )


def test_existing_crm_login_and_db_tenant_binding_guard_upload(tmp_path):
    client, cursor, reads = fixture_client(tmp_path)
    payload = csv_payload()
    response = client.post(
        '/v1/revenue-crm/predictive-diagnostic/customer-history/forecast-preview',
        content=payload, headers={'Content-Type': 'text/csv'},
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['forecast_available'] is True
    assert result['upload_persisted'] is False
    assert result['forecast_registered'] is False
    assert reads == [True]
    assert cursor.calls[0][0] == 'SET TRANSACTION READ ONLY'
    assert all(not sql.startswith(('INSERT', 'UPDATE', 'DELETE'))
               for sql, _ in cursor.calls)
    assert TENANT not in response.text
    assert payload.decode().splitlines()[-1] not in response.text


def test_unauthenticated_customer_history_upload_never_reads_db(tmp_path):
    client, _, reads = fixture_client(tmp_path, authenticated=False)
    response = client.post(
        '/v1/revenue-crm/predictive-diagnostic/customer-history/forecast-preview',
        content=csv_payload(), headers={'Content-Type': 'text/csv'},
    )
    assert response.status_code == 401
    assert reads == []


def test_upload_bounds_and_query_shape_are_rejected_before_database_read(tmp_path):
    client, _, reads = fixture_client(tmp_path)
    path = '/v1/revenue-crm/predictive-diagnostic/customer-history/forecast-preview'
    oversized = client.post(
        path, content=b'x' * 32769,
        headers={'Content-Type': 'text/csv'},
    )
    duplicate_horizon = client.post(
        path + '?horizon_days=7&horizon_days=30', content=b'x',
        headers={'Content-Type': 'text/csv'},
    )
    wrong_content_type = client.post(
        path, content=b'x', headers={'Content-Type': 'application/json'},
    )
    assert oversized.status_code == 413
    assert duplicate_horizon.status_code == 422
    assert wrong_content_type.status_code == 415
    assert reads == []
