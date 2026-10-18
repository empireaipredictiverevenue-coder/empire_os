"use strict";
/** Staged SSR+browser smoke against existing read-only Search API.
 * Launcher supplies local preview and API ports. No POST, external requests,
 * customer records, search queries or publication.
 */
const assert = require("node:assert/strict");
const puppeteer = require(process.env.PUPPETEER_MODULE || "puppeteer");
const origin = process.env.STAGED_SEARCH_CENTRE_ORIGIN || "http://127.0.0.1:3197";
async function main() {
  const browser = await puppeteer.launch({
    headless:true, executablePath: process.env.CHROME_BIN,
    args:["--no-sandbox","--disable-dev-shm-usage","--disable-gpu"],
  });
  try {
    for (const width of [390,1440]) {
      const page=await browser.newPage();
      await page.setViewport({width,height:900});
      const forbidden=[];
      const errors=[];
      await page.setRequestInterception(true);
      page.on("request",req=>{
        if(!["GET","HEAD"].includes(req.method())){
          forbidden.push(req.method());return req.abort();
        }
        if(!req.url().startsWith(origin+"/")){
          forbidden.push("EXTERNAL_URL");return req.abort();
        }
        req.continue();
      });
      page.on("pageerror",err=>errors.push(err.message));
      try {
        const resp=await page.goto(origin+"/department",{
          waitUntil:"networkidle2",timeout:30000,
        });
        assert.equal(resp.status(),200);
        const details=await page.evaluate(()=>{
          const text=document.body.innerText;
          return {
            heading:!!document.querySelector('h1')?.textContent.includes("Unified SEO evidence"),
            sourceHeld:text.includes("Department evidence unavailable"),
            headings:[...document.querySelectorAll("h2")].map(x=>x.textContent),
            noIndex:document.querySelector('meta[name="robots"]')?.content,
            links:[...document.querySelectorAll("a[href]")].map(a=>a.getAttribute("href")),
            text,
            scrollWidth:document.documentElement.scrollWidth,
            viewportWidth:document.documentElement.clientWidth,
          };
        });
        assert.equal(details.heading,true);
        assert.equal(details.sourceHeld,false,"real read-only aggregate should render");
        assert.ok(details.headings.some(s=>s?.includes("404 editorial priorities")));
        assert.ok(details.headings.some(s=>s?.includes("Cached evidence health")));
        assert.ok(details.headings.some(s=>s?.includes("Organic revenue chain")));
        assert.ok(details.headings.some(s=>s?.includes("Remaining evidence")));
        assert.ok(details.links.includes("/"));
        assert.ok(details.links.includes("/technical"));
        assert.ok(details.text.includes("Not verified"));
        assert.ok(details.text.includes("34"));
        assert.ok(details.text.includes("31"));
        assert.ok(details.text.includes("Fresh cache envelopes"));
        assert.ok(details.noIndex?.includes("noindex"));
        assert.ok(details.scrollWidth <= details.viewportWidth+2,
          "dashboard has no mobile horizontal overflow");
        assert.deepEqual(forbidden,[]);
        assert.deepEqual(errors,[]);
        console.log("PASS_LOCAL_SEO_DEPARTMENT_UI",width,
          "gsc sample and cache status visible; noindex and no external/POST");
      } finally {await page.close();}
    }
  } finally {await browser.close();}
}
main().catch(e=>{console.error(e);process.exitCode=1;});
