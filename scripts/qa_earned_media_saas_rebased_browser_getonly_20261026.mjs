// Read-only browser QA of the privately rebased website: exact CTA, JS,
// same-origin consent form, existing new SaaS preview, zero POST/customer data.
import assert from "node:assert/strict";
import {spawn} from "node:child_process";
import {readFileSync, mkdtempSync, rmSync} from "node:fs";
import {tmpdir} from "node:os";
import {join} from "node:path";

const root="/home/ubuntu/empire_releases/earned_media_saas_union_20261026";
const r=JSON.parse(readFileSync(join(root,"private_candidate_receipt.json"),"utf8"));
assert.equal(r.status,"OFFLINE_REBASED_CTA_SAAS_CANDIDATE_NOT_OWNER_APPROVED");
const pageChunk=r.build.original_build_chunk.split("/").at(-1);
const origin="http://127.0.0.1:28964";
const chrome="/home/ubuntu/.cache/puppeteer/chrome-headless-shell/linux-153.0.8010.36/chrome-headless-shell-linux64/chrome-headless-shell";
const profile=mkdtempSync(join(tmpdir(),"empire-rebased-cta-qa-"));
const server=spawn("/srv/empire_os/.venv/bin/python",[
  "-B","-m","scripts.serve_earned_media_saas_preview_getonly_20261026"
],{cwd:"/home/ubuntu/empire_worktrees/earned_media_advisory_bridge_20261025",stdio:"ignore"});
const browserPort=28965;
let browser,ws,serial=0;
const pending=new Map(),exceptions=[],posts=[],badResponses=[],externalRequests=[],scriptRequests=[];
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const start=Date.now();

