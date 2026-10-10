"""Portfolio-wide readiness is a projection, never commercial authority."""
import json
from pathlib import Path

from empire_os.revenue_completion_supervisor import (
    PORTFOLIO_SOURCES, PORTFOLIO_SCHEMAS, stream_portfolio_status,
)


def put(root: Path, source: str, payload: dict):
    p=root/PORTFOLIO_SOURCES[source]
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps({"schema_version":PORTFOLIO_SCHEMAS[source],**payload}))


def fixture(root: Path):
    put(root,"catalog",{
        "product_count":4,"active_count":3,"binding_terms_ready_count":2,
        "products":[
            {"product_code":"local_search_grid","product_family":"search_intelligence",
             "active":True,"binding_terms_ready":True},
            {"product_code":"solar_opportunity_map_gb","product_family":"search_intelligence",
             "active":True,"binding_terms_ready":True},
            {"product_code":"predictive_revenue_diagnostic","product_family":"predictive_revenue",
             "active":True,"binding_terms_ready":False},
            {"product_code":"legacy_starter","product_family":"recovered_mrr",
             "active":False,"binding_terms_ready":False},
        ]})
    put(root,"relationships",{
        "warm_business_action_queue":[
            {"company":"LeadBank","last_inbound_at":"2026-10-10T11:00:00Z","gmail_snapshot_fresh":True},
            {"company":"Fake Brand","last_inbound_at":"2026-10-10T11:00:00Z","gmail_snapshot_fresh":True},
        ],"partner_pilot_readiness_queue":[
            {"company":"LeadBank","gate_count_verified":0,"gate_count_total":9}]})
    put(root,"enterprise",{"review_ready_count":2,"actual_revenue":False})
    put(root,"exchange",{"buyer_seat_count":1057,"verified_market_price_count":0,
                          "actual_revenue":False})
    put(root,"lead_smart",{"traffic_enabled":False,
                           "routing":{"runtime_verified":False}})
    put(root,"payment",{"semantic_truth":{"real_payment_observed":False}})
    put(root,"funnel",{"recognized_revenue_cents":0})
    p=root/PORTFOLIO_SOURCES["contractors"]
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps({"schema":PORTFOLIO_SCHEMAS["contractors"],
                             "outbound_authorized":False}))


def by_key(report):
    return {x["stream_key"]:x for x in report["streams"]}


def test_exact_fourteen_streams_no_unearned_commercial_promotions(tmp_path):
    fixture(tmp_path)
    d=stream_portfolio_status(tmp_path)
    assert d["stream_count"]==14
    assert len(by_key(d))==14
    assert set(d["sources"].values())=={"READABLE_SCHEMA_VERIFIED"}
    assert d["catalog_totals"]=={"total":4,"active":3,"binding_terms_ready":2}
    assert d["warm_buyer_conversations_observed"]==1
    assert d["enterprise_internal_review_ready_count"]==2
    assert d["exchange_seat_records_not_verified_sellable"]==1057
    assert d["exchange_verified_market_price_count"]==0
    assert d["current_payment_observation"]=="NOT_OBSERVED"
    assert d["funnel_recognized_revenue_cents"]==0
    assert d["external_outbound_authorized"] is False
    assert d["payment_per_stream_attributed"] is False
    assert all(not x["actual_revenue"] for x in d["streams"])
    assert all(not x["gates"]["realised_revenue_proven"] for x in d["streams"])
    assert all(not x["gates"]["payment_proven"] for x in d["streams"])
    assert all(not x["gates"]["delivery_or_route_proven"] for x in d["streams"])
    assert all(not x["gates"]["complete_onboarding"] for x in d["streams"])


def test_solar_and_search_are_disjoint_and_catalog_not_a_customer(tmp_path):
    fixture(tmp_path)
    d=by_key(stream_portfolio_status(tmp_path))
    assert d["search_aeo_geo"]["catalog"]["terms_ready"]==1
    assert d["solar_intelligence"]["catalog"]["terms_ready"]==1
    for k in ("search_aeo_geo","solar_intelligence"):
        assert d[k]["stage"]=="CATALOG_READY_NO_BUYER_PROOF"
        assert d[k]["gates"]["verified_product_terms"] is True
        assert d[k]["gates"]["real_counterparty"] is False
        assert d[k]["actual_revenue"] is False
    assert d["lead_calls"]["gates"]["real_counterparty"] is True
    assert d["lead_calls"]["gates"]["current_buy_box_or_customer_need"] is False
    assert d["lead_calls"]["stage"]=="ENGAGED_AWAITING_VERIFIED_BUY_BOX"
    assert d["predictive_revenue"]["catalog"]["terms_ready"]==0


def test_claims_settlement_stays_legal_blocked_even_with_partner_evidence(tmp_path):
    fixture(tmp_path)
    d=by_key(stream_portfolio_status(tmp_path))
    x=d["claims_settlement_regulated"]
    assert x["stage"]=="LEGAL_AND_LICENSING_BLOCKED"
    assert x["legal_gate_required"] is True
    assert "REGULATED_CLAIMS_COMPENSATION_AND_LICENSING_HOLD" in x["blocking_evidence"]
    assert x["founder_outbound_authorized"] is False
    assert d["insurance_carrier_network"]["legal_gate_required"] is True
    assert d["insurance_carrier_network"]["gates"]["real_counterparty"] is False


