"use strict";
const http=require("node:http"), fs=require("node:fs"), path=require("node:path");
const {once}=require("node:events");
const puppeteer=require("/home/ubuntu/.nvm/versions/node/v22.23.2/lib/node_modules/@wonderwhy-er/desktop-commander/node_modules/puppeteer");
const LIVE="/srv/empire_os/apps/empire-public-site/out";
const STAGE="/home/ubuntu/empire_staging/agency_surgical_live_pages_20261020";
const PORT=18893;
let posts=0, routedGet=0;
const mime={".html":"text/html; charset=utf-8",".js":"text/javascript; charset=utf-8",".css":"text/css; charset=utf-8",".png":"image/png",".svg":"image/svg+xml",".webp":"image/webp",".woff2":"font/woff2"};
const server=http.createServer(async (req,res)=>{
  try {
    if (!["HEAD","GET"].includes(req.method)) {posts++;res.writeHead(405).end();return;}
    const uri=new URL(req.url,"http://127.0.0.1");
    if(uri.pathname.startsWith("/v1/") || uri.pathname.startsWith("/api/")) {
      routedGet++;
      const response=await fetch("http://127.0.0.1"+uri.pathname+uri.search,{headers:{Host:"empire-ai.co.uk"},signal:AbortSignal.timeout(6000)});
      res.writeHead(response.status,{"Content-Type":response.headers.get("content-type")||"application/json","Cache-Control":"no-store"});
      res.end(Buffer.from(await response.arrayBuffer()));return;
    }
    const relative=(uri.pathname==="/"?"buy":uri.pathname.replace(/^\//,""));
    const fileName=relative.includes(".")?relative:relative+".html";
    if(fileName.includes("..")){res.writeHead(404).end();return;}
    let file=path.join(STAGE,fileName);
    if(!fs.existsSync(file)) file=path.join(LIVE,fileName);
    if(!fs.existsSync(file) || !fs.statSync(file).isFile()){res.writeHead(404).end();return;}
    res.writeHead(200,{"Content-Type":mime[path.extname(file)]||"application/octet-stream","Cache-Control":"no-store"});
    fs.createReadStream(file).pipe(res);
  }catch(e){res.writeHead(500).end("local GET smoke unavailable");}
});
(async()=>{
  server.listen(PORT,"127.0.0.1");await once(server,"listening");
  let browser;
  try{
    browser=await puppeteer.launch({executablePath:"/home/ubuntu/.cache/puppeteer/chrome/linux-153.0.8010.36/chrome-linux64/chrome",headless:true,args:["--no-sandbox","--disable-dev-shm-usage","--disable-gpu"]});
    const page=await browser.newPage();
    const errs=[];
    page.on("pageerror",e=>errs.push(String(e.message).slice(0,180)));
    await page.goto("http://127.0.0.1:"+PORT+"/buy",{waitUntil:"networkidle2",timeout:30000});
    const alternative=()=>page.$eval("#empire-agency-proposal-alternative",e=>e.getAttribute("href"));
    await page.waitForSelector("#empire-agency-proposal-alternative",{timeout:15000});
    const initial=await alternative();
    await page.evaluate(()=>{
      const target=[...document.querySelectorAll('button[type=button]')].find(e=>e.querySelector("strong")?.textContent.trim()==="Search Opportunity Map");
      if(!target)throw Error("approved second product option not rendered");
      target.click();
    });
    await page.waitForFunction(()=>document.querySelector("#empire-agency-proposal-alternative")?.getAttribute("href")==="/commercial?product=search_opportunity_map#commercial-enquiry",{timeout:10000});
    await page.evaluate(()=>{
      const target=[...document.querySelectorAll('button[type=button]')].find(e=>e.querySelector("strong")?.textContent.trim()==="Competitor Search Gap");
      target.click();
    });
    await page.waitForFunction(()=>document.querySelector("#empire-agency-proposal-alternative")?.getAttribute("href")==="/commercial?product=competitor_search_gap#commercial-enquiry",{timeout:10000});
    const chosen=await alternative();
    const paymentKept=await page.evaluate(()=>[...document.querySelectorAll('button')].some(e=>e.textContent.includes('CREATE PAYMENT REQUEST')));
    await page.goto("http://127.0.0.1:"+PORT+chosen,{waitUntil:"networkidle2",timeout:30000});
    await page.waitForFunction(()=>document.querySelector('#commercial-enquiry select')?.value==="competitor_search_gap",{timeout:12000});
    const good=await page.$eval('#commercial-enquiry select',e=>({code:e.value,label:e.selectedOptions[0]?.textContent}));
    const brokeragePreserved=await page.evaluate(()=>!!document.getElementById('premium-brokerage'));
    await page.goto("http://127.0.0.1:"+PORT+"/commercial?product=bogus_product#commercial-enquiry",{waitUntil:"networkidle2",timeout:30000});
    await page.waitForFunction(()=>document.querySelector('#commercial-enquiry select')?.value==="consultancy_opportunity_assessment",{timeout:12000});
    const bad=await page.$eval("#commercial-enquiry select",e=>e.value);
    const report={status:"LIVE_STATIC_SURGICAL_PREVIEW_BROWSER_PASS",initial,chosen,form_selected:good,unapproved_product_fallback:bad,brokerage_preserved:brokeragePreserved,payment_form_preserved:paymentKept,http_post_requests:posts,read_only_api_get_requests:routedGet,page_errors:errs.slice(0,6)};
    console.log(JSON.stringify(report,null,2));
    if(chosen!=="/commercial?product=competitor_search_gap#commercial-enquiry"||good.code!=="competitor_search_gap"||!brokeragePreserved||!paymentKept||posts!==0)throw Error("live snapshot parity smoke failed");
  }finally{if(browser)await browser.close();server.close();}
})().catch(e=>{console.error("SMOKE_HELD "+e.message);server.close();process.exitCode=3;});