function send(method,params={}){
  const id=++serial;
  return new Promise((resolve,reject)=>{
    pending.set(id,{resolve,reject});
    ws.send(JSON.stringify({id,method,params}));
  });
}
async function evaluate(expression){
  const packet=await send("Runtime.evaluate",{
    expression,returnByValue:true,awaitPromise:true
  });
  if(packet.result?.exceptionDetails)throw Error("JS_EVALUATION_FAILED");
  return packet.result?.result?.value;
}
async function until(expression,max=145){
  for(let i=0;i<max;i++){
    try{const value=await evaluate(expression);if(value)return value;}catch{}
    await sleep(100);
  }
  throw Error("BROWSER_EXPECTATION_TIMEOUT:"+expression);
}
try {
  let health=false;
  for(let i=0;i<90;i++){
    if(server.exitCode!==null)throw Error("LOOPBACK_PREVIEW_SERVER_EXITED");
    try{
      const res=await fetch(origin+"/_preview/health");
      health=res.ok&&(await res.json()).status==="GET_ONLY_REBASED_STATIC_PREVIEW";
      if(health)break;
    }catch{}
    await sleep(100);
  }
  assert.equal(health,true,"local only GET preview");
  browser=spawn(chrome,[
    "--no-sandbox","--headless","--disable-gpu",
    "--disable-dev-shm-usage","--remote-allow-origins=*",
    `--remote-debugging-port=${browserPort}`,
    `--user-data-dir=${profile}`,
    "--window-size=1365,1000","about:blank"
  ],{stdio:"ignore"});
  let addr;
  for(let i=0;i<90;i++){
    try {
      const list=await(await fetch(`http://127.0.0.1:${browserPort}/json/list`)).json();
      addr=list.find(x=>x.type==="page")?.webSocketDebuggerUrl;
      if(addr)break;
    }catch{}
    await sleep(100);
  }
  assert.ok(addr,"Chrome DevTools active");
  ws=new WebSocket(addr);
  await new Promise((resolve,reject)=>{
    ws.addEventListener("open",resolve,{once:true});
    ws.addEventListener("error",reject,{once:true});
  });
  ws.addEventListener("message",e=>{
    const m=JSON.parse(e.data);
    if(m.id&&pending.has(m.id)){
      const p=pending.get(m.id);pending.delete(m.id);
      m.error?p.reject(Error(JSON.stringify(m.error))):p.resolve(m);
    }
    if(m.method==="Runtime.exceptionThrown")
      exceptions.push(m.params?.exceptionDetails?.text||"runtime_exception");
    if(m.method==="Network.requestWillBeSent"){
      const req=m.params?.request;
      if(req?.method==="POST")posts.push(req.url);
      if(req?.url?.startsWith(origin)&&req.url.endsWith(".js"))
        scriptRequests.push(req.url.split("/").at(-1));
      if(req?.url?.startsWith("http")&&!req.url.startsWith(origin))
        externalRequests.push(req.url.slice(0,100));
    }
    if(m.method==="Network.responseReceived"){
      const res=m.params?.response;
      if(res?.url?.startsWith(origin)&&res.status>=400)
        badResponses.push({route:res.url.slice(origin.length,origin.length+90),status:res.status});
    }
  });
  await send("Runtime.enable");
  await send("Network.enable");
  await send("Page.enable");
  await send("Page.navigate",{url:origin+"/predictive-revenue"});
  const newHref="/commercial?entry=%2Fpredictive-revenue#commercial-enquiry";
  await until(`document.querySelector('a[href="${newHref}"]')!==null`);
  await until('document.querySelector("#deployment-request")!==null');
  await until('document.querySelector("#free-evidence-sample")!==null');
  await sleep(900);
  const initial=await evaluate(`(() => {
    const a=document.querySelector('a[href="${newHref}"]');
    return {
      label:a?.textContent?.trim(),
      href:a?.getAttribute("href"),
      consent:!!document.querySelector("#deployment-request input[type=checkbox][required]"),
      hydratedChunkLoaded:performance.getEntriesByType("resource").some(
        x=>x.name.includes("${pageChunk}")
      ),
      hasOriginalPreview:!!document.querySelector("#free-evidence-sample")
    };
  })()`);
  assert.equal(initial.href,newHref);
  assert.equal(initial.label,"Request a commercial proposal");
  assert.equal(initial.consent,true);
  assert.equal(initial.hydratedChunkLoaded,true);
  assert.equal(initial.hasOriginalPreview,true);
  await evaluate(`document.querySelector('a[href="${newHref}"]').click()`);
  await until('location.pathname==="/commercial"&&document.querySelector("#commercial-enquiry")!==null');
  await sleep(350);
  const after=await evaluate(`(() => ({
    pathname:location.pathname,
    entry:new URLSearchParams(location.search).get("entry"),
    hash:location.hash,
    consent:!!document.querySelector('#commercial-enquiry input[type="checkbox"][required]'),
    title:document.title
  }))()`);
  assert.equal(after.pathname,"/commercial");
  assert.equal(after.entry,"/predictive-revenue");
  assert.equal(after.hash,"#commercial-enquiry");
  assert.equal(after.consent,true);
  assert.equal(posts.length,0);
  assert.deepEqual(exceptions,[]);
  assert.deepEqual(badResponses,[]);
  assert.deepEqual(externalRequests,[]);
  assert.ok(scriptRequests.includes(pageChunk));
  console.log(JSON.stringify({
    status:"PRIVATE_REBASED_BROWSER_CTA_AND_CONSENT_PASS",
    original_saas_evidence_preview_visible:true,
    exact_new_cta:initial.href,
    html_hydration_page_chunk:pageChunk,
    buyer_initiated_commercial_route_reached:true,
    browser_entry_hint_read_as_unverified:after.entry,
    actual_consent_form_checkbox_rendered:true,
    newer_commercial_page_title:after.title,
    runtime_exceptions:0,requests_4xx_5xx:0,
    external_requests:0,form_posts:0,
    customer_created:false,publication_executed:false,
    browser_qa_duration_seconds:Math.round((Date.now()-start)/1000)
  },null,2));
} finally {
  if(ws)ws.close();
  if(browser)browser.kill("SIGTERM");
  server.kill("SIGTERM");
  await sleep(350);
  try{rmSync(profile,{recursive:true,force:true,maxRetries:10,retryDelay:200});}catch{}
}
