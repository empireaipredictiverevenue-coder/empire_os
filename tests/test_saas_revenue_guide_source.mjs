// Editorial QA: render source-only JSX; no Next deploy, visitor POST or data access.
import {test} from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import {createRequire, Module} from "node:module";
import {fileURLToPath} from "node:url";

const here=path.dirname(fileURLToPath(import.meta.url));
const app=path.join(here,"../apps/empire-public-site");
const req=createRequire(path.join(app,"package.json"));
const ts=req("typescript");
const React=req("react");
const {renderToStaticMarkup}=req("react-dom/server");
const guideFile=path.join(app,"src/components/SaaSRevenueLeakageGuide.tsx");
const pageFile=path.join(app,"src/app/predictive-revenue/page.tsx");

function renderedGuide(){
  const source=fs.readFileSync(guideFile,"utf8");
  const js=ts.transpileModule(source,{compilerOptions:{
    module:ts.ModuleKind.CommonJS,
    jsx:ts.JsxEmit.ReactJSX,
    target:ts.ScriptTarget.ES2022,
  }}).outputText;
  const mod=new Module(guideFile);
  mod.filename=guideFile;
  mod.paths=Module._nodeModulePaths(path.dirname(guideFile));
  mod._compile(js,guideFile);
  return renderToStaticMarkup(React.createElement(mod.exports.default));
}

test("two evidence-led SaaS problems render one clear original guide",()=>{
  const html=renderedGuide();
  assert.match(html,/id="saas-revenue-diagnosis"/);
  assert.match(html,/id="saas-lost-recurring-revenue"/);
  assert.match(html,/id="saas-activation-friction"/);
  assert.match(html,/Why is SaaS recurring revenue falling/);
  assert.match(html,/Where does SaaS activation friction/);
  assert.equal((html.match(/<ol/g)||[]).length,2);
  assert.equal((html.match(/<li/g)||[]).length,8);
});

test("grounded sources and original buyer-intake destinations, never publisher routing",()=>{
  const html=renderedGuide();
  assert.match(html,/href="https:\/\/chartmogul.com\/saas-metrics\/nrr\/"/);
  assert.match(html,/href="https:\/\/amplitude.com\/docs\/quick-guides\/build-your-first-funnel"/);
  assert.match(html,/href="#deployment-request"/);
  assert.match(html,/href="\/commercial#commercial-enquiry"/);
  assert.doesNotMatch(html,/<form|onClick=|href="tel:|href="\/r\/|affiliate/);
  assert.match(html,/not consent to unrelated marketing/);
  assert.match(html,/not a diagnosis/);
});

test("existing form and immutable SEO director remain intact",()=>{
  const page=fs.readFileSync(pageFile,"utf8");
  assert.match(page,/import SaaSRevenueLeakageGuide/);
  assert.match(page,/<SaaSRevenueLeakageGuide \/>/);
  assert.match(page,/id="deployment-request"/);
  assert.match(page,/contact_consent: contactConsent/);
  assert.match(page,/\/v1\/checkout\/predictive-revenue\/interests/);
  assert.equal((page.match(/<SaaSRevenueLeakageGuide/g)||[]).length,1);
  assert.match(page,/PredictiveRevenueBuyerExplanation/);
  assert.doesNotMatch(fs.readFileSync(guideFile,"utf8"),/Math\.random|localStorage|sessionStorage/);
});
