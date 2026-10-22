"use strict";
// Private Chromium smoke on the two-page mixed-generation overlay.
// GET-only localhost files. No money, email, form submission, external browser requests.
const fs=require("fs");
const path=require("path");
const http=require("http");
const crypto=require("crypto");
const puppeteer=require("/home/ubuntu/.nvm/versions/node/v22.23.2/lib/node_modules/@wonderwhy-er/desktop-commander/node_modules/puppeteer");
const root="/home/ubuntu/empire_releases/seo_predictive_roofing_public_pilot_20261022/overlay-79dd421bb";
const base=path.join(root,"out");
const receiptPath=path.join(root,"RELEASE_CANDIDATE_RECEIPT.json");
const evidencePath=path.join(root,"BROWSER_CANDIDATE_QA.json");
const executable="/home/ubuntu/.cache/puppeteer/chrome/linux-153.0.8010.36/chrome-linux64/chrome";
const target=[
 {url:"/predictive-revenue",phrase:"How do you test a revenue forecast against actual results?"},
 {url:"/industries/roofing",phrase:"How to audit a roofing call from click to settlement"}
];
const widths=[320,390,820,1440];
const digest=(p)=>crypto.createHash("sha256").update(fs.readFileSync(p)).digest("hex");
if(!fs.existsSync(receiptPath)||!fs.existsSync(executable)||fs.existsSync(evidencePath))
 throw Error("MISSING_PRECHECK_OR_EVIDENCE_ALREADY_WRITTEN");
const rec=JSON.parse(fs.readFileSync(receiptPath,"utf8"));
if(rec.status!=="PRIVATE_TWO_PAGE_OVERLAY_BUILT_NOT_PUBLISHED" ||rec.approved_for_public_release!==false
 ||Object.keys(rec.private_candidate_sha256||{}).length!==653)throw Error("INVALID_SOURCE_RECEIPT");
for(const rel of ["predictive-revenue.html","predictive-revenue.txt","industries/roofing.html","industries/roofing.txt"])
 if(digest(path.join(base,rel))!==rec.replaced_path_sha256_after[rel])throw Error("SOURCE_BYTES_CHANGED");
const mime={".html":"text/html",".js":"application/javascript",".css":"text/css",
 ".svg":"image/svg+xml",".png":"image/png",".jpg":"image/jpeg",".webp":"image/webp",
 ".woff2":"font/woff2",".txt":"text/plain",".ico":"image/x-icon"};
const report={schema_version:"empire.search.private_public_seo_browser_review.v1",
 status:"CANDIDATE_BROWSER_RUNNING",source_commit:"79dd421bb",widths,
 route_checks:[],navigation_checks:[],missing_local_assets:[],page_errors:[],
 screenshots:[],blocked_external:0,blocked_non_get:0,form_submissions:0,
 public_website_modified:false,public_release_authorized:false,
 execution_authority:"NONE"};
