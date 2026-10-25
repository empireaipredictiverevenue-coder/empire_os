// Real first-party website GET/navigation observation only.
// No forms, no buyer data and no outbound POSTs.
import {spawn} from "node:child_process";
import {mkdtempSync,rmSync} from "node:fs";
import {tmpdir} from "node:os";
import {join} from "node:path";
import assert from "node:assert/strict";

const origin="https://empire-ai.co.uk";
const expectPreview = process.argv.includes("--expect-preview");
if(process.argv.some(arg=>arg.startsWith("--") && arg!=="--expect-preview")){
 throw Error("INVALID_PUBLIC_NAVIGATION_MODE");
}
const chrome="/home/ubuntu/.cache/puppeteer/chrome-headless-shell/linux-153.0.8010.36/chrome-headless-shell-linux64/chrome-headless-shell";
const port=28786, profile=mkdtempSync(join(tmpdir(),"empire-public-nav-"));
const proc=spawn(chrome,["--no-sandbox","--headless","--disable-gpu","--disable-dev-shm-usage","--remote-allow-origins=*",
 `--remote-debugging-port=${port}`,`--user-data-dir=${profile}`,"--window-size=1365,1000",origin+"/commercial"],{stdio:"ignore"});
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
let ws,serial=0;
const pending=new Map(),errors=[],posts=[],failedRequests=[],routeCalls=[];
function send(method,params={}){
 const id=++serial;return new Promise((resolve,reject)=>{pending.set(id,{resolve,reject});ws.send(JSON.stringify({id,method,params}))});
}
async function evaluate(expression){
 const result=await send("Runtime.evaluate",{expression,returnByValue:true,awaitPromise:true});
 if(result.result?.exceptionDetails)throw Error(JSON.stringify(result.result.exceptionDetails).slice(0,400));
 return result.result?.result?.value;
}
async function until(expression,max=110){
 for(let i=0;i<max;i++){try{const x=await evaluate(expression);if(x)return x;}catch{}await sleep(100)}
 throw Error("LIVE_BROWSER_NAV_TIMEOUT:"+expression);
}
try{
 let address;
 for(let i=0;i<70;i++){
  try{const tabs=await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();address=tabs.find(x=>x.type==="page")?.webSocketDebuggerUrl;if(address)break}catch{}
  await sleep(100);
 }
 assert.ok(address,"browser debugger");
 ws=new WebSocket(address);
 await new Promise((resolve,reject)=>{ws.addEventListener("open",resolve,{once:true});ws.addEventListener("error",reject,{once:true})});
 ws.addEventListener("message",event=>{
  const m=JSON.parse(event.data);
  if(m.id&&pending.has(m.id)){const r=pending.get(m.id);pending.delete(m.id);m.error?r.reject(Error(JSON.stringify(m.error))):r.resolve(m);}
  if(m.method==="Runtime.exceptionThrown")errors.push(m.params?.exceptionDetails?.text||"exception");
  if(m.method==="Network.requestWillBeSent"){
   const req=m.params?.request;
   if(req?.method==="POST")posts.push(req.url);
   if(req?.url?.startsWith(origin)&&(/predictive-revenue|\.txt|_rsc=/.test(req.url)))routeCalls.push({method:req.method,url:req.url.slice(0,165)});
  }
  if(m.method==="Network.responseReceived"){
   const r=m.params?.response;
   if(r?.url?.startsWith(origin)&&r.status>=400)failedRequests.push({url:r.url.slice(0,180),status:r.status});
  }
 });
 await send("Network.enable");await send("Runtime.enable");await send("Page.enable");
 await until('document.querySelector("a[href=\'/predictive-revenue\']")!==null');
 const before=await evaluate('({url:location.href, hasCommercialForm:!!document.querySelector("#commercial-enquiry")})');
 await evaluate('document.querySelector("a[href=\'/predictive-revenue\']").click()');
 await until('location.pathname === "/predictive-revenue" && document.querySelector("#deployment-request")!==null',145);
 await sleep(1700);
 const after=await evaluate('({url:location.href, newPreview:!!document.querySelector("#free-evidence-sample"), originalForm:!!document.querySelector("#deployment-request"), commercialSalesProductList:document.body.innerText.includes("Diagnostic"), hasConsent:!!document.querySelector("#deployment-request input[type=checkbox][required]")})');
 assert.equal(after.originalForm,true);
 assert.equal(after.hasConsent,true);
 assert.equal(after.newPreview,expectPreview);
 assert.equal(posts.length,0);
 assert.deepEqual(failedRequests,[]);
 assert.deepEqual(errors,[]);
 const requiredChunk=expectPreview
   ? "page-119dcf00a0b5a51e.js"
   : "page-8a641c1798fea86e.js";
 assert.ok(routeCalls.some(req=>req.url.includes(requiredChunk)),
           "Expected versioned Predictive Revenue JS chunk not loaded");
 console.log(JSON.stringify({
  status:expectPreview ? "PUBLIC_NEW_SAAS_BROWSER_NAV_VERIFIED" :
                         "PUBLIC_EXISTING_SITE_GET_ONLY_NAV_OBSERVED",
  validation_mode:expectPreview ? "after" : "before",
  from:before.url,to:after.url,
  html_and_form_work:after.originalForm,
  preview_visible:after.newPreview,
  catalog_text_present:after.commercialSalesProductList,
  navigation_fetches:routeCalls,
  errors_4xx_5xx:failedRequests,
  javascript_exceptions:errors,
  post_requests:posts.length,
  real_customer_submission_performed:false,
  publication_performed:false,
 },null,2));
}finally{
 if(ws)ws.close();
 proc.kill("SIGTERM");
 await sleep(400);
 try{rmSync(profile,{recursive:true,force:true,maxRetries:10,retryDelay:200})}catch{}
}
