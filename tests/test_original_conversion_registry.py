"""Original conversion prediction: prospective, tenant-bound and dormant."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import json

import pytest

from empire_os.original_conversion_registry import (
    OriginalConversionRegistryUnavailable,
    build_registration_request, inspect_prospective_registry_readback,
)
from empire_os.original_conversion_registry_transport import (
    PostgresOriginalConversionRegistry, WRITER_ROLE, READER_ROLE, WRITE_SQL, READ_SQL,
)
from test_original_conversion_prediction_preflight import packet, NOW


def valid_review_material():
    candidate = packet()
    prediction = candidate["proposed_prediction"]
    digest = sha256(json.dumps(
        prediction, sort_keys=True, separators=(",", ":"),
    ).encode()).hexdigest()
    receipt = {
        "status": "recorded",
        "prediction_ref": prediction["prediction_ref"],
        "tenant_id": prediction["tenant_id"],
        "recorded_at": NOW.isoformat(),
        "payload_sha256": digest,
    }
    readback = {
        "prediction_ref": prediction["prediction_ref"],
        "tenant_id": prediction["tenant_id"],
        "recorded_at": NOW.isoformat(),
        "payload_sha256": digest,
        "prediction": dict(prediction),
    }
    return candidate, receipt, readback


def test_request_is_preflight_not_mutation_or_registration():
    request = build_registration_request(packet(), as_of=NOW)
    assert request["status"] == "DB_MIGRATION_AND_AUTH_REQUIRED"
    assert request["original_prediction_registered"] is False
    assert request["db_readback_verified"] is False
    assert request["database_writes"] is False
    assert request["time_safe_for_calibration"] is False
    assert request["execution_authority"] == "none"


def test_matching_mocked_receipt_never_pretends_authenticity():
    candidate, receipt, readback = valid_review_material()
    review = inspect_prospective_registry_readback(
        candidate, receipt=receipt, readback=readback, as_of=NOW,
    )
    assert review["status"] == "MATCHED_UNAUTHENTICATED_INPUT"
    assert review["consistent"] is True
    assert review["immutable_registry_proven"] is False
    assert review["original_prediction_registered"] is False
    assert review["eligible_for_calibration"] is False
    assert review["execution_authority"] == "none"


@pytest.mark.parametrize("modify,expected", [
    (lambda a,b: a.update(tenant_id="wrong"), "readback_identity_mismatch"),
    (lambda a,b: b.update(tenant_id="other"), "readback_identity_mismatch"),
    (lambda a,b: a.update(payload_sha256="f" * 64), "readback_hash_mismatch"),
    (lambda a,b: b["prediction"].update(predicted_probability=0.9), "readback_payload_mismatch"),
    (lambda a,b: b.update(recorded_at=(NOW + timedelta(minutes=1)).isoformat()), "readback_timestamp_mismatch"),
    (lambda a,b: a.update(recorded_at=(NOW - timedelta(minutes=15)).isoformat()), "readback_timestamp_mismatch"),
])
def test_receipt_disagreements_fail_closed(modify, expected):
    candidate, receipt, readback = valid_review_material()
    modify(receipt, readback)
    review = inspect_prospective_registry_readback(
        candidate, receipt=receipt, readback=readback, as_of=NOW,
    )
    assert review["status"] == "READBACK_HOLD"
    assert review["reason"] == expected
    assert review["eligible_for_calibration"] is False


def test_missing_receipt_does_not_look_like_negative_conversion():
    candidate, _, _ = valid_review_material()
    result = inspect_prospective_registry_readback(
        candidate, receipt=None, readback=None, as_of=NOW,
    )
    assert result["status"] == "READBACK_HOLD"
    assert result["original_prediction_registered"] is False
    assert result["eligible_for_calibration"] is False


def test_stale_candidate_refused_at_prewrite():
    expired = packet()
    with pytest.raises(ValueError, match="too old"):
        build_registration_request(
            expired, as_of=NOW + timedelta(minutes=6),
        )


def test_modified_candidate_identity_rejected():
    item = packet()
    item["proposed_prediction"]["predicted_probability"] = 0.7
    with pytest.raises(ValueError, match="digest or payload"):
        build_registration_request(item, as_of=NOW)


def test_disabled_transport_never_connects():
    called = []
    def forbidden(dsn):
        called.append(dsn)
        raise AssertionError("must never touch database")
    transport = PostgresOriginalConversionRegistry(connect_factory=forbidden)
    with pytest.raises(OriginalConversionRegistryUnavailable):
        transport.register(packet(), as_of=NOW)
    with pytest.raises(OriginalConversionRegistryUnavailable):
        transport.readback(tenant_id="tenant", prediction_ref="ref")
    assert called == []


def test_enabled_transport_requires_dedicated_both_connections():
    with pytest.raises(OriginalConversionRegistryUnavailable):
        PostgresOriginalConversionRegistry(enabled=True, writer_dsn="some", reader_dsn=None)
    with pytest.raises(ValueError):
        PostgresOriginalConversionRegistry(enabled=1)


class FakeCursor:
    def __init__(self, output, log):
        self.output, self.log = output, log
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    def execute(self, statement, params=None):
        self.log.append((statement, params))
    def fetchone(self):
        return (self.output,)


class FakeConnection:
    def __init__(self, output, log):
        self.output, self.log = output, log
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    def cursor(self):
        return FakeCursor(self.output, self.log)


def test_explicit_transport_uses_separate_transaction_local_roles():
    candidate, receipt, readback = valid_review_material()
    logs = {"writer": [], "reader": []}
    def connect(dsn):
        assert dsn in logs
        return FakeConnection(receipt if dsn == "writer" else readback, logs[dsn])
    adapter = PostgresOriginalConversionRegistry(
        writer_dsn="writer", reader_dsn="reader", enabled=True,
        connect_factory=connect,
    )
    result = adapter.register_review(candidate, as_of=NOW)
    assert result["status"] == "MATCHED_UNAUTHENTICATED_INPUT"
    assert logs["writer"][0] == ("SET LOCAL ROLE " + WRITER_ROLE, None)
    assert logs["writer"][1][0] == WRITE_SQL
    assert logs["reader"][0] == ("SET LOCAL ROLE " + READER_ROLE, None)
    assert logs["reader"][1][0] == READ_SQL
    assert logs["writer"][1][1][0] == "test-tenant"
    assert len(logs["writer"][1][1][3]) == 64
    assert result["eligible_for_calibration"] is False


def test_staged_sql_is_not_automatic_migration_and_contains_required_guards():
    sql = (Path(__file__).parents[1] /
           "docs/commercial/STAGED_ORIGINAL_CONVERSION_REGISTRY_20261018.sql").read_text()
    for required in (
        "STAGED ONLY", "current_database() <> 'empiredb'",
        "CREATE TABLE public.original_conversion_predictions",
        "ENABLE ROW LEVEL SECURITY", "FORCE ROW LEVEL SECURITY",
        "original_conversion_migrator_tenant_insert",
        "empire_current_tenant_id()", "CONV_REG_APPEND_ONLY",
        "SECURITY DEFINER", "NOLOGIN", "NOINHERIT",
        "REVOKE ALL", "GRANT EXECUTE", "CONV_REG_TENANT_NOT_AUTHENTICATED",
        "CONV_REG_IMMUTABLE_IDENTITY_COLLISION",
    ):
        assert required in sql
    assert "GRANT empire_original_conversion_prediction_writer TO " not in sql
    assert "GRANT empire_original_conversion_prediction_reader TO " not in sql
