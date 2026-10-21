"""Product coverage is not inferred from globally mixed or later revenue."""
import json

from empire_os.predictive_tenant_terminal_cohort_reader import CANDIDATE_SQL, LIMIT
from tests.test_predictive_tenant_terminal_cohort_reader import (
    run, candidate, uid, NOW,
)


def test_temporal_sql_requires_both_event_and_ingest_before_asof():
    assert "ce.occurred_at <= %s" in CANDIDATE_SQL
    assert "ce.created_at <= %s" in CANDIDATE_SQL
    assert "ce.occurred_at >= o.created_at" in CANDIDATE_SQL
    assert "ce.created_at >= o.created_at" in CANDIDATE_SQL
    _, calls = run([])
    sql, params = calls[-1]
    assert sql == CANDIDATE_SQL
    assert params == (NOW, NOW, LIMIT + 1)


def test_twenty_four_source_rows_for_one_product_not_scientific_authentication():
    rows = []
    for n in range(1, 25):
        row = candidate(n)
        rows.append((row[0], uid(2001), *row[2:]))
    rows.extend([candidate(101), candidate(102), candidate(103)])
    report, _ = run(rows)
    assert report["candidate_rows_observed"] == 27
    assert report["candidate_products_observed"] == 4
    assert report["largest_candidate_product_terminal_cohort"] == 24
    assert report["candidate_product_cohorts_reaching_20"] == 1
    assert report["source_census_complete"] is False
    assert report["customer_forecast_eligible"] is False
    assert report["source_rows_exported_to_scientific_training"] is False
    assert report["original_terminal_outcomes_independently_attested"] is False
    assert uid(2001) not in json.dumps(report)


def test_twenty_four_outcomes_spread_over_many_products_not_eligible():
    report, _ = run([candidate(i) for i in range(1,25)])
    assert report["candidate_products_observed"] == 24
    assert report["largest_candidate_product_terminal_cohort"] == 1
    assert report["candidate_product_cohorts_reaching_20"] == 0
    assert report["customer_forecast_eligible"] is False


def test_empty_product_cohort_is_not_a_false_training_zero():
    report, _ = run([])
    assert report["candidate_products_observed"] == 0
    assert report["largest_candidate_product_terminal_cohort"] == 0
    assert report["candidate_product_cohorts_reaching_20"] == 0
    assert report["original_terminal_outcomes_independently_attested"] is False
