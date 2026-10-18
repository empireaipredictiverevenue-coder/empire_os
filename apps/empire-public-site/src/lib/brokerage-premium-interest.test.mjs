import { test } from "node:test";
import assert from "node:assert/strict";
import {
  PREMIUM_DISCOVERY_CODES,PREMIUM_DISCOVERY_ENDPOINT,
  parsePremiumDiscoveryCatalog,parsePremiumDiscoveryReceipt,
} from "./brokerage-premium-interest.ts";

const choices = PREMIUM_DISCOVERY_CODES.map((code,i)=>({
  product_code:code,
  title:i ? "Territory Intelligence" : "Agency Market Intelligence",
  buyer_problem:"Evidence-backed market research for serious commercial decisions",
  price_state:"DISCUSS_CUSTOM_SCOPE",
  public_approved_price_available:false,
  request_type:"NONBINDING_FOUNDER_ENQUIRY",
  checkout_enabled:false,
}));
function catalog() {
  return {
    schema_version:"empire.data_brokerage.gateway_candidate.v1",
    status:"UNPRICED_DISCOVERY_CHOICES_NONBINDING",
    count:2,
    offers:structuredClone(choices),
    marketing_consent_included:false,
    customer_delivery_enabled:false,
    binding_terms_ready:false,
    payment_authorized:false,
  };
}
function receipt() {
  return {
    decision:"commercial_enquiry_recorded",
    product_code:PREMIUM_DISCOVERY_CODES[0],
    reference:"1234567890abcdef1234",
    next_step:"FOUNDER_PRIVATE_SCOPE_REVIEW",
    binding_terms_ready:false,payment_action:false,revenue_recognized:false,
  };
}
test("fixed same-origin, first-party premium path",()=>{
  assert.equal(PREMIUM_DISCOVERY_ENDPOINT,"/v1/checkout/brokerage/premium-discovery");
  assert.equal(PREMIUM_DISCOVERY_CODES.length,2);
});

test("only unpriced matching two-product catalog is accepted",()=>{
  const parsed=parsePremiumDiscoveryCatalog(catalog());
  assert.ok(parsed);
  assert.equal(parsed.offers.length,2);
  assert.equal(parsed.offers[0].price_state,"DISCUSS_CUSTOM_SCOPE");
});
test("cannot render invented prices, paid SKUs, or consent claims",()=>{
  const changes=[
    x=>x.offers[0].public_approved_price_available=true,
    x=>x.offers[0].approved_price_cents=125000,
    x=>x.offers[0].price_state="£1250/month",
    x=>x.offers[0].product_code="agency_white_label_search",
    x=>x.offers[1].product_code=x.offers[0].product_code,
    x=>x.offers[1].checkout_enabled=true,
    x=>x.count=3,
    x=>x.payment_authorized=true,
    x=>x.marketing_consent_included=true,
    x=>x.customer_delivery_enabled=true,
    x=>x.binding_terms_ready=true,
    x=>x.status="PREMIUM_SUBSCRIPTIONS_LIVE",
  ];
  for(const change of changes){
    const bad=catalog();change(bad);
    assert.equal(parsePremiumDiscoveryCatalog(bad),null,change.toString());
  }
});
test("only canonical acknowledgement for matching chosen code is accepted",()=>{
  const valid=receipt();
  assert.ok(parsePremiumDiscoveryReceipt(valid,PREMIUM_DISCOVERY_CODES[0]));
  assert.equal(parsePremiumDiscoveryReceipt(valid,PREMIUM_DISCOVERY_CODES[1]),null);
});
test("untrusted financial/identity receipts cannot be displayed",()=>{
  const changes=[
    x=>x.reference="customer@private.example",
    x=>x.reference="x".repeat(20),
    x=>x.decision="payment_received",
    x=>x.binding_terms_ready=true,
    x=>x.payment_action=true,
    x=>x.revenue_recognized=true,
    x=>x.next_step="SUBSCRIPTION_ACTIVE",
  ];
  for(const change of changes){
    const bad=receipt();change(bad);
    assert.equal(parsePremiumDiscoveryReceipt(bad,PREMIUM_DISCOVERY_CODES[0]),null);
  }
});
