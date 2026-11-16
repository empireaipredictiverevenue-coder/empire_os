"""Never simulate source presence as a live original EmpireDB result."""
import json

from scripts.probe_predictive_original_source_catalog_readonly import (
    FIELDS, QUERY, main, review_catalog,
)

ALL_PASS = {field: True for field in FIELDS}


def test_query_metadata_only_and_explicit_read_only():
    assert QUERY.startswith("BEGIN READ ONLY;")
    assert QUERY.rstrip().endswith("ROLLBACK;")
    assert "pg_catalog." in QUERY
    assert "CREATE " not in QUERY
    assert "UPDATE " not in QUERY
    assert "INSERT " not in QUERY
    assert "DELETE " not in QUERY
    assert "commercial_events" not in QUERY
    assert "SELECT *" not in QUERY


def test_independent_registry_and_census_both_need_catalogue_presence():
    def source(sql):
        assert sql == QUERY
        return json.dumps(ALL_PASS)
    report = review_catalog(admin_query=source)
    assert report["status"] == "SOURCE_CATALOGUE_PRESENT_NOT_AUTHENTICATED"
    assert report["source_contracts_both_present"] is True
    assert report["authenticated_forecast_rows_read"] is False
    assert report["customer_outcomes_read"] is False
    assert report["forecast_accuracy_measurable"] is False
    assert report["database_writes"] is False


def test_rev052_event_reader_alone_cannot_prove_forecast():
    facts = {**ALL_PASS,
        "forecast_registry_table_exists": False,
        "forecast_registry_force_rls": False,
        "forecast_registry_reader_role_safe": False,
        "restricted_day_census_function_exists": False,
    }
    report = review_catalog(admin_query=lambda _: json.dumps(facts))
    assert report["catalogue_facts"]["rev052_single_event_reader_exists"] is True
    assert report["status"] == "FORECAST_OR_CENSUS_SOURCE_CATALOGUE_INCOMPLETE"
    assert report["source_contracts_both_present"] is False


def test_bad_or_dangerous_catalogue_payload_rejected():
    for payload in ('{}', '[]', 'not json',
                    json.dumps({**ALL_PASS, "correct_database": "true"}),
                    json.dumps({**ALL_PASS, "secret": "not allowed"})):
        report = review_catalog(admin_query=lambda _, raw=payload: raw)
        assert report["status"] == "CATALOG_UNAVAILABLE_HOLD"
        assert report["catalogue_facts"] is None
    wrong = review_catalog(admin_query=lambda _: json.dumps(
        {**ALL_PASS, "correct_database": False}))
    assert wrong["status"] == "WRONG_OR_UNTRUSTED_DATABASE_HOLD"
    assert wrong["catalogue_facts"] is None


def test_read_errors_sanitized():
    def denied(_):
        raise RuntimeError("DB password supersecret")
    report = review_catalog(admin_query=denied)
    assert report["status"] == "CATALOG_UNAVAILABLE_HOLD"
    assert "supersecret" not in json.dumps(report)


def test_main_denies_unauthorized_privileged_catalogue(monkeypatch, capsys):
    monkeypatch.setattr("scripts.probe_predictive_original_source_catalog_readonly.os.geteuid", lambda: 1000)
    assert main(["--read-only"]) == 2
    assert main([]) == 2
    seen = capsys.readouterr().out
    assert "EXPLICIT_ROOT_READ_ONLY_SESSION_REQUIRED" in seen
