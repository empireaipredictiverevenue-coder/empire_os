// Retry-safety contract: no customer contact or production writes.
import {test} from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import {
  reuseCommercialInterestAttempt as reuse,
} from "../apps/empire-public-site/src/lib/commercial-interest-attempt.ts";

const details={
  product_code:"consultancy_opportunity_assessment",
  business_name:"Example Ltd",email:"buyer@example.test",
  domain:"example.test",industry:"Professional services",
  geography:"United Kingdom",desired_outcome:"Improve sales qualification and reply handling.",
  contact_consent:true,website:"",
};
const pageFile=new URL("../apps/empire-public-site/src/app/commercial/page.tsx",import.meta.url);

test("retry of identical consented enquiry always reuses the exact source key",()=>{
  let generated=0;
  const next=()=>`commercial-test-${++generated}-secure`;
  const first=reuse(null,details,next);
  const uncertainNetworkResponse=reuse(first,{...details},next);
  const retryAfterTimeout=reuse(uncertainNetworkResponse,{...details},next);
  assert.strictEqual(first,uncertainNetworkResponse);
  assert.strictEqual(first,retryAfterTimeout);
  assert.equal(generated,1);
  assert.match(first.idempotencyKey,/^commercial-test-1-secure$/);
});

test("materially changed visitor inputs require a new request key",()=>{
  let generated=0; const next=()=>`commercial-key-${++generated}`;
  const first=reuse(null,details,next);
  const variants=[
    {product_code:"consultancy_strategy_blueprint"},
    {business_name:"Other Example Ltd"},
    {email:"other@example.test"},
    {domain:"other.example.test"},
    {industry:"Roofing"},
    {geography:"United States"},
    {desired_outcome:"Improve staff capacity and lead qualification."},
    {contact_consent:false},
    {website:"a honeypot value"},
  ];
  for(const delta of variants) {
    const changed=reuse(first,{...details,...delta},next);
    assert.notEqual(changed.idempotencyKey,first.idempotencyKey);
  }
  assert.equal(generated,1+variants.length);
});

test("no insecure key fallback when browser crypto is absent or invalid",()=>{
  const noCrypto=()=>{throw Error("secure_commercial_key_unavailable");};
  assert.throws(()=>reuse(null,details,noCrypto),/secure_commercial_key_unavailable/);
  const before=reuse(null,details,()=>"valid-frontend-key-123");
  assert.strictEqual(reuse(before,{...details},noCrypto),before);
  for(const bad of ["","short","abc@unsafe","".padEnd(129,"x")]) {
    assert.throws(()=>reuse(null,details,()=>bad),/secure_commercial_key_unavailable/);
  }
});

test("commercial form wires in stable key, blocks resubmit after receipt",()=>{
  const source=fs.readFileSync(pageFile,"utf8");
  assert.match(source,/enquiryAttemptRef = useRef<CommercialInterestAttempt \| null>\(null\)/);
  assert.match(source,/reuseCommercialInterestAttempt\(/);
  assert.match(source,/enquiryAttemptRef\.current = attempt/);
  assert.match(source,/idempotency_key: attempt\.idempotencyKey/);
  assert.match(source,/result\?\.decision === "commercial_enquiry_recorded"/);
  assert.match(source,/Secure request identity unavailable/);
  assert.doesNotMatch(source,/idempotency_key: crypto\.randomUUID\(\)/);
  assert.doesNotMatch(source,/Math\.random\(/);
  assert.doesNotMatch(source,/sessionStorage|localStorage/);
});
