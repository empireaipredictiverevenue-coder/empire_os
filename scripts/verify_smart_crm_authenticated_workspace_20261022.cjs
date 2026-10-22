"use strict";
/* Synthetic localhost-only browser canary. No real tenant credentials, contacts,
   production CRM writes, outbound traffic, paid inference or payment actions. */
const fs=require("fs");
const path=require("path");
const http=require("http");
const assert=require("node:assert/strict");
const puppeteer=require("/home/ubuntu/.nvm/versions/node/v22.23.2/lib/node_modules/@wonderwhy-er/desktop-commander/node_modules/puppeteer");
const root="/home/ubuntu/empire_worktrees/smart_crm_authenticated_workspace_20261022/release_candidates/smart_crm_authenticated";
const html=fs.readFileSync(path.join(root,"revenue_crm_action_console.html"));
const js=fs.readFileSync(path.join(root,"revenue_crm_action_console.js"));
const bearer="synthetic-test-only-"+("x".repeat(162));
const allowed=new Set(["ready","running","review","blocked","done","failed"]);
const sources=[];
const board={schema_version:"empire.departments.kanban.v1",
  source:"canonical_department_work_queue",tenant_scope:"explicit_tenant",
  read_only:true,execution_authority:"none",lanes:{}};
for(const name of allowed){
 board.lanes[name]={total:0,cards:[],truncated:false};
}
board.lanes.ready={total:1,truncated:false,cards:[{
 work_id:"synthetic-task-readonly",goal_key:"Inspect tenant CRM",
 department_keys:["sales"],target_component:"crm",priority:9,
 status:"READY",has_result_evidence:false,has_active_lease:false,
}]};
let forged=false;
let rejectedProtected=0;
const server=http.createServer((req,res)=>{
 const u=new URL(req.url,"http://127.0.0.1");
 const response=(code,obj)=>{
  res.writeHead(code,{"Content-Type":"application/json","Cache-Control":"no-store"});
  res.end(JSON.stringify(obj));
 };
 if(u.pathname==="/v1/revenue-crm/review-console"&&req.method==="GET"){
  res.writeHead(200,{"Content-Type":"text/html","Cache-Control":"no-store"});
  return res.end(html);
 }
 if(u.pathname==="/v1/revenue-crm/review-console.js"&&req.method==="GET"){
  res.writeHead(200,{"Content-Type":"application/javascript","Cache-Control":"no-store"});
  return res.end(js);
 }
 if(u.pathname==="/v1/revenue-crm/auth/login"&&req.method==="POST"){
  return response(200,{
    token_type:"Bearer",access_token:bearer,scope:"crm:read",expires_in:180,
  });
 }
 const auth=req.headers.authorization==="Bearer "+bearer;
 if(!auth){rejectedProtected++;return response(401,{detail:"authenticated_crm_scope_required"});}
 sources.push({path:u.pathname,method:req.method,auth});
 if(u.pathname==="/v1/revenue-crm/prospects"){
  return response(200,{
    source:"canonical_revenue_crm_repository",read_only:true,count:1,
    limit:40,items:[{prospect_id:"synthetic-prospect-1",business_name:"Synthetic Agency",
      niche:"B2B",prospect_status:"review"}],
  });
 }
 if(u.pathname==="/v1/revenue-crm/prospects/synthetic-prospect-1/commercial-action-review"){
  return response(200,{
    schema_version:"empire.revenue_crm_commercial_action_review.v1",
    mode:"OBSERVE",execution_authority:"none",send_authorized:false,
    contact_hold:false,priority_rank:4,status:"INTERNAL_REVIEW_ONLY",
    recommended_internal_review:"REVIEW_SOURCE_GAPS",
    crm_stage_action:"research",unverified_reply_signals:[],
    source_proof_blockers_present:true,channel_evidence_status:"UNVERIFIED",
    canonical_evidence_refs:[],
  });
 }
 if(u.pathname==="/v1/revenue-crm/buyers"){
  return response(200,{
    source:"canonical_revenue_crm_repository",read_only:true,count:1,
    items:[{business_name:"Synthetic Buyer Org"}],
  });
 }
 if(u.pathname==="/v1/revenue-crm/department-kanban"){
  return response(200,forged?{...board,tenant_scope:"unbound"}:board);
 }
 return response(503,{detail:"original_source_fixture_not_available"});
});
async function main(){
 await new Promise(ok=>server.listen(0,"127.0.0.1",ok));
 const origin="http://127.0.0.1:"+server.address().port;
 const browser=await puppeteer.launch({
   executablePath:"/home/ubuntu/.cache/puppeteer/chrome/linux-153.0.8010.36/chrome-linux64/chrome",
   headless:true,args:["--no-sandbox","--disable-gpu","--disable-background-networking"],
   protocolTimeout:60000,
 });
 const states=[];
 try{
  const page=await browser.newPage();
  await page.setViewport({width:390,height:820});
  await page.setRequestInterception(true);
  page.on("request",r=>{
   if(r.url().startsWith(origin+"/"))return r.continue();
   return r.abort();
  });
  const errors=[];
  page.on("pageerror",e=>errors.push(e.message));
  const unauth=await page.goto(origin+"/v1/revenue-crm/review-console",{waitUntil:"domcontentloaded"});
  assert.equal(unauth.status(),200);
  await page.waitForSelector("#login-form");
  assert.equal(await page.$eval("#workspace-nav",e=>e.hidden),true);
  assert.equal(await page.$eval("#review-panel",e=>e.hidden),true);
  const unauthorized=await page.evaluate(async()=>{
    const r=await fetch("/v1/revenue-crm/department-kanban");
    return r.status;
  });
  assert.equal(unauthorized,401);
  states.push("ANONYMOUS_KANBAN_401");
  await page.type("#account","synthetic@example.invalid");
  await page.type("#password","not-a-live-password");
  await page.type("#tenant","00000000-0000-4000-8000-000000000001");
  await page.click("#sign-in");
  await page.waitForFunction(()=>document.querySelector("#review-panel")?.hidden===false);
  await page.waitForFunction(()=>document.querySelector("#kanban-status")?.textContent?.includes("tenant-bound task previews"));
  await page.waitForFunction(()=>document.querySelector("#buyer-review-status")?.textContent?.includes("tenant buyer rows returned"));
  await page.waitForFunction(()=>document.querySelector("#sales-actions-workspace-status")?.textContent?.includes("internal action reviews"));
  const signed=await page.evaluate(()=>({
    navHidden:document.querySelector("#workspace-nav").hidden,
    buyer:document.querySelector("#buyer-results").innerText,
    opportunities:document.querySelector("#results").innerText,
    agent:document.querySelector("#kanban-results").innerText,
    revenue:document.querySelector("#revenue-evidence-status").innerText,
    sales:document.querySelector("#sales-actions-workspace-status").innerText,
    nav:[...document.querySelectorAll(".workspace-nav a")].map(a=>a.innerText),
    localStorageLength:localStorage.length,
    sessionStorageLength:sessionStorage.length,
    overflow:document.documentElement.scrollWidth>innerWidth+3,
  }));
  assert.equal(signed.navHidden,false);
  assert.match(signed.buyer,/Synthetic Buyer Org/);
  assert.match(signed.opportunities,/Synthetic Agency/);
  assert.match(signed.agent,/Inspect tenant CRM/);
  assert.match(signed.revenue,/not connected/);
  assert.match(signed.sales,/1 signed-tenant internal action reviews/);
  assert.deepEqual(signed.nav,["Contacts","Opportunities","Sales Actions","Conversations","Revenue","Startup & agents"]);
  assert.equal(signed.localStorageLength,0);
  assert.equal(signed.sessionStorageLength,0);
  assert.equal(signed.overflow,false);
  states.push("SIGNED_TENANT_DATA_RENDERED_IN_MEMORY");
  await page.evaluate(()=>window.scrollTo(0,0));
  const screenshot="/home/ubuntu/empire_releases/smart_crm_authenticated_workspace_20261022/mobile-390-synthetic-preview.png";
  await page.screenshot({path:screenshot,fullPage:false});
  await page.setViewport({width:1440,height:900});
  const desktop=await page.evaluate(()=>({
    overflow:document.documentElement.scrollWidth>innerWidth+3,
    navVisible:!document.querySelector("#workspace-nav").hidden,
    currentWidth:innerWidth,
  }));
  assert.equal(desktop.currentWidth,1440);
  assert.equal(desktop.overflow,false);
  assert.equal(desktop.navVisible,true);
  states.push("MOBILE_AND_DESKTOP_AUTHENTICATED_LAYOUT");
  forged=true;
  await page.$eval("#refresh",el=>el.click());
  await page.waitForFunction(()=>document.querySelector("#kanban-status")?.textContent?.includes("no agent work promoted"));
  const forgery=await page.$eval("#kanban-results",e=>e.innerText);
  assert.equal(forgery,"");
  states.push("FORGED_TENANT_BOARD_REJECTED");
  await page.click("#sign-out");
  const logout=await page.evaluate(()=>({
    nav:document.querySelector("#workspace-nav").hidden,
    login:document.querySelector("#login-panel").hidden,
    review:document.querySelector("#review-panel").hidden,
    buyer:document.querySelector("#buyer-results").innerText,
    kanban:document.querySelector("#kanban-results").innerText,
    password:document.querySelector("#password").value,
  }));
  assert.equal(logout.nav,true);
  assert.equal(logout.login,false);
  assert.equal(logout.review,true);
  assert.equal(logout.buyer,"");
  assert.equal(logout.kanban,"");
  assert.equal(logout.password,"");
  assert.deepEqual(errors,[]);
  states.push("LOGOUT_CLEARS_TENANT_CONTENT");
  assert.ok(rejectedProtected>0);
  assert.ok(sources.some(s=>s.path==="/v1/revenue-crm/buyers"&&s.auth));
  assert.ok(sources.some(s=>s.path==="/v1/revenue-crm/prospects"&&s.auth));
  assert.ok(sources.some(s=>s.path==="/v1/revenue-crm/department-kanban"&&s.auth));
  console.log(JSON.stringify({
    status:"SYNTHETIC_SIGNED_TENANT_BROWSER_PASS",
    checks:states,
    source_endpoint_count:sources.length,
    anonymous_401_events:rejectedProtected,
    browser_page_errors:errors.length,
    width:390,
    public_site_changed:false,
    existing_crm_service_changed:false,
    real_credentials_used:false,
    genuine_customer_records_read:false,
    execution_authority:"NONE",
  }));
 }finally{
  await browser.close();
  await new Promise(ok=>server.close(ok));
 }
}
main().catch(e=>{console.error("SYNTHETIC_CRM_BROWSER_HOLD",String(e.message).slice(0,190));server.close();process.exitCode=2;});
