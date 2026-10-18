"use strict";
/** Local-only SSR+Chromium review; never mutates the production console. */
const assert = require("node:assert/strict");
const puppeteer = require(process.env.PUPPETEER_MODULE || "puppeteer");

const origin = "http://127.0.0.1:3197";
const api = "http://127.0.0.1:8871/v1/search/department/review";

async function main(){
  const source = await fetch(api, {cache: "no-store"});
  assert.equal(source.status, 200);
  const report = await source.json();
  const chart = report.gsc_daily_chart;
  assert.equal(chart?.schema_version, "empire.search.gsc_daily_chart_evidence.v1");
  assert.equal(chart?.source, "google_search_console_date_dimension");
  assert.equal(chart?.status, "DATE_DIMENSION_ROWS_OBSERVED");
  assert.equal(chart?.missing_days_treated_as_zero, false);
  assert.equal(chart?.independent_google_rank_positions_verified, false);
  assert.equal(chart?.realised_revenue_verified, false);
  assert.equal(chart?.days_missing_unreported.length, 0);
  assert.ok(chart.rows.length > 1 && chart.rows.length <= 31);
  const browser=await puppeteer.launch({
    headless:true,
    executablePath:process.env.CHROME_BIN,
    args:["--no-sandbox","--disable-dev-shm-usage","--disable-gpu"],
  });
  try {
    for (const width of [390,1440]){
      const page=await browser.newPage();
      await page.setViewport({width,height:950});
      const forbidden=[];const errors=[];
      await page.setRequestInterception(true);
      page.on("request",(req)=>{
        if (!["GET","HEAD"].includes(req.method()) || !req.url().startsWith(origin+"/")){
          forbidden.push(req.url()); return req.abort();
        }
        req.continue();
      });
      page.on("pageerror",(err)=>errors.push(err.message));
      try {
        const result=await page.goto(origin+"/department",{waitUntil:"networkidle2",timeout:30000});
        assert.equal(result.status(),200);
        const metrics=await page.evaluate(()=>{
          const text=document.body.innerText.toLowerCase();
          const panel=[...document.querySelectorAll("section")].find(
            s=>s.getAttribute("aria-label")==="First-party daily search trend");
          return {
            visible:!!panel,
            panelText:panel?.innerText.toLowerCase(),
            dataRows:panel?.querySelectorAll("tbody tr").length,
            barCount:panel?.querySelectorAll('[title$="reported impressions"]').length,
            clicksSvg:!!panel?.querySelector('svg[aria-label*="clicks"]'),
            horizontalOverflow:document.documentElement.scrollWidth-document.documentElement.clientWidth,
            robots:document.querySelector('meta[name="robots"]')?.content,
            claims: [
              text.includes("independent google rankings verified"),
              text.includes("revenue verified"),
            ],
          };
        });
        assert.equal(metrics.visible,true);
        assert.ok(metrics.panelText.includes("observed organic search trend"));
        assert.ok(metrics.panelText.includes(chart.reported_date_dimension_impressions.toLocaleString("en-GB").toLowerCase()));
        assert.ok(metrics.panelText.includes(chart.reported_date_dimension_clicks.toLocaleString("en-GB").toLowerCase()));
        assert.equal(metrics.dataRows,chart.rows.length);
        assert.equal(metrics.barCount,chart.rows.length);
        assert.equal(metrics.clicksSvg,true);
        assert.equal(metrics.horizontalOverflow <= 2,true);
        assert.ok(metrics.robots.includes("noindex"));
        assert.deepEqual(metrics.claims,[false,false]);
        assert.deepEqual(forbidden,[]); assert.deepEqual(errors,[]);
        console.log("GSC_DAILY_CHART_BROWSER_PASS",width,"observed_days="+chart.rows.length,
          "reported_clicks="+chart.reported_date_dimension_clicks);
      } finally {await page.close();}
    }
  } finally {await browser.close();}
}
main().catch((error)=>{ console.error(error); process.exitCode=1;});
