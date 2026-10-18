"""Production-facing availability bridge for existing Data Brokerage sales drafts.

Reads an authenticated *internal* offer review and a publicly readable
enquiry-offer catalog. Does not create public offers, prospect rows,
products, users, company identities, outbound messages or payments.
"""
from __future__ import annotations
from collections.abc import Mapping
from typing import Any

from empire_os.data_brokerage_sales_activation import (
    SAFE_OFFERS, validate_sales_activation_review,
)

SCHEMA="empire.data_brokerage.public_enquiry_visibility.v1"

# Exact **existing** approved one-time commercial catalog relationship.
# The other two private prices are NOT founder-approved public prices.
PUBLIC_ENTRY = {
    "roofing_competitor_report": ("competitor_search_gap","USD",19900,"one_time"),
}
PRIVATE_ONLY = frozenset({
    "agency_white_label_search",
    "portfolio_geography_intelligence",
})

def review_visibility(private:Mapping[str,Any],
                      public:Mapping[str,Any])->dict[str,Any]:
    if not validate_sales_activation_review(private):
        raise ValueError("UNTRUSTED_PRIVATE_SALES_PACKAGE_REVIEW")
    if (not isinstance(public,Mapping)
        or public.get("schema_version")!="empire.first-party-commercial-interest.v1"
        or public.get("status")!="FOUNDER_LED_ENQUIRY_AVAILABLE"
        or public.get("scope")!="BUYER_INITIATED_CONTACT_ONLY"
        or public.get("outbound_authority")!="none"
        or public.get("payment_authority")!="none"
        or public.get("checkout_authorized") is not False
        or public.get("actual_revenue") is not False
        or public.get("commercial_terms_binding") is not False
        or type(public.get("count")) is not int
        or type(public.get("offers")) is not list
        or public["count"]!=len(public["offers"])
        or not 1<=public["count"]<=100):
        raise ValueError("PUBLIC_COMMERCIAL_CATALOG_UNTRUSTED")
    index={}
    for offer in public["offers"]:
        if (not isinstance(offer,Mapping) or type(offer.get("product_code")) is not str
            or not offer.get("product_code")
            or offer["product_code"] in index):
            raise ValueError("PUBLIC_PRODUCT_ID_UNTRUSTED_OR_DUPLICATED")
        index[offer["product_code"]]=offer

    # Do not interpret a public agency/territory listing as an automatic
    # approved recurring SKU: the source registry has prices only as hypotheses.
    if any(code in index for code in PRIVATE_ONLY):
        raise ValueError("UNAPPROVED_INTERNAL_PRICE_HYPOTHESIS_PUBLICLY_EXPOSED")
    listings=[]
    for item in private["packages"]:
        key=item["offer_code"]
        if key in PUBLIC_ENTRY:
            code,currency,cents,interval=PUBLIC_ENTRY[key]
            public_item=index.get(code)
            if not isinstance(public_item,Mapping):
                state="PUBLIC_ENTRY_NOT_AVAILABLE"
                proof=False
            else:
                proof=(
                    public_item.get("offer_family")=="intelligence_product"
                    and public_item.get("approved_price_cents")==cents
                    and type(public_item.get("approved_price_cents")) is int
                    and public_item.get("currency")==currency
                    and public_item.get("price_interval")==interval
                    and public_item.get("sale_mode")=="FOUNDER_LED_PROPOSAL_ONLY"
                    and public_item.get("checkout_enabled") is False
                    and public_item.get("binding_terms_ready") is False
                    and public_item.get("fulfilment_automated") is False
                )
                if not proof:
                    raise ValueError("FOUND_ENTRY_OFFER_WITH_UNTRUSTED_PUBLIC_PRICE_OR_AUTHORITY")
                state="PUBLIC_FOUNDER_ENQUIRY_VISIBLE_NOT_SALE"
            listings.append({
                "offer_code":key,"public_product_code":code,
                "visibility":state,
                "founder_enquiry_catalog_match":proof,
                "real_buyer_enquiry_submitted":False,
                "website_to_founder_crm_delivery_verified":False,
                "payment_or_contract_executed":False,
            })
        else:
            if key not in PRIVATE_ONLY:
                raise ValueError("UNEXPECTED_PRIVATE_PACKAGE")
            listings.append({
                "offer_code":key,
                "public_product_code":None,
                "visibility":"PRIVATE_ONLY_NO_PUBLIC_PURCHASE_OR_INTAKE_SKU",
                "founder_enquiry_catalog_match":False,
                "real_buyer_enquiry_submitted":False,
                "website_to_founder_crm_delivery_verified":False,
                "payment_or_contract_executed":False,
            })
    assert len(listings)==len(SAFE_OFFERS)
    verified=sum(x["founder_enquiry_catalog_match"] is True for x in listings)
    return {
        "schema_version":SCHEMA,
        "status":("ONE_PUBLIC_ENTRY_TWO_PRIVATE_RECURRING_DRAFTS"
                  if verified==1 else "BROKERAGE_NO_PUBLIC_ENTRY_ON_CURRENT_CATALOG"),
        "mode":"OBSERVE",
        "public_enquiry_offers_total":public["count"],
        "internal_brokerage_packages":len(listings),
        "public_entry_match_count":verified,
        "private_recurring_package_count":2,
        "packages":listings,
        "public_page_post_was_not_executed":True,
        "public_page_rendering_not_proved_by_catalog_alone":True,
        "end_to_end_website_to_crm_proved":False,
        "new_enquiry_or_purchase_executed":False,
        "founder_approval_required_before_new_public_package":True,
        "unapproved_price_exposed":False,
        "approved_public_agency_or_enterprise_prices":False,
        "raw_source_licensing_enabled":False,
        "customer_record_exported":False,
        "email_sent":False,"payment_activated":False,
        "database_writes":False,"website_mutation":False,
        "execution_authority":"NONE",
        "next_action":"ASTRA_EXISTING_COMMERCIAL_PAGE_ADD_UNPRICED_AGENCY_AND_ENTERPRISE_DISCOVERY_ONLY_AFTER_APPROVAL",
    }