def test_missing_sources_remain_unknown_not_false_proof(tmp_path):
    d=stream_portfolio_status(tmp_path)
    assert d["stream_count"]==14
    assert all(s=="MISSING_OR_UNEXPECTED_SCHEMA" for s in d["sources"].values())
    assert d["catalog_totals"]["total"] is None
    assert d["warm_buyer_conversations_observed"] is None
    assert d["funnel_recognized_revenue_cents"] is None
    assert d["current_payment_observation"]=="UNKNOWN"
    assert all(not r["gates"]["verified_product_terms"] for r in d["streams"])
    assert all(not r["actual_revenue"] for r in d["streams"])


def test_aggregate_payment_signal_not_product_attribution(tmp_path):
    fixture(tmp_path)
    put(tmp_path,"payment",{"semantic_truth":{"real_payment_observed":True}})
    put(tmp_path,"funnel",{"recognized_revenue_cents":150000})
    d=stream_portfolio_status(tmp_path)
    assert d["current_payment_observation"]=="PRESENT_REQUIRES_INDEPENDENT_ATTRIBUTION"
    assert d["funnel_recognized_revenue_cents"]==150000
    assert d["payment_per_stream_attributed"] is False
    assert d["actual_revenue_from_portfolio_proven"] is False
    assert all(not row["gates"]["payment_proven"] and not row["actual_revenue"]
               for row in d["streams"])


def test_unexpected_catalog_schema_does_not_make_fake_sellable_product(tmp_path):
    fixture(tmp_path)
    put(tmp_path,"catalog",{"schema_version":"untrusted.catalog.schema",
                             "product_count":4000,
                             "products":[{"product_code":"fake",
                                          "product_family":"search_intelligence",
                                          "active":True,"binding_terms_ready":True}]})
    d=stream_portfolio_status(tmp_path)
    assert d["sources"]["catalog"]=="MISSING_OR_UNEXPECTED_SCHEMA"
    assert d["catalog_totals"]["total"] is None
    assert by_key(d)["search_aeo_geo"]["catalog"]["terms_ready"]==0



def test_sent_legacy_one_pass_email_stays_proven_after_later_replies(tmp_path):
    from empire_os.commercial_relationship_registry import (
        LAST_CONSOLIDATED_BUYER_REQUEST, PARTNER_PILOT_SCOPES,
    )
    from empire_os.revenue_completion_supervisor import _archived_complete_buyer_requests
    p=tmp_path/"runtime/buyer_network_intelligence/buyer_partner_message_index_20261010.json"
    p.parent.mkdir(parents=True,exist_ok=True)
    threads=[]
    for key,src in PARTNER_PILOT_SCOPES.items():
        threads.append({
          "thread_id":src["reviewed_thread"],
          "message_count":2,"truncated":False,
          "messages":[
            {"id":LAST_CONSOLIDATED_BUYER_REQUEST[key],"labels":["SENT"]},
            {"id":"f"*15+"e","labels":["SENT"]},
          ],
        })
    threads.append({"thread_id":"1111111111111111","message_count":1,
                    "truncated":False,"messages":[{"id":"aaa","labels":[]}]})
    p.write_text(json.dumps({
      "schema_version":"empire.buyer_gmail_original_message_index.v1",
      "source":"empire_gmail_api_readonly","threads":threads,
    }))
    p.chmod(0o600)
    assert _archived_complete_buyer_requests(tmp_path)==3
    d=stream_portfolio_status(tmp_path)
    assert by_key(d)["lead_calls"]["past_complete_request_proven_count"]==3
    assert by_key(d)["lead_calls"]["new_request_authorized"] is False
    p.chmod(0o644)
    assert _archived_complete_buyer_requests(tmp_path)==0


def test_unverified_message_label_cannot_prove_a_buyer_request(tmp_path):
    from empire_os.commercial_relationship_registry import (
        LAST_CONSOLIDATED_BUYER_REQUEST, PARTNER_PILOT_SCOPES,
    )
    from empire_os.revenue_completion_supervisor import _archived_complete_buyer_requests
    p=tmp_path/"runtime/buyer_network_intelligence/buyer_partner_message_index_20261010.json"
    p.parent.mkdir(parents=True,exist_ok=True)
    threads=[]
    for key,src in PARTNER_PILOT_SCOPES.items():
        threads.append({
          "thread_id":src["reviewed_thread"],"message_count":1,
          "truncated":False,
          "messages":[{"id":LAST_CONSOLIDATED_BUYER_REQUEST[key],
                       "labels":["INBOX"]}],
        })
    threads.append({"thread_id":"1111111111111111","message_count":0,
                    "truncated":False,"messages":[]})
    p.write_text(json.dumps({
      "schema_version":"empire.buyer_gmail_original_message_index.v1",
      "source":"connected_gmail_connector_read_only","threads":threads,
    }))
    p.chmod(0o600)
    assert _archived_complete_buyer_requests(tmp_path)==0
