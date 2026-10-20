// Browser smoke for PRIVATE merged static release, no live HTTP or buyer POST.
// Checks both the latest Next pages and preserved old public-only routes.
"use strict";
const fs = require("fs");
const path = require("path");
const http = require("http");
const puppeteer = require("/home/ubuntu/.nvm/versions/node/v22.23.2/lib/node_modules/@wonderwhy-er/desktop-commander/node_modules/puppeteer");
const parent = "/home/ubuntu/empire_releases/flagship_checkout_union_20261020";
const baseDir = path.resolve(parent, "out");
const receiptPath = path.resolve(parent, "RELEASE_CANDIDATE_RECEIPT.json");
const reportPath = path.resolve(parent, "BROWSER_ROUTE_EVIDENCE.json");
const allowedReadOnlyPublicGet = new Set(["/v1/checkout/catalog","/v1/checkout/exchange/tiers","/v1/checkout/brokerage/premium-discovery"]);
const mime = {".html":"text/html", ".js":"application/javascript", ".css":"text/css", ".svg":"image/svg+xml", ".txt":"text/plain", ".webp":"image/webp", ".png":"image/png", ".jpg":"image/jpeg", ".jpeg":"image/jpeg", ".woff2":"font/woff2", ".avif":"image/avif"};
const fixture = {status:"FOUNDER_LED_ENQUIRY_AVAILABLE",offers:[
  {product_code:"competitor_search_gap",name:"Competitor search gap"},
  {product_code:"search_opportunity_map",name:"Search opportunity map"},
  {product_code:"technical_search_audit",name:"Technical search audit"},
  {product_code:"solar_opportunity_map_us",name:"US solar opportunity map"}
]};
const checked = [
  {url:"/", label:"cinematic-home", required:"Empire"},
  {url:"/buy", label:"new-buyer-checkout", required:"REQUEST A PROPOSAL"},
  {url:"/commercial", label:"new-commercial-enquiry", required:"Empire"},
  {url:"/about", label:"preserved-about", required:"Empire"},
  {url:"/insights/revenue-opportunity-assessment",label:"preserved-insight",required:""},
  {url:"/roofing/installation-checklist",label:"new-roofing-guide",required:""},
];
const output = {
  schema_version:"empire.website.flagship_checkout_union_browser.v1",
  routes:[],navigation:[],missing_local_assets:[],browser_page_errors:[],
  read_only_existing_public_api_gets:[],
  external_requests_blocked:0,non_get_requests_blocked:0,
  checkout_posts_submitted:0,public_site_modified:false,
  release_approved:false,payment_execution:false,
};
if(!fs.existsSync(receiptPath) || !fs.existsSync(baseDir))throw Error("CANDIDATE_ABSENT");
const receipt=JSON.parse(fs.readFileSync(receiptPath,"utf8"));
if(receipt.status!=="PRIVATE_MIXED_GENERATION_STATIC_CANDIDATE_ASSEMBLED" ||
   receipt.new_public_release_authorized!==false ||
   Object.keys(receipt.static_file_sha256||{}).length!==632)throw Error("ORIGINAL_UNION_RECEIPT_UNTRUSTED");
