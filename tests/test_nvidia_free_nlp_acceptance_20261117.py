"""NVIDIA synthetic NLP acceptance parsing and six-case contract."""
from scripts.accept_nvidia_free_nlp_six_20261117 import CASES, parse_count


def test_exactly_six_canonical_cases_and_filter_requirements():
    assert set(CASES)=={
        "buyer_demand_edge_count","capacity_edge_count",
        "unknown_demand_null","known_demand_zero",
        "product_market_join","positive_matching_capacity",
    }
    for question,sql,tokens in CASES.values():
        assert question and "ontology_edges" in sql
        assert all(t.lower() in sql.lower() for t in tokens)
        assert "COUNT(*)" in sql.upper()


def test_actual_sql_response_count_parsing():
    examples=[
        ([{"value":2}],2),
        ('[{"value": 2}]',2),
        (['[{"total": 0}]'],0),
        ([[{"count(*)":1}]],1),
        ('[{"value":"2"}]',2),
        ("[{'count': 1}]",1),
        (['[{"buyer_demands_lane_count":2}]'],2),
        (['[{"known_zero_count":0}]'],0),
        ({"rows":[{"n":0}]},0),
        (None,None),
        ("I think it is two",None),
    ]
    for payload,count in examples:
        assert parse_count(payload)==count
