// In-browser simulated first-party buyer submission on isolated localhost.
// CDP intercepts ALL checkout-interest POST requests and provides fake responses.
// Never communicates a synthetic enquiry to the public domain or EmpireDB.
import { spawn } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import assert from "node:assert/strict";

const origin="http://127.0.0.1:28741";
const endpoint="/v1/checkout/predictive-revenue/interests";
const chrome="/home/ubuntu/.cache/puppeteer/chrome-headless-shell/linux-153.0.8010.36/chrome-headless-shell-linux64/chrome-headless-shell";
const profile=mkdtempSync(join(tmpdir(),"empire-saas-intercept-"));
const port=28767;
const proc=spawn(chrome,[
 "--no-sandbox","--headless","--disable-gpu","--disable-dev-shm-usage",
 "--remote-allow-origins=*",
 `--remote-debugging-port=${port}`,
 `--user-data-dir=${profile}`,"--window-size=1440,1100",
 origin+"/predictive-revenue.html"
],{stdio:"ignore"});
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
let ws, nextId=0, responses=0;
const pending=new Map();
const posted=[];
const unsafePosts=[];
const errors=[];
let interceptFailure;
function send(method,params={}){
 const id=++nextId;
 return new Promise((resolve,reject)=>{
  pending.set(id,{resolve,reject});
  ws.send(JSON.stringify({id,method,params}));
 });
}
async function evaluate(expression){
 const r=await send("Runtime.evaluate",{expression,returnByValue:true,awaitPromise:true});
 if(r.result?.exceptionDetails)throw Error("SCRIPT_ERROR:"+r.result.exceptionDetails.text);
 return r.result?.result?.value;
}
async function until(expression,limit=120){
 for(let i=0;i<limit;i++){
  try{const x=await evaluate(expression);if(x)return x;}catch{}
  await pause(85);
 }
 throw Error("WAIT_FOR_CLIENT_FAILED:"+expression);
}
try {
 let endpointWS;
 for(let i=0;i<75;i++){
  try{
   const tabs=await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
   endpointWS=tabs.find(x=>x.type==="page")?.webSocketDebuggerUrl;
   if(endpointWS)break;
  }catch{}
  await pause(100);
 }
 assert.ok(endpointWS,"Chrome DevTools listener");
 ws=new WebSocket(endpointWS);
 await new Promise((resolve,reject)=>{
  ws.addEventListener("open",resolve,{once:true});
  ws.addEventListener("error",reject,{once:true});
 });
 ws.addEventListener("message",event=>{
  const msg=JSON.parse(event.data);
  if(msg.id&&pending.has(msg.id)){
   const entry=pending.get(msg.id);pending.delete(msg.id);
   msg.error?entry.reject(Error(JSON.stringify(msg.error))):entry.resolve(msg);
  }
  if(msg.method==="Runtime.exceptionThrown"){
   errors.push(msg.params.exceptionDetails.text);
  }
  if(msg.method==="Network.requestWillBeSent" &&
     msg.params?.request?.method==="POST" &&
     msg.params.request.url!==origin+endpoint){
    unsafePosts.push(msg.params.request.url);
  }
  if(msg.method==="Fetch.requestPaused"){
   const data=msg.params;
   const req=data.request;
   (async()=>{
    assert.equal(req.url,origin+endpoint);
    assert.equal(req.method,"POST");
    const payload=JSON.parse(req.postData);
    posted.push(payload);
    assert.ok(payload.idempotency_key);
    assert.equal(payload.business_name,"Synthetic QA Example");
    assert.equal(payload.email,"qa@example.test");
    assert.equal(payload.contact_consent,true);
    assert.equal(payload.website,"");
    assert.equal(payload.product_code,"predictive_revenue_diagnostic");
    assert.ok(payload.desired_outcome.includes("stage-to-cash"));
    const response=posted.length===1
      ? {detail:"Synthetic isolated transport failure"}
      : {decision:"deployment_interest_recorded",prospect_id:"synthetic-local-only-0001",actual_revenue:false};
    const status=posted.length===1?503:200;
    await send("Fetch.fulfillRequest",{
      requestId:data.requestId,
      responseCode:status,
      responseHeaders:[
        {name:"content-type",value:"application/json"},
        {name:"cache-control",value:"no-store"}
      ],
      body:Buffer.from(JSON.stringify(response)).toString("base64")
    });
    responses++;
   })().catch(error=>{interceptFailure=String(error);});
  }
 });
 await send("Runtime.enable");
 await send("Page.enable");
 await send("Network.enable");
 // This interception is installed before allowing *any* form submission.
 await send("Fetch.enable",{patterns:[{
   urlPattern:origin+endpoint,
   requestStage:"Request"
 }]});
 await until('document.querySelector("#deployment-request") !== null && document.querySelector("#free-evidence-sample") !== null');
 await until('document.querySelector("#deployment-request button[type=submit]") !== null || document.querySelector("#deployment-request button:not([type])") !== null');
 await until('document.querySelector("#deployment-request button:not([type])")?.disabled === true');
 await until('document.body.innerText.includes("Diagnostic")');
 // Fill synthetic, non-identifying QA values via React-compatible native setters.
 const filled=await evaluate(`(() => {
 const form=document.querySelector("#deployment-request");
 const values={
   "Example Group":"Synthetic QA Example",
   "you@company.com":"qa@example.test",
   "company.com":"example.test",
   "Roofing, SaaS, PE…":"SaaS",
   "UK, US, Europe…":"UK",
   "Forecast accuracy, pipeline conversion, market expansion, revenue leakage, portfolio intelligence…":
      "Check stage-to-cash evidence before requesting any paid deployment"
 };
 const set=(node,value)=>{
  const descriptor=Object.getOwnPropertyDescriptor(
   node.tagName==="TEXTAREA"?HTMLTextAreaElement.prototype:HTMLInputElement.prototype,"value");
  descriptor.set.call(node,value);
  node.dispatchEvent(new Event("input",{bubbles:true}));
 };
 for(const [key,value] of Object.entries(values)){
  const el=[...form.querySelectorAll("input,textarea")].find(x=>x.placeholder===key);
  if(!el)return {found:false,missing:key};
  set(el,value);
 }
 const consent=form.querySelector('input[type="checkbox"][required]');
 const button=[...form.querySelectorAll("button")].find(x=>x.innerText.includes("REQUEST DEPLOYMENT"));
 return {found:true,buttonInitiallyDisabled:button.disabled,consentInitiallyOff:!consent.checked,checkValid:form.checkValidity()};
 })()`);
 assert.equal(filled.found,true);
 assert.equal(filled.consentInitiallyOff,true);
 assert.equal(filled.buttonInitiallyDisabled,true);
 assert.equal(posted.length,0);
 // Demonstrate the explicit consent gate: without clicking it, there is no call.
 await evaluate('document.querySelector("#deployment-request input[type=checkbox][required]").click()');
 await until('document.querySelector("#deployment-request button:not([type])")?.disabled === false');
 await evaluate('document.querySelector("#deployment-request").requestSubmit()');
 await until('document.body.innerText.includes("Synthetic isolated transport failure")');
 assert.equal(posted.length,1);
 assert.equal(responses,1);
 assert.equal(posted[0].website,"");
 const firstKey=posted[0].idempotency_key;
 // User retries exact same request. Original component must retain idempotency.
 await evaluate('document.querySelector("#deployment-request").requestSubmit()');
 await until('document.body.innerText.includes("Deployment request recorded")');
 assert.equal(posted.length,2);
 assert.equal(responses,2);
 assert.equal(posted[1].idempotency_key,firstKey);
 assert.deepEqual(posted[0],posted[1]);
 const state=await evaluate(`(() => {
  const form=document.querySelector("#deployment-request");
  const submit=[...form.querySelectorAll("button")].find(x=>x.innerText.includes("REQUEST DEPLOYMENT"));
  return {submissionDisabled:submit.disabled,
          acceptanceVisible:document.body.innerText.includes("Deployment request recorded"),
          evidencePanelPresent:!!document.querySelector("#free-evidence-sample"),
          originalFormPresent:!!form};
 })()`);
 assert.equal(state.submissionDisabled,true);
 assert.equal(state.acceptanceVisible,true);
 assert.equal(state.evidencePanelPresent,true);
 assert.equal(interceptFailure,undefined);
 assert.deepEqual(unsafePosts,[]);
 assert.deepEqual(errors,[]);
 console.log(JSON.stringify({
   status:"ISOLATED_SAAS_FORM_CONSENT_RETRY_PASS",
   scenario:"Synthetic browser-only form with local CDP checkout interception",
   source_is_localhost:true,
   consent_required_before_submit:true,
   initial_unapproved_posts:0,
   intercepted_posts:posted.length,
   first_response:"503 synthetic failure",
   retry_response:"200 synthetic locally recorded",
   retry_idempotency_reused:true,
   accidental_duplicate_after_success_blocked:state.submissionDisabled,
   existing_customer_data_written:false,
   original_backend_invoked:false,
   unrelated_or_external_post_requests:unsafePosts.length,
   founder_crm_mutated:false,
   authentic_buyer_observed:false
 },null,2));
}finally{
 if(ws)ws.close();
 proc.kill("SIGTERM");
 await pause(500);
 try{rmSync(profile,{recursive:true,force:true,maxRetries:20,retryDelay:200});}catch{}
}