const server=http.createServer((req,res)=>{
  if(req.method!=="GET"){output.non_get_requests_blocked++;res.writeHead(405);return res.end();}
  const url=new URL(req.url,"http://localhost");
  if(url.pathname==="/v1/checkout/commercial/offers"){res.setHeader("Content-Type","application/json");return res.end(JSON.stringify(fixture));}
  if(allowedReadOnlyPublicGet.has(url.pathname)){
    const upstream=http.request({
      hostname:"127.0.0.1",port:80,path:url.pathname,method:"GET",
      headers:{Host:"empire-ai.co.uk",Accept:"application/json"},timeout:3500
    },u=>{
      let received=0;const buffers=[];
      u.on("data",chunk=>{
        received+=chunk.length;
        if(received>16000){u.destroy();return;}
        buffers.push(chunk);
      });
      u.on("end",()=>{
        const content=String(u.headers["content-type"]||"");
        const valid=u.statusCode===200&&content.startsWith("application/json")&&received<=16000;
        output.read_only_existing_public_api_gets.push({route:url.pathname,status:u.statusCode,valid});
        res.writeHead(valid?200:502,{"Content-Type":"application/json","Cache-Control":"no-store"});
        res.end(valid?Buffer.concat(buffers):'{"status":"SOURCE_HOLD"}');
      });
      u.on("error",()=>{if(!res.headersSent){res.writeHead(502);res.end();}});
    });
    upstream.on("timeout",()=>upstream.destroy());
    upstream.on("error",()=>{if(!res.headersSent){res.writeHead(502);res.end();}});
    upstream.end();return;
  }
  let file=path.resolve(baseDir,"."+url.pathname);
  if(!file.startsWith(baseDir+path.sep) && file!==baseDir){res.writeHead(403);return res.end();}
  if(fs.existsSync(file+".html"))file+=".html";
  if(fs.existsSync(file)&&fs.statSync(file).isDirectory())file=path.join(file,"index.html");
  if(!fs.existsSync(file)||!fs.statSync(file).isFile()){res.writeHead(404);return res.end();}
  res.setHeader("Content-Type",mime[path.extname(file)]||"application/octet-stream");
  res.setHeader("Cache-Control","no-store");
  fs.createReadStream(file).pipe(res);
});
(async()=>{
  await new Promise(resolve=>server.listen(0,"127.0.0.1",resolve));
  const origin="http://127.0.0.1:"+server.address().port;
  const browser=await puppeteer.launch({
    executablePath:"/home/ubuntu/.cache/puppeteer/chrome/linux-153.0.8010.36/chrome-linux64/chrome",
    headless:true,args:["--no-sandbox","--disable-gpu","--disable-background-networking"],protocolTimeout:60000
  });
  try{
    for(const width of [1440,390]){
      const page=await browser.newPage();
      await page.setViewport({width,height:850});
      await page.setRequestInterception(true);
      page.on("request",r=>{
        if(r.url().startsWith(origin+"/") && r.method()==="GET")return r.continue();
        output.external_requests_blocked++;
        return r.abort();
      });
      page.on("pageerror",e=>output.browser_page_errors.push({width,kind:"BROWSER_PAGE_ERROR",summary:String(e.message).slice(0,80)}));
      page.on("response",response=>{
        if(response.url().startsWith(origin+"/") &&
           response.status()>=400 &&
           response.request().method()==="GET"){
          const pathOnly=new URL(response.url()).pathname;
          if(pathOnly!=="/favicon.ico")output.missing_local_assets.push({width,route:pathOnly,status:response.status()});
        }
      });
      for(const spec of checked){
        try{
          const response=await page.goto(origin+spec.url,{waitUntil:"domcontentloaded",timeout:15000});
          await new Promise(resolve=>setTimeout(resolve,800));
          const found=await page.evaluate(required=>({
            hasMain:!!document.querySelector("main, h1"),
            overflow:document.documentElement.scrollWidth>innerWidth+3,
            wordMatches:!required || document.body.textContent.includes(required),
            forms:document.querySelectorAll("form").length,
          }),spec.required);
          output.routes.push({
            width,route:spec.label,status:response.status(),hasMain:found.hasMain,
            noHorizontalOverflow:!found.overflow,expectedContent:found.wordMatches,
            passed:response.status()===200&&found.hasMain&&!found.overflow&&found.wordMatches,
          });
        }catch(e){
          output.routes.push({width,route:spec.label,passed:false,reason:"ROUTE_BROWSER_RUNTIME_HOLD"});
        }
      }
      for(const route of [
        {from:"/buy", link:'a[href^="/commercial"]', to:"/commercial"},
        {from:"/about", link:'a[href^="/buy"]', to:"/buy"},
      ]){
        let success=false, reason="UNTESTED";
        try{
          await page.goto(origin+route.from,{waitUntil:"domcontentloaded",timeout:15000});
          const clicked=await page.evaluate(selector=>{
            const matching=[...document.querySelectorAll(selector)];
            const visible=matching.find(a=>{
              const r=a.getBoundingClientRect(),style=getComputedStyle(a);
              return r.width>0&&r.height>0&&style.display!=="none"
                &&style.visibility!=="hidden";
            });
            if(!visible)return false;
            visible.click();
            return true;
          },route.link);
          reason=clicked?"NAVIGATION_TIMEOUT":"NO_VISIBLE_MATCHING_LINK";
          if(clicked){
            await page.waitForFunction(
              expected=>window.location.pathname===expected,
              {timeout:8000},route.to
            );
            success=true;reason="PASS";
          }
        }catch(e){reason="NAVIGATION_OR_BROWSER_EXCEPTION";}
        output.navigation.push({width,from:route.from,to:route.to,passed:success,reason});
      }
      await page.close();
    }
  }finally{await browser.close();server.close();}
})().catch(e=>{output.browser_page_errors.push({kind:"BROWSER_HARNESS_FAILURE",summary:String(e.message).slice(0,100)});process.exitCode=2;})
.finally(()=>{
  output.status=(
    output.routes.length===checked.length*2 &&
    output.routes.every(x=>x.passed) &&
    output.navigation.length===4 && output.navigation.every(x=>x.passed) &&
    output.browser_page_errors.length===0 &&
    output.missing_local_assets.length===0 &&
    output.read_only_existing_public_api_gets.length>=6 &&
    output.read_only_existing_public_api_gets.every(x=>x.valid) &&
    output.non_get_requests_blocked===0
  )?"PRIVATE_UNION_BROWSER_TECHNICAL_PASS":"PRIVATE_UNION_BROWSER_RELEASE_REVIEW_HOLD";
  fs.writeFileSync(reportPath,JSON.stringify(output,null,2)+"\n");
  console.log(JSON.stringify({
    status:output.status,routesChecked:output.routes.length,
    failedRoutes:output.routes.filter(x=>!x.passed).map(x=>x.route+"@"+x.width),
    navigationChecked:output.navigation.length,
    failedNavigation:output.navigation.filter(x=>!x.passed).map(x=>x.from+"=>"+x.to+"@"+x.width),
    browserErrors:output.browser_page_errors.length,
    missingAssets:output.missing_local_assets.length,
    externalBlocked:output.external_requests_blocked,
    buyerPosts:output.checkout_posts_submitted,
    releaseApproved:false
  }));
  if(output.status!=="PRIVATE_UNION_BROWSER_TECHNICAL_PASS")process.exitCode=2;
});
