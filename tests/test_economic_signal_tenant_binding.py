from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from empire_os.economic_signal_tenant_binding import (
    TenantEntityBindingError,
    resolve_tenant_entity_binding,
)


NOW = datetime(2026, 10, 6, 10, 0, tzinfo=timezone.utc)
TENANT = str(uuid4())
ENTITY = str(uuid4())


class Cursor:
    def __init__(self, rows):
        self.rows = rows
        self.executed = []

    def execute(self, sql, params):
        self.executed.append((" ".join(sql.split()), params))

    def fetchall(self):
        return list(self.rows)


def binding_row(
    *,
    kind="prospect",
    evidence_ref="canonical:prospect:123",
):
    return (
        TENANT,
        ENTITY,
        kind,
        evidence_ref,
        NOW - timedelta(days=1),
        None,
    )


def test_resolves_single_canonical_binding():
    cursor = Cursor([binding_row()])

    binding = resolve_tenant_entity_binding(
        cursor,
        tenant_id=TENANT,
        entity_id=ENTITY,
        as_of=NOW,
    )

    assert binding.tenant_id == TENANT
    assert binding.entity_id == ENTITY
    assert binding.binding_kind == "prospect"
    assert binding.evidence_ref == "canonical:prospect:123"
    assert binding.binding_ref.startswith(
        "empiredb:tenant_business_entity_bindings:"
    )


def test_query_requires_active_and_temporally_valid_binding():
    cursor = Cursor([binding_row()])

    resolve_tenant_entity_binding(
        cursor,
        tenant_id=TENANT,
        entity_id=ENTITY,
        as_of=NOW,
    )

    sql, params = cursor.executed[0]

    assert "active=true" in sql
    assert "valid_from <=" in sql
    assert "valid_until IS NULL OR valid_until >" in sql
    assert params[0] == TENANT
    assert params[1] == ENTITY


def test_missing_binding_fails_closed():
    with pytest.raises(
        TenantEntityBindingError,
        match="tenant_entity_binding_not_found",
    ):
        resolve_tenant_entity_binding(
            Cursor([]),
            tenant_id=TENANT,
            entity_id=ENTITY,
            as_of=NOW,
        )


def test_multiple_bindings_fail_closed():
    rows = [
        binding_row(kind="prospect"),
        binding_row(kind="observed"),
    ]

    with pytest.raises(
        TenantEntityBindingError,
        match="tenant_entity_binding_ambiguous",
    ):
        resolve_tenant_entity_binding(
            Cursor(rows),
            tenant_id=TENANT,
            entity_id=ENTITY,
            as_of=NOW,
        )


def test_missing_evidence_fails_closed():
    with pytest.raises(
        TenantEntityBindingError,
        match="binding_evidence_required",
    ):
        resolve_tenant_entity_binding(
            Cursor([binding_row(evidence_ref="")]),
            tenant_id=TENANT,
            entity_id=ENTITY,
            as_of=NOW,
        )


def test_unknown_binding_kind_fails_closed():
    with pytest.raises(
        TenantEntityBindingError,
        match="unsupported_binding_kind",
    ):
        resolve_tenant_entity_binding(
            Cursor([binding_row(kind="magic")]),
            tenant_id=TENANT,
            entity_id=ENTITY,
            as_of=NOW,
        )


def test_naive_as_of_rejected():
    with pytest.raises(
        TenantEntityBindingError,
        match="aware_as_of_required",
    ):
        resolve_tenant_entity_binding(
            Cursor([binding_row()]),
            tenant_id=TENANT,
            entity_id=ENTITY,
            as_of=datetime(2026, 10, 6, 10, 0),
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("tenant_id", "not-a-uuid"),
        ("entity_id", "not-a-uuid"),
    ],
)
def test_invalid_uuid_rejected(field, value):
    kwargs = {
        "tenant_id": TENANT,
        "entity_id": ENTITY,
    }
    kwargs[field] = value

    with pytest.raises(TenantEntityBindingError):
        resolve_tenant_entity_binding(
            Cursor([binding_row()]),
            as_of=NOW,
            **kwargs,
        )
