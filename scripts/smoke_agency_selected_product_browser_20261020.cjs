// Read-only browser smoke: actual frozen export, existing public GET catalogues,
// and zero writable HTTP calls. No fabricated live buyer data or POST requests.
"use strict";
const http = require("node:http");
const fs = require("node:fs");
const path = require("node:path");
const { once } = require("node:events");
const puppeteer = require("/home/ubuntu/.nvm/versions/node/v22.23.2/lib/node_modules/@wonderwhy-er/desktop-commander/node_modules/puppeteer");
const ROOT = "/home/ubuntu/empire_staging/agency_selected_product_enquiry_20261020/out";
const HOST = "127.0.0.1";
const PORT = 18890;
let blockedWrites = 0, forwardedGetCount = 0;
const mime = {".html":"text/html; charset=utf-8",".js":"application/javascript",".css":"text/css",".svg":"image/svg+xml",".woff2":"font/woff2",".png":"image/png",".webp":"image/webp",".json":"application/json"};
const server = http.createServer(async (req, res) => {
  try {
    if (req.method !== "GET" && req.method !== "HEAD") {
      blockedWrites++;
      res.writeHead(405).end("non-mutating browser smoke only");
      return;
    }
    const pathname = new URL(req.url, "http://localhost").pathname;
    if (pathname.startsWith("/v1/checkout/")) {
      if (!["/v1/checkout/catalog","/v1/checkout/commercial/offers","/v1/checkout/exchange/tiers"].includes(pathname)) {
        res.writeHead(404).end();
        return;
      }
      forwardedGetCount++;
      const reply = await fetch("http://127.0.0.1"+pathname,{headers:{Host:"empire-ai.co.uk"},signal:AbortSignal.timeout(5000)});
      res.writeHead(reply.status,{"Content-Type":reply.headers.get("content-type")||"application/json","Cache-Control":"no-store"});
      res.end(Buffer.from(await reply.arrayBuffer()));
      return;
    }
    const rel = pathname === "/" ? "index.html" : pathname.slice(1);
    let file = path.join(ROOT, rel);
    if (!path.extname(file)) file += ".html";
    if (!file.startsWith(ROOT+"/") || !fs.existsSync(file) || !fs.statSync(file).isFile()) {
      res.writeHead(404).end(); return;
    }
    res.writeHead(200,{"Content-Type":mime[path.extname(file)]||"application/octet-stream","Cache-Control":"no-store"});
    fs.createReadStream(file).pipe(res);
  } catch (e) {
    res.writeHead(500).end("local test fixture error");
  }
});
(async () => {
  server.listen(PORT,HOST);
  await once(server,"listening");
  let browser;
  try {
    browser = await puppeteer.launch({
      executablePath:"/home/ubuntu/.cache/puppeteer/chrome/linux-153.0.8010.36/chrome-linux64/chrome",
      headless: true,
      args:["--no-sandbox","--disable-dev-shm-usage","--disable-gpu"]
    });
    const page=await browser.newPage();
    const responses = [];
    page.on("response",r=>{ if (r.url().includes("/v1/checkout/")) responses.push({path:new URL(r.url()).pathname,status:r.status()}); });
    await page.goto("http://"+HOST+":"+PORT+"/buy",{waitUntil:"networkidle2",timeout:30000});
    const button = await page.$("button");
    await page.waitForFunction(() => [...document.querySelectorAll("button")].some(b=>b.textContent.includes("Competitor Search Gap")),{timeout:20000});
    // Exercise a non-default selection first, then switch back: tests React
    // state propagation, not merely an initially defaulted catalogue item.
    await page.evaluate(()=>{
      const button=[...document.querySelectorAll("button")].find(b=>b.textContent.includes("Search Opportunity Map"));
      if (!button) throw Error("second live catalogue product unavailable");
      button.click();
    });
    await page.waitForFunction(() => [...document.querySelectorAll("a")].some(
      a => a.textContent.includes("REQUEST A PROPOSAL")
        && a.getAttribute("href")==="/commercial?product=search_opportunity_map#commercial-enquiry"
    ),{timeout:10000});
    await page.evaluate(()=>{
      const button=[...document.querySelectorAll("button")].find(b=>b.textContent.includes("Competitor Search Gap"));
      if (!button) throw Error("approved competitor product unavailable");
      button.click();
    });
    await page.waitForFunction(() => [...document.querySelectorAll("a")].some(
      a => a.textContent.includes("REQUEST A PROPOSAL")
        && a.getAttribute("href")==="/commercial?product=competitor_search_gap#commercial-enquiry"
    ),{timeout:10000});
    const chosen=await page.evaluate(()=>{
      const cta=[...document.querySelectorAll("a")].find(a=>a.textContent.includes("REQUEST A PROPOSAL"));
      return cta?.getAttribute("href");
    });
    if (chosen !== "/commercial?product=competitor_search_gap#commercial-enquiry") throw Error("selected-product deep link missing: "+chosen);
    await page.goto("http://"+HOST+":"+PORT+chosen,{waitUntil:"networkidle2",timeout:30000});
    await page.waitForFunction(() => {
      const select=document.querySelector("#commercial-enquiry select");
      return select?.value==="competitor_search_gap";
    },{timeout:18000});
    const approved=await page.$eval("#commercial-enquiry select",el=>({value:el.value, label:el.selectedOptions[0]?.textContent}));
    await page.goto("http://"+HOST+":"+PORT+"/commercial?product=unknown-code#commercial-enquiry",{waitUntil:"networkidle2",timeout:30000});
    await page.waitForFunction(()=>document.querySelector("#commercial-enquiry select")?.value === "consultancy_opportunity_assessment",{timeout:18000});
    const unknownFallback=await page.$eval("#commercial-enquiry select",el=>el.value);
    if(blockedWrites) throw Error("browser emitted unexpected writable HTTP attempts");
    console.log(JSON.stringify({status:"REAL_BROWSER_SELECTED_PRODUCT_HANDOFF_PASS",selected_link:chosen,approved_product:approved,unknown_product_fallback:unknownFallback,live_catalogue_get_requests:responses,blocked_post_requests:blockedWrites,public_site_changed:false},null,2));
  } finally {
    if(browser) await browser.close();
    server.close();
  }
})().catch(e=>{process.stderr.write("BROWSER_SMOKE_HELD: "+e.message+"\n");process.exitCode=3;server.close();});