const server=http.createServer((req,res)=>{
 if(req.method!=="GET"){report.blocked_non_get++;return res.writeHead(405).end();}
 const u=new URL(req.url,"http://127.0.0.1");
 if(u.pathname.startsWith("/v1/")){
   res.writeHead(503,{"Content-Type":"application/json","Cache-Control":"no-store"});
   return res.end('{"status":"LOCAL_PREVIEW_NO_BACKEND"}');
 }
 let file=path.resolve(base,"."+u.pathname);
 if(!file.startsWith(base+path.sep)&&file!==base)return res.writeHead(403).end();
 if(fs.existsSync(file+".html"))file+=".html";
 if(fs.existsSync(file)&&fs.statSync(file).isDirectory())file=path.join(file,"index.html");
 if(!fs.existsSync(file)||!fs.statSync(file).isFile())return res.writeHead(404).end();
 res.writeHead(200,{"Content-Type":mime[path.extname(file)]||"application/octet-stream","Cache-Control":"no-store"});
 fs.createReadStream(file).pipe(res);
});
(async()=>{
 await new Promise(ok=>server.listen(0,"127.0.0.1",ok));
 const origin="http://127.0.0.1:"+server.address().port;
 const browser=await puppeteer.launch({executablePath:executable,headless:true,
   args:["--no-sandbox","--disable-gpu","--disable-background-networking"],protocolTimeout:60000});
 try {
  for(const width of widths){
   const page=await browser.newPage();
   await page.setViewport({width,height:880,deviceScaleFactor:1});
   await page.setRequestInterception(true);
   page.on("request",r=>{
     if(r.url().startsWith(origin+"/")&&r.method()==="GET")return r.continue();
     if(r.method()!=="GET")report.blocked_non_get++;
     else report.blocked_external++;
     return r.abort();
   });
   page.on("pageerror",e=>report.page_errors.push({width,error:String(e.message).slice(0,90)}));
   page.on("response",res=>{
     if(!res.url().startsWith(origin+"/")||res.status()<400)return;
     const p=new URL(res.url()).pathname;
     if(p.startsWith("/v1/")||p==="/favicon.ico")return;
     report.missing_local_assets.push({width,path:p,http_status:res.status()});
   });
   for(const item of target){
     const response=await page.goto(origin+item.url,{waitUntil:"domcontentloaded",timeout:17000});
     await new Promise(ok=>setTimeout(ok,550));
     const visible=await page.evaluate((phrase,url)=>{
       const t=document.body.innerText||"";
       const links=[...document.querySelectorAll('a[href="/commercial"]')];
       return {hasText:t.includes(phrase),h1:document.querySelectorAll("h1").length,
         main:document.querySelectorAll("main").length,
         canonical:document.querySelector('link[rel="canonical"]')?.href||"",
         overflow:document.documentElement.scrollWidth>innerWidth+3,
         scrollWidth:document.documentElement.scrollWidth,viewport:innerWidth,
         visibleCTA:links.some(a=>{const r=a.getBoundingClientRect();const s=getComputedStyle(a);
           return r.width>0&&r.height>0&&s.display!=="none"&&s.visibility!=="hidden";}),
         formCount:document.querySelectorAll("form").length};
     },item.phrase,item.url);
     report.route_checks.push({width,url:item.url,http_status:response.status(),...visible});
     if(width===390){
       const name=item.url==="/predictive-revenue"?"predictive":"roofing";
       const screenshot=path.join(root,"BROWSER_"+name+"_390.png");
       await page.screenshot({path:screenshot,fullPage:false});
       report.screenshots.push({url:item.url,width,sha256:digest(screenshot),path:screenshot});
     }
     if(response.status()!==200||!visible.hasText||visible.h1!==1||visible.main!==1
        ||visible.canonical!=="https://empire-ai.co.uk"+item.url
        ||visible.overflow||!visible.visibleCTA)
        throw Error("RENDER_MOBILE_OR_SEO_HOLD_"+width+"_"+item.url);
   }
   if(width===390||width===1440){
      await page.goto(origin+"/predictive-revenue",{waitUntil:"domcontentloaded",timeout:17000});
      const clicked=await page.evaluate(()=>{
        const e=[...document.querySelectorAll('a[href="/commercial"]')].find(a=>{
         const r=a.getBoundingClientRect();const s=getComputedStyle(a);
         return r.width>0&&r.height>0&&s.visibility!=="hidden"&&s.display!=="none";
        });
        if(!e)return false;
        e.click();return true;
      });
      await new Promise(ok=>setTimeout(ok,900));
      const destination=new URL(page.url()).pathname;
      report.navigation_checks.push({width,clicked,destination,
                                     passed:clicked&&destination==="/commercial"});
      if(!clicked||destination!=="/commercial")throw Error("MIXED_NAVIGATION_HOLD_"+width);
   }
   await page.close();
  }
  if(report.missing_local_assets.length||report.page_errors.length)
    throw Error("CLIENT_ERRORS_OR_MISSING_ASSETS");
  report.status="PRIVATE_DESKTOP_MOBILE_BROWSER_SMOKE_PASS_NOT_PUBLISHED";
 } finally {
   await browser.close();
   await new Promise(ok=>server.close(ok));
 }
 fs.writeFileSync(evidencePath,JSON.stringify(report,null,2)+"\n",{flag:"wx",mode:0o600});
 console.log(JSON.stringify({status:report.status,checked:report.route_checks.length,
  navigation:report.navigation_checks.length,missing_assets:report.missing_local_assets.length,
  page_errors:report.page_errors.length,external_blocked:report.blocked_external,
  non_get_blocked:report.blocked_non_get,receipt_sha256:digest(evidencePath),
  public_site_modified:false}));
})().catch(e=>{
 report.status="PRIVATE_BROWSER_QA_HELD";
 report.failure_class="BROWSER_QA_FAILED";
 try{fs.writeFileSync(evidencePath,JSON.stringify(report,null,2)+"\n",{flag:"wx",mode:0o600});}catch{}
 console.error("BROWSER_QA_HELD",String(e.message).slice(0,180));
 server.close();
 process.exitCode=2;
});
