// Synthetic, isolated, GET-only browser verification of native buyer proposal.
const fs = require("fs");
const path = require("path");
const http = require("http");
const puppeteer = require("/home/ubuntu/.nvm/versions/node/v22.23.2/lib/node_modules/@wonderwhy-er/desktop-commander/node_modules/puppeteer");
const baseDir = path.resolve(process.cwd(), "apps/empire-public-site/out");
const output = path.resolve(process.cwd(), "docs/evidence/flagship-checkout-browser-20261020");
fs.mkdirSync(output, {recursive:true});
const fixture = {status:"FOUNDER_LED_ENQUIRY_AVAILABLE", offers:[
  {product_code:"competitor_search_gap",name:"Competitor search gap"},
  {product_code:"search_opportunity_map",name:"Search opportunity map"},
  {product_code:"technical_search_audit",name:"Technical search audit"},
  {product_code:"solar_opportunity_map_us",name:"US solar opportunity map"},
]};
const mime = {".html":"text/html",".js":"application/javascript",".css":"text/css",".webp":"image/webp",".png":"image/png",".woff2":"font/woff2",".svg":"image/svg+xml",".jpg":"image/jpeg"};
const observed = {pages:[],blockedPostRequests:0,externalRequestsBlocked:0,pageErrors:[],source:"ISOLATED_BUILD_AND_SYNTHETIC_OFFERS",publicPostSubmitted:false};
const server = http.createServer((req,res)=>{
  if(req.method!=="GET"){observed.blockedPostRequests++;res.writeHead(405);return res.end();}
  const u=new URL(req.url,"http://localhost");
  if(u.pathname==="/v1/checkout/commercial/offers"){
    res.setHeader("Content-Type","application/json");
    return res.end(JSON.stringify(fixture));
  }
  let file=path.resolve(baseDir, "."+u.pathname);
  if(!file.startsWith(baseDir+path.sep)&&file!==baseDir){res.writeHead(403);return res.end();}
  if(fs.existsSync(file+".html"))file+=".html";
  if(fs.existsSync(file)&&fs.statSync(file).isDirectory())file=path.join(file,"index.html");
  if(!fs.existsSync(file)||!fs.statSync(file).isFile()){res.writeHead(404);return res.end();}
  res.setHeader("Content-Type",mime[path.extname(file)]||"application/octet-stream");
  fs.createReadStream(file).pipe(res);
});
const verify=(name,pass,extra={})=>{observed.pages.push({name,pass,...extra});console.log(name,pass,JSON.stringify(extra));};
(async()=>{
  await new Promise(resolve=>server.listen(0,"127.0.0.1",resolve));
  const base="http://127.0.0.1:"+server.address().port;
  const browser=await puppeteer.launch({executablePath:"/home/ubuntu/.cache/puppeteer/chrome/linux-153.0.8010.36/chrome-linux64/chrome",headless:true,args:["--no-sandbox","--disable-gpu","--disable-background-networking"],protocolTimeout:60000});
  try {
    const page=await browser.newPage();
    await page.setRequestInterception(true);
    page.on("request",req=>{
      if(req.url().startsWith(base+"/") && req.method()==="GET")return req.continue();
      observed.externalRequestsBlocked++;
      req.abort();
    });
    page.on("pageerror",err=>observed.pageErrors.push(err.message));
    for(const width of [1440,390]){
      await page.setViewport({width,height:900});
      await page.goto(base+"/buy",{waitUntil:"networkidle2",timeout:20000});
      let metrics=await page.evaluate(()=>({
        overflow:document.documentElement.scrollWidth>window.innerWidth+2,
        primaryHeading:!!document.querySelector("h1"),
        chrome:!!document.querySelector(".site-header"),
        proposalMarkup:document.body.textContent.includes("REQUEST A PROPOSAL"),
      }));
      verify("buy-"+width,
        metrics.primaryHeading&&!metrics.overflow&&metrics.chrome&&metrics.proposalMarkup,metrics);
      await page.goto(base+"/commercial?product=competitor_search_gap#commercial-enquiry",{waitUntil:"networkidle2",timeout:20000});
      await page.waitForFunction(()=>document.querySelector('form select')?.value==="competitor_search_gap",{timeout:9000});
      metrics=await page.evaluate(()=>({
        overflow:document.documentElement.scrollWidth>window.innerWidth+2,
        selectedOffer:document.querySelector("form select")?.value,
        consentUnchecked:document.querySelector("form input[type=checkbox]")?.checked===false,
        submitDisabled:document.querySelector("form button[type=submit]")?.disabled===true,
        privacyLink:!!document.querySelector('form a[href="/privacy"]'),
        chrome:!!document.querySelector(".site-header"),
      }));
      verify("commercial-approved-"+width,
        !metrics.overflow&&metrics.selectedOffer==="competitor_search_gap"
        &&metrics.consentUnchecked&&metrics.submitDisabled&&metrics.privacyLink&&metrics.chrome,
        metrics);
      await page.goto(base+"/commercial?product=forged_unknown#commercial-enquiry",{waitUntil:"networkidle2",timeout:20000});
      await page.waitForFunction(()=>document.body.textContent.includes("The requested product is not available for a proposal"),{timeout:9000});
      metrics=await page.evaluate(()=>({
        rejectedMessage:document.body.textContent.includes("The requested product is not available for a proposal"),
        noAutoSelectedProduct:document.querySelector("form select")?.value==="",
        consentUnchecked:document.querySelector("form input[type=checkbox]")?.checked===false,
        submitDisabled:document.querySelector("form button[type=submit]")?.disabled===true,
      }));
      verify("commercial-rejected-"+width,
        Object.values(metrics).every(Boolean),metrics);
    }
  }finally{
    await browser.close();
    server.close();
  }
})().catch(err=>{observed.pageErrors.push(err.message);process.exitCode=1;}).finally(()=>{
  observed.publicPostSubmitted=false;
  const ok=observed.pages.length===6&&observed.pages.every(x=>x.pass)
     &&observed.pageErrors.length===0&&observed.blockedPostRequests===0;
  observed.status=ok?"COMBINED_CHECKOUT_BROWSER_PASS":"COMBINED_CHECKOUT_BROWSER_HOLD";
  fs.writeFileSync(path.join(output,"checks.json"),JSON.stringify(observed,null,2));
  if(!ok)process.exitCode=1;
  console.log(observed.status,"checked",observed.pages.length,"page_errors",observed.pageErrors.length);
});
