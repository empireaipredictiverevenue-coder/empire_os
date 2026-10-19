"use strict";
const assert = require("node:assert/strict");
const puppeteer = require(process.env.PUPPETEER_MODULE || "puppeteer");
const origin = "http://127.0.0.1:3197";
async function main(){
  const sr=await fetch("http://127.0.0.1:8771/v1/search/department/review",{cache:"no-store"});
  assert.equal(sr.status,200);
  const source=await sr.json();const chart=source.gsc_daily_chart;
  assert.equal(source.schema_version,"empire.search_growth.department_integration.v1");
  assert.equal(chart?.status,"DATE_DIMENSION_ROWS_OBSERVED");
  assert.equal(source.realised_revenue_verified,false);
  const browser=await puppeteer.launch({headless:true,executablePath:process.env.CHROME_BIN,args:["--no-sandbox","--disable-dev-shm-usage"]});
  try{
    for(const width of [390,768,1440]){
      const page=await browser.newPage();
      await page.setViewport({width,height:920});
      const unexpected=[],errors=[];
      await page.setRequestInterception(true);
      page.on("request",req=>{
        if(!["GET","HEAD"].includes(req.method())||!req.url().startsWith(origin+"/")){unexpected.push(req.method()+" "+req.url());return req.abort();}
        req.continue();
      });
      page.on("pageerror",e=>errors.push(e.message));
      const response=await page.goto(origin+"/department",{waitUntil:"networkidle2",timeout:35000});
      assert.equal(response.status(),200);
      const d=await page.evaluate(()=>{
        const body=document.body.innerText.toLowerCase();
        const logo=document.querySelector('img[alt="Empire AI Predictive Revenue"]');
        return {
          title:document.querySelector("h1")?.textContent,
          hasSource:body.includes("date-dimension"),
          unknownVisitors:body.includes("visitors & sessions")&&body.includes("not connected"),
          unknownRevenue:body.includes("attributed revenue")&&body.includes("not connected"),
          quality:body.includes("measurement integrity"),
          evidenceLink:!!document.querySelector('a[href="/department/evidence"]'),
          dataRows:document.querySelectorAll('section[aria-label="First-party daily search trend"] tbody tr').length,
          impressionBars:document.querySelectorAll('section[aria-label="First-party daily search trend"] [title$="reported impressions"]').length,
          clicksLine:!!document.querySelector('section[aria-label="First-party daily search trend"] svg[aria-label*="clicks"]'),
          allSections:["overview","acquisition","content","conversions","data-quality"].every(s=>!!document.getElementById(s)),
          logoLoaded:!!logo&&logo.complete&&logo.naturalWidth>0,
          robots:document.querySelector('meta[name="robots"]')?.content,
          overflow:document.documentElement.scrollWidth-document.documentElement.clientWidth,
        };
      });
      assert.ok(d.title.includes("Analytics"));
      for(const k of ["hasSource","unknownVisitors","unknownRevenue","quality","evidenceLink","clicksLine","allSections","logoLoaded"])assert.equal(d[k],true,k);
      assert.equal(d.dataRows,chart.rows.length);
      assert.equal(d.impressionBars,chart.rows.length);
      assert.ok(d.robots.includes("noindex"));
      assert.ok(d.overflow<=2,"horizontal overflow "+d.overflow);
      assert.deepEqual(unexpected,[]);assert.deepEqual(errors,[]);
      if(width===1440)await page.screenshot({path:"/tmp/empire_analytics_revamp_desktop_20261019.png",fullPage:true});
      console.log("EMPIRE_ANALYTICS_BROWSER_PASS",width,"source_days="+chart.rows.length);
      await page.close();
    }
    const old=await browser.newPage();
    const resp=await old.goto(origin+"/department/evidence",{waitUntil:"networkidle2",timeout:35000});
    assert.equal(resp.status(),200);
    const text=await old.evaluate(()=>document.body.innerText);
    assert.ok(text.includes("Unified SEO evidence"));
    assert.ok(text.includes("404 editorial priorities"));
    console.log("EXISTING_EVIDENCE_ARCHIVE_PRESERVED_PASS");
    await old.close();
  }finally{await browser.close();}
}
main().catch(e=>{console.error(e);process.exitCode=1;});
