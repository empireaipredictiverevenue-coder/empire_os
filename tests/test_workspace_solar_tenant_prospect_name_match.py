"""Authenticated CRM tenant read-only candidate matching, never identity proof."""
from copy import deepcopy
from uuid import UUID

import pytest

from empire_os.workspace_solar_crm_tenant_prospect_match import (
    TenantProspectMatchHeld, preview_six_tenant_prospect_name_matches,
)
from tests.test_revenue_crm_authenticated_router import (
    A,B,client_with_server_resolver,repo
)

def row(company, tenant=A, seq=1):
    return {
        "tenant_id":tenant,
        "prospect_id":f"00000000-0000-0000-0000-{seq:012d}",
        "business_name":company,
        "niche":"solar",
        "prospect_status":"new",
    }


def test_exact_normalized_name_matches_only_and_never_promotes():
    result=preview_six_tenant_prospect_name_matches([
        row("GB  NRG",seq=1),
        row("SOL PV GROUP",seq=2),
        row("GB NRG",seq=3),
        row("Some Different Company",seq=4),
    ],authenticated_tenant_id=A)
    assert result["tenant_visible_window_exhaustive"] is True
    assert result["possible_exact_company_name_matches"]==3
    by={x["company"]:x for x in result["items"]}
    assert by["GB NRG"]["possible_name_match_count"]==2
    assert by["GB NRG"]["status"]=="POSSIBLE_MULTIPLE_NAME_MATCHES_REQUIRE_DEDUP_REVIEW"
    assert by["SOL PV Group"]["possible_name_match_count"]==1
    assert by["Solar4Good"]["possible_name_match_count"]==0
    assert by["Solar4Good"]["status"]=="NO_EXACT_NAME_MATCH_IN_VISIBLE_TENANT_VIEW"
    assert result["canonical_contact_identity_verified"] is False
    assert result["tenant_contact_authority_verified"] is False
    assert result["historical_outbound_intent_bound"] is False
    assert result["crm_mutation"] is False
    assert result["outbound_sent"] is False
    assert not any(x["crm_contact_binding_verified"] for x in result["items"])


def test_psycopg_native_uuid_columns_supported_without_loosening_tenant_scope():
    """Real PostgreSQL uuid columns arrive as UUID, not JSON strings."""
    first=row("GB NRG",seq=71)
    first["tenant_id"]=UUID(A)
    first["prospect_id"]=UUID(first["prospect_id"])
    result=preview_six_tenant_prospect_name_matches(
        [first],authenticated_tenant_id=A,
    )
    assert result["possible_exact_company_name_matches"]==1
    assert next(x for x in result["items"] if x["company"]=="GB NRG")[
        "candidate_prospect_ids"
    ]==["00000000-0000-0000-0000-000000000071"]
    assert result["tenant_contact_authority_verified"] is False
    altered=dict(first,tenant_id=UUID(B))
    with pytest.raises(TenantProspectMatchHeld,match="CROSS_TENANT_CRM_ROW"):
        preview_six_tenant_prospect_name_matches(
            [altered],authenticated_tenant_id=A,
        )


def test_partial_view_is_never_exhaustive_negative():
    items=[row(f"unrelated {i}",seq=i+1) for i in range(500)]
    result=preview_six_tenant_prospect_name_matches(
        items,authenticated_tenant_id=A
    )
    assert result["tenant_visible_window_exhaustive"] is False
    assert all(
        entry["status"]=="NO_MATCH_IN_PARTIAL_TENANT_VIEW_NOT_EXHAUSTIVE"
        for entry in result["items"]
    )


@pytest.mark.parametrize("rows,tenancy,limit",[
    ([row("GB NRG",B)],A,500),
    ([row("GB NRG"),row("Solar4Good",seq=1)],A,500),
    ([row("GB NRG",tenant="not-uuid")],A,500),
    ([row("GB NRG",seq=1),{"tenant_id":A,"business_name":"x"}],A,500),
    ([row("\tGB NRG")],A,500),
    ([row("GB NRG")],"not-uuid",500),
    ([row("GB NRG")],A,0),
    ([row("GB NRG")],A,True),
    ([row("GB NRG")],A,501),
    ([row("GB NRG"),row("Solar4Good",seq=2)],A,1),
])
def test_cross_tenant_bad_schema_duplicates_and_limits_fail_closed(rows,tenancy,limit):
    with pytest.raises(TenantProspectMatchHeld):
        preview_six_tenant_prospect_name_matches(
            rows,authenticated_tenant_id=tenancy,window_limit=limit,
        )


def test_existing_crm_route_requires_server_authenticated_tenant():
    reader,_=repo()
    reader.prospects=lambda *,limit: [row("GB NRG",seq=3)]
    c=client_with_server_resolver(reader)
    path="/v1/revenue-crm/workspace-solar/prospect-name-matches/preview"
    denied=c.get(path,headers={
        "X-Tenant-ID":A,
        "Authorization":"Bearer someone-else",
    })
    assert denied.status_code==401
    assert denied.json()["detail"]=="authenticated_crm_scope_required"
    approved=client_with_server_resolver(reader,authenticated_tenant=A)
    result=approved.get(path)
    assert result.status_code==200
    payload=result.json()
    assert payload["tenant_visible_window_exhaustive"] is True
    assert payload["possible_exact_company_name_matches"]==1
    assert payload["items"][1]["company"]=="GB NRG"
    assert payload["items"][1]["candidate_prospect_ids"]==[
        "00000000-0000-0000-0000-000000000003"
    ]
    assert payload["crm_mutation"] is False


def test_authenticated_resolver_source_with_cross_tenant_row_returns_sanitized_error():
    reader,_=repo()
    reader.prospects=lambda *,limit: [row("GB NRG",B)]
    c=client_with_server_resolver(reader,authenticated_tenant=A)
    p=c.get("/v1/revenue-crm/workspace-solar/prospect-name-matches/preview")
    assert p.status_code==503
    assert p.json()["detail"]=="crm_tenant_name_match_source_invalid"
    assert A not in p.text and B not in p.text


def test_authenticated_route_rejects_untrusted_query_tenant_overrides():
    reader,_=repo()
    reader.prospects=lambda *,limit: [row("GB NRG",seq=1)]
    c=client_with_server_resolver(reader,authenticated_tenant=A)
    p=c.get("/v1/revenue-crm/workspace-solar/prospect-name-matches/preview?tenant_id="+B,
            headers={"X-Tenant-ID":B})
    assert p.status_code==200
    assert p.json()["items"][1]["possible_name_match_count"]==1
    assert p.json()["tenant_contact_authority_verified"] is False
