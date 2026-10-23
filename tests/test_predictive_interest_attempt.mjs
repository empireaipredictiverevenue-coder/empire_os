// Source-level proof only. No HTTP or customer data submitted.
import {test} from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import {reusePredictiveInterestAttempt as reuse} from "../apps/empire-public-site/src/lib/predictive-interest-attempt.ts";

const fields={
  product_code:"predictive_revenue_enterprise", business_name:"Example Company",
  email:"buyer@example.test", domain:"example.test",industry:"SaaS",
  geography:"UK",annual_revenue_band:"unknown",
  desired_outcome:"Understand pipeline conversion and lost recurring revenue.",
  systems:["CRM","Search / SEO"], contact_consent:true,website:"",
};
const page=new URL("../apps/empire-public-site/src/app/predictive-revenue/page.tsx",import.meta.url);

test("same request and consent use one key after uncertain network response",()=>{
  let n=0;const gen=()=>`predictive-secure-key-${++n}`;
  const first=reuse(null,fields,gen);
  const again=reuse(first,{...fields,systems:[...fields.systems].reverse()},gen);
  const retry=reuse(again,{...fields},gen);
  assert.strictEqual(again,first);
  assert.strictEqual(retry,first);
  assert.equal(n,1);
});

test("changed request, permission, integration, or revenue band rotates the key",()=>{
  let n=0;const gen=()=>`predictive-secure-key-${++n}`;
  const first=reuse(null,fields,gen);
  const alternatives=[
    {product_code:"new_product"}, {business_name:"New Company"},
    {email:"new@example.test"}, {domain:"another.example.test"},
    {industry:"Roofing"}, {geography:"US"},
    {annual_revenue_band:"1m_5m"}, {desired_outcome:"Another requirement"},
    {systems:["CRM"]}, {contact_consent:false}, {website:"bot fill"},
  ];
  for (const patch of alternatives) {
    const next=reuse(first,{...fields,...patch},gen);
    assert.notEqual(next.idempotencyKey,first.idempotencyKey);
  }
  assert.equal(n,1+alternatives.length);
});

test("missing browser crypto must not invent a weak timestamp or Math.random key",()=>{
  const fail=()=>{throw Error("secure_predictive_key_unavailable")};
  assert.throws(()=>reuse(null,fields,fail),/secure_predictive_key_unavailable/);
  const first=reuse(null,fields,()=> "real-safe-request-uuid");
  assert.equal(reuse(first,{...fields},fail),first);
  for(const bad of ["","x","a@b","x".repeat(130)]) {
    assert.throws(()=>reuse(null,fields,()=>bad),/secure_predictive_key_unavailable/);
  }
});

test("existing form uses same key and permits no duplicate after success",()=>{
  const text=fs.readFileSync(page,"utf8");
  assert.match(text,/enquiryAttemptRef = useRef<PredictiveInterestAttempt \| null>\(null\)/);
  assert.match(text,/reusePredictiveInterestAttempt\(/);
  assert.match(text,/enquiryAttemptRef\.current = attempt/);
  assert.match(text,/idempotency_key: attempt\.idempotencyKey/);
  assert.match(text,/result\?\.decision === "deployment_interest_recorded"/);
  assert.match(text,/Secure request identity unavailable/);
  assert.match(text,/No order was placed/);
  assert.doesNotMatch(text,/Math\.random\(/);
  assert.doesNotMatch(text,/Date\.now\(/);
  assert.doesNotMatch(text,/localStorage|sessionStorage/);
});
