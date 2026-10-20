"use client";

import { useEffect, useMemo, useState } from "react";
import RoiGuidedConversation from "./RoiGuidedConversation";
import {reviewPublicReaderStatus, type RoiPublicReaderStatus} from "@/lib/roi-public-reader-status";
import {
  answerAssessmentQuestion, buildRoiActionPlan, buildRoiGuidance,
  exportAssessmentText, type RoiQuestion,
} from "@/lib/roi-guidance";
import {
  calculateRoiScenarios, ILLUSTRATIVE_INPUTS, PREVIEW_INTELLIGENCE_CONTEXT,
  publicIntelligenceSignals, type RoiInputs,
} from "@/lib/roi-assessment";

type Field = { key: keyof RoiInputs; label: string; help: string; max: number; step: number };
const fields: readonly Field[] = [
  {key:"monthlyLeads",label:"Monthly enquiries",help:"Enquiries received in a typical month",max:100000,step:1},
  {key:"qualificationRatePct",label:"Qualified leads (%)",help:"Current share of enquiries that fit your requirements",max:100,step:1},
  {key:"closeRatePct",label:"Qualified leads that buy (%)",help:"Share of qualified leads that become customers",max:100,step:1},
  {key:"contributionPerDeal",label:"Contribution per completed sale",help:"Sale value minus directly attributable delivery costs",max:10000000,step:25},
  {key:"minutesPerLead",label:"Review minutes per enquiry",help:"Time spent qualifying every incoming enquiry",max:1440,step:1},
  {key:"loadedHourlyCost",label:"Hourly staff cost",help:"Estimated fully loaded labour cost",max:100000,step:1},
  {key:"monthlySolutionCost",label:"Assumed monthly solution cost",help:"Your estimated recurring cost, not an Empire AI quote",max:10000000,step:25},
  {key:"oneTimeSetupCost",label:"Assumed implementation cost",help:"Your estimated one-off cost, not an Empire AI quote",max:10000000,step:25},
  {key:"qualificationLiftPoints",label:"Assumed qualification lift (points)",help:"e.g. 30% to 35% qualified is +5 percentage points",max:100,step:1},
  {key:"reviewTimeSavedPct",label:"Assumed review time saved (%)",help:"Estimate of manual qualification time avoided",max:100,step:1},
];

/** Comfortable slider ranges. Numeric boxes still permit the existing bounded engine caps. */
const sliderCaps: Record<keyof RoiInputs,number> = {
  monthlyLeads: 1200,
  qualificationRatePct: 100,
  closeRatePct: 100,
  contributionPerDeal: 5000,
  minutesPerLead: 60,
  loadedHourlyCost: 250,
  monthlySolutionCost: 5000,
  oneTimeSetupCost: 10000,
  qualificationLiftPoints: 100,
  reviewTimeSavedPct: 100,
};
function inputUnits(key:keyof RoiInputs):string {
  return ["qualificationRatePct","closeRatePct","reviewTimeSavedPct","qualificationLiftPoints"].includes(key) ? "%" : "";
}

const explanation = [
  {
    label:"How are additional customers estimated?",
    body:"Additional qualified enquiries equal monthly leads multiplied by the assumed percentage-point lift. They are multiplied by your stated close rate to estimate extra won deals. No model-derived buyer probability is used.",
  },
  {
    label:"Where does the labour saving come from?",
    body:"Monthly enquiries × review minutes per enquiry ÷ 60 × hourly staff cost × assumed time saved. No automatic claim is made that all freed time turns into cash savings.",
  },
  {
    label:"How will Empire Intelligence improve it?",
    body:"Search, Market, Competitor, Buyer, Predictive and Economic Memory can add properly sourced context after public-use and privacy checks. Evidence stays separated from user assumptions; missing predictive cohorts never create fabricated probabilities.",
  },
];

export default function RevenueOpportunityAssessment() {
  const [inputs,setInputs] = useState<RoiInputs>({...ILLUSTRATIVE_INPUTS});
  const [currency,setCurrency] = useState<"GBP"|"USD">("GBP");
  const [expanded,setExpanded] = useState<number|null>(null);
  const [showEvidence,setShowEvidence] = useState(false);
  const [readerStatus,setReaderStatus] = useState<RoiPublicReaderStatus|null>(null);
  const [readerLoading,setReaderLoading] = useState(false);
  const [question,setQuestion] = useState<RoiQuestion | null>(null);
  const results = useMemo(()=>{
    try {return {rows:calculateRoiScenarios(inputs),error:""};}
    catch (error) {return {rows:[],error:error instanceof Error?error.message:"Invalid assumptions"};}
  },[inputs]);
  const formatCurrency = (value:number) =>
    new Intl.NumberFormat(currency==="GBP"?"en-GB":"en-US",
      {style:"currency",currency,maximumFractionDigits:0}).format(value);
  const formatNumber = (value:number) =>
    new Intl.NumberFormat("en-GB",{maximumFractionDigits:1}).format(value);
  const verifiedSignals=publicIntelligenceSignals(PREVIEW_INTELLIGENCE_CONTEXT);
  // Only check existing Search Intelligence operational status on request.
  // No ROI inputs, contact information, questions or other customer data sent.
  useEffect(()=>{
    if(!showEvidence) return;
    const controller=new AbortController();
    setReaderLoading(true);
    fetch("/v1/roi/intelligence/public", {
      method:"GET",cache:"no-store",signal:controller.signal,
    }).then(async response=>{
      if(!response.ok) return null;
      return response.json() as Promise<unknown>;
    }).then(payload=>{
      if(!controller.signal.aborted)
        setReaderStatus(reviewPublicReaderStatus(payload));
    }).catch(()=>{
      if(!controller.signal.aborted)setReaderStatus(reviewPublicReaderStatus(null));
    }).finally(()=>{
      if(!controller.signal.aborted)setReaderLoading(false);
    });
    return ()=>controller.abort();
  },[showEvidence]);
  const guidance=useMemo(
    ()=>results.error?null:buildRoiGuidance(inputs,results.rows[1]),
    [inputs,results],
  );
  const nextActions=useMemo(
    ()=>results.error?[]:buildRoiActionPlan(inputs,results.rows[1]),
    [inputs,results],
  );
  const baseCase=results.rows[1];
  /** A changed qualification slider cannot imply a base case above 100%. */
  function updateAssumption(key:keyof RoiInputs, value:number, fromSlider:boolean) {
    if(!Number.isFinite(value)) return;
    setInputs(previous=>{
      const next={...previous,[key]:value};
      if(fromSlider && key==="qualificationRatePct" &&
         next.qualificationRatePct+next.qualificationLiftPoints>100) {
        next.qualificationLiftPoints=Math.max(0,100-next.qualificationRatePct);
      }
      return next;
    });
  }

  function downloadAssessment() {
    if (results.error) return;
    const file=new Blob([exportAssessmentText(inputs,results.rows,currency)],{type:"text/plain;charset=utf-8"});
    const url=URL.createObjectURL(file);
    const link=document.createElement("a");
    link.href=url;
    link.download="empire-ai-revenue-opportunity-assessment.txt";
    document.body.append(link);link.click();link.remove();
    window.setTimeout(()=>URL.revokeObjectURL(url),1000);
  }

  return <main className="min-h-screen bg-[#020817] text-slate-100">
    <div className="relative isolate overflow-hidden border-b border-cyan-300/20 px-5 pb-14 pt-10 sm:px-10">
      <div className="pointer-events-none absolute inset-0 -z-10 bg-[radial-gradient(ellipse_at_80%_15%,rgba(0,155,255,.20),transparent_50%),radial-gradient(ellipse_at_10%_85%,rgba(245,190,55,.09),transparent_48%)]" />
      <div className="mx-auto max-w-6xl">
        <nav className="flex flex-wrap items-center gap-x-6 gap-y-3 text-sm text-slate-300" aria-label="Assessment navigation">
          <a href="/" className="font-semibold text-white hover:text-amber-200">Empire AI</a>
          <a href="/commercial" className="hover:text-cyan-200">Request a proposal</a>
          <a href="/trust" className="hover:text-cyan-200">Trust and evidence</a>
        </nav>
        <p className="mt-16 text-xs font-bold uppercase tracking-[.24em] text-cyan-300">Interactive commercial assessment · Preview</p>
        <h1 className="mt-5 max-w-4xl text-4xl font-semibold leading-[1.05] tracking-tight sm:text-6xl">
          See what better lead qualification <span className="text-amber-200">could be worth.</span>
        </h1>
        <p className="mt-7 max-w-3xl text-base leading-8 text-slate-300">
          Adjust your own business figures. Compare conservative, base and optimistic scenarios.
          Every result is recalculated locally and every assumption is visible.
        </p>
        <p className="mt-5 max-w-3xl border-l-2 border-amber-300/65 pl-4 text-sm leading-7 text-amber-100">
          Illustrative planning tool, not a forecast, guarantee, product quote or verified ROI.
          The starting figures are examples only. No personal data is submitted or stored.
        </p>
      </div>
    </div>

    <div className="mx-auto max-w-6xl px-5 py-12 sm:px-10">
      <section aria-labelledby="assumptions-title" className="rounded-3xl border border-white/10 bg-[#09162b] p-5 sm:p-8">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h2 id="assumptions-title" className="text-2xl font-semibold text-white">Your editable assumptions</h2>
            <p className="mt-2 text-sm leading-6 text-slate-400">Numbers are illustrative until you replace them with your actual figures.</p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <label className="text-sm text-slate-300" htmlFor="roi-currency">Currency</label>
            <select id="roi-currency" value={currency} onChange={e=>setCurrency(e.target.value as "GBP"|"USD")}
              className="rounded-lg border border-slate-600 bg-[#020817] px-3 py-2 text-white">
              <option value="GBP">GBP (£)</option><option value="USD">USD ($)</option>
            </select>
            <button type="button" onClick={()=>setInputs({...ILLUSTRATIVE_INPUTS})}
              className="rounded-lg border border-white/20 px-4 py-2 text-sm text-slate-200 hover:border-cyan-300">
              Reset examples
            </button>
            <button type="button" onClick={downloadAssessment} disabled={Boolean(results.error)}
              className="rounded-lg border border-amber-300/40 px-4 py-2 text-sm font-semibold text-amber-100 hover:bg-amber-300/10 disabled:opacity-40">
              Save my assessment
            </button>
          </div>
        </div>
        <p className="mt-3 text-xs text-slate-500">Changing currency switches the units only; it does not convert amounts at an exchange rate.</p>
        <p className="mt-5 flex items-center gap-2 text-xs font-semibold uppercase tracking-[.16em] text-cyan-200">
          <span aria-hidden="true">↔</span> Drag the sliders or enter exact figures
        </p>
        <div className="mt-5 grid gap-5 sm:grid-cols-2 lg:grid-cols-3" role="group" aria-label="Interactive ROI assumption sliders">
          {fields.map(field=>{
            const isLift=field.key==="qualificationLiftPoints";
            const allowedMax=isLift?Math.min(field.max,100-inputs.qualificationRatePct):field.max;
            const railMax=Math.max(Math.min(allowedMax,sliderCaps[field.key]),inputs[field.key]);
            const id=`roi-assumption-${field.key}`;
            return <div key={field.key} className="rounded-2xl border border-cyan-300/15 bg-[#050e20] p-4 transition-colors hover:border-cyan-300/35">
              <label htmlFor={id} className="block text-sm font-semibold text-slate-100">{field.label}</label>
              <span className="mt-1 block min-h-10 text-xs leading-5 text-slate-400">{field.help}</span>
              <input id={id} type="number" inputMode="decimal" min="0" max={allowedMax} step={field.step}
                value={inputs[field.key]} onChange={e=>updateAssumption(field.key,e.target.value===""?0:Number(e.target.value),false)}
                className="mt-3 w-full rounded-lg border border-cyan-300/25 bg-[#0c2040] px-3 py-3 text-base text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-cyan-300" />
              <div className="mt-4 flex items-center justify-between gap-3">
                <label htmlFor={`${id}-slider`} className="text-xs font-semibold text-cyan-200">Adjust instantly</label>
                <output htmlFor={`${id}-slider`} className="font-mono text-xs tabular-nums text-amber-200">
                  {formatNumber(inputs[field.key])}{inputUnits(field.key)}
                </output>
              </div>
              <input id={`${id}-slider`} type="range" min={0} max={railMax}
                step={field.step} value={inputs[field.key]}
                onChange={e=>updateAssumption(field.key,Number(e.target.value),true)}
                aria-label={`Adjust ${field.label}`}
                aria-valuetext={`${formatNumber(inputs[field.key])}${inputUnits(field.key)}`}
                style={{accentColor:"#71d8ff"}}
                className="mt-2 h-9 w-full cursor-pointer touch-pan-y focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cyan-300" />
            </div>;
          })}
        </div>
        {results.error && <p role="alert" className="mt-6 rounded-xl border border-amber-300/30 p-4 text-sm text-amber-200">{results.error}</p>}
      </section>

      <section aria-labelledby="scenario-title" className="mt-12">
        <div className="mb-9 rounded-3xl border border-cyan-300/25 bg-[linear-gradient(120deg,#0a2849,#081329)] p-6 sm:p-8">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[.18em] text-cyan-200">Live sensitivity readout</p>
              <h3 className="mt-3 text-lg font-semibold text-white">Move any slider to see how the example changes.</h3>
              <p className="mt-2 text-xs leading-6 text-slate-400">Base-case net benefit after assumed monthly solution costs; not realised income.</p>
            </div>
            <p data-testid="roi-live-preview" aria-live="polite"
              className={`font-mono text-3xl font-semibold tabular-nums ${baseCase && baseCase.netMonthlyBenefit>=0?"text-amber-200":"text-rose-200"}`}>
              {baseCase?formatCurrency(baseCase.netMonthlyBenefit):"—"}
            </p>
          </div>
          {baseCase && <div className="mt-6 grid gap-3 sm:grid-cols-3" aria-label="Illustrative three-scenario monthly outcome comparison">
            {results.rows.map(row=>{
              const largest=Math.max(1,...results.rows.map(item=>Math.abs(item.netMonthlyBenefit)));
              const ratio=Math.abs(row.netMonthlyBenefit)/largest*100;
              return <div key={row.name}>
                <p className="flex items-baseline justify-between gap-2 text-xs text-slate-300"><span>{row.name}</span>
                  <span className="font-mono tabular-nums text-white">{formatCurrency(row.netMonthlyBenefit)}</span></p>
                <div role="meter" aria-label={row.name+" monthly benefit magnitude"} aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(ratio)}
                  className="mt-2 h-2.5 overflow-hidden rounded-full bg-[#24374f]">
                  <div className={`h-full rounded-full transition-[width] duration-300 ${row.netMonthlyBenefit>=0?"bg-gradient-to-r from-cyan-500 to-amber-200":"bg-gradient-to-r from-rose-700 to-rose-300"}`}
                    style={{width:`${ratio}%`}}/>
                </div>
              </div>;
            })}
          </div>}
        </div>
        <h2 id="scenario-title" className="text-3xl font-semibold text-white">Three possible outcomes</h2>
        <p className="mt-3 max-w-4xl text-sm leading-7 text-slate-400">
          Conservative uses half your assumed improvements; optimistic uses 1.5 times them (capped at 100%).
          None are probabilities or independently predicted results.
        </p>
        <div className="mt-7 grid gap-5 lg:grid-cols-3" aria-live="polite">
          {results.rows.map(row=><article key={row.name}
            className={"rounded-3xl border p-6 "+(row.name==="Base case"?"border-cyan-300/55 bg-[#0b2543]":"border-white/15 bg-[#0a172d]")}>
            <p className="text-xs uppercase tracking-[.16em] text-cyan-200">{row.name}</p>
            <p className="mt-5 text-sm text-slate-300">Estimated monthly net benefit</p>
            <p className={"mt-2 text-3xl font-semibold "+(row.netMonthlyBenefit>=0?"text-amber-200":"text-rose-200")}>{formatCurrency(row.netMonthlyBenefit)}</p>
            <dl className="mt-7 grid gap-3 border-t border-white/15 pt-6 text-sm">
              {[
                ["Additional closed deals/month",formatNumber(row.estimatedAdditionalDeals)],
                ["Added monthly contribution",formatCurrency(row.incrementalContribution)],
                ["Illustrative labour saving",formatCurrency(row.labourSavings)],
                ["Monthly solution cost",formatCurrency(inputs.monthlySolutionCost)],
                ["First-year net after setup",formatCurrency(row.firstYearNet)],
                ["Illustrative first-year ROI",row.firstYearReturnPct===null?"Undefined (no costs entered)":formatNumber(row.firstYearReturnPct)+"%"],
                ["Setup payback",row.paybackMonths===null?"Not established":formatNumber(row.paybackMonths)+" months"],
              ].map(([label,value])=><div key={label} className="flex justify-between gap-3">
                <dt className="text-slate-400">{label}</dt>
                <dd className="text-right text-slate-100">{value}</dd>
              </div>)}
            </dl>
          </article>)}
        </div>
      </section>

      <section aria-labelledby="decision-title" className="mt-12 rounded-3xl border border-amber-300/20 bg-[#101b30] p-6 sm:p-8">
        <p className="text-xs font-bold uppercase tracking-[.16em] text-amber-200">Scenario diagnostics · assumption-based</p>
        <h2 id="decision-title" className="mt-3 text-2xl font-semibold">What would it take to break even?</h2>
        <p className="mt-3 max-w-4xl text-sm leading-7 text-slate-200">
          {guidance?.breakEvenExplanation ?? "Adjust the highlighted inputs to see your estimated break-even requirements."}
        </p>
        <p className="mt-4 text-xs leading-6 text-slate-400">
          This threshold spreads the assumed one-off setup across 12 months. It does not establish buyer
          conversion rates, achievable performance, or real cash savings.
        </p>
        {Boolean(guidance?.riskNotes.length) && <ul className="mt-5 grid gap-2" aria-label="Assumption risks">
          {guidance?.riskNotes.map(note=><li key={note} className="flex gap-3 text-sm leading-6 text-slate-300">
            <span aria-hidden="true" className="text-amber-200">•</span>{note}
          </li>)}
        </ul>}
      </section>

      <section aria-labelledby="actions-title" className="mt-12">
        <p className="text-xs font-semibold uppercase tracking-[.16em] text-cyan-300">From calculation to a real business decision</p>
        <h2 id="actions-title" className="mt-3 text-2xl font-semibold sm:text-3xl">Your next three practical checks</h2>
        <p className="mt-3 max-w-4xl text-sm leading-7 text-slate-400">
          A rule-based action plan from the figures you entered. These are hypotheses to verify,
          not insights from private EmpireOS data or guaranteed results.
        </p>
        <div className="mt-7 grid gap-4 lg:grid-cols-3">
          {nextActions.map(item=><article key={item.priority}
            className="rounded-2xl border border-white/15 bg-[#09162b] p-6">
            <span className="text-xs font-semibold uppercase tracking-[.15em] text-amber-200">
              Step {item.priority} · Your assumptions
            </span>
            <h3 className="mt-3 text-lg font-semibold text-white">{item.title}</h3>
            <p className="mt-4 text-sm leading-7 text-slate-300">{item.why}</p>
            <p className="mt-5 border-t border-white/10 pt-4 text-sm leading-7 text-cyan-100">
              <span className="font-semibold">Suggested check: </span>{item.suggestedTest}
            </p>
          </article>)}
        </div>
      </section>

      <section aria-labelledby="intelligence-title" className="mt-12 rounded-3xl border border-cyan-300/20 bg-[#081a33] p-6 sm:p-8">
        <p className="text-xs font-semibold uppercase tracking-[.16em] text-cyan-300">EmpireOS intelligence integration</p>
        <h2 id="intelligence-title" className="mt-3 text-2xl font-semibold">Evidence, not invented predictions</h2>
        <p className="mt-3 max-w-3xl text-sm leading-7 text-slate-300">
          The assessment still uses only the numbers you enter. You can check whether our own Search Intelligence reader
          is online, but that status does not establish demand in your sector, verified customers or revenue. No private
          observations or forecasts are shared with this public calculator.
        </p>
        <button type="button" aria-expanded={showEvidence} onClick={()=>setShowEvidence(value=>!value)}
          className="mt-6 rounded-full border border-cyan-300/35 px-5 py-3 text-sm font-semibold text-cyan-100 hover:bg-cyan-300/10">
          {showEvidence?"Hide":"Show"} intelligence source status
        </button>
        {showEvidence && <p role="status" className="mt-3 text-xs text-slate-400">
          {readerLoading?"Checking existing Search Intelligence reader…":
            readerStatus?.ready?"Owned Search Intelligence reader responding; no public outcome evidence released.":
            "No authorised public Search Intelligence result is available. Your assessment still works offline."}
        </p>}
        {showEvidence && <ul className="mt-6 grid gap-3 sm:grid-cols-2">
          {PREVIEW_INTELLIGENCE_CONTEXT.map(signal=><li key={signal.source} className="rounded-xl border border-white/10 p-4">
            <p className="text-sm font-semibold text-white">{signal.source.replaceAll("_"," ")}</p>
            <p className="mt-1 text-xs uppercase tracking-wider text-amber-200">
              {verifiedSignals.some(item=>item.source===signal.source)?"Evidence available":
                signal.source==="SEARCH_INTELLIGENCE" && readerStatus?.ready
                  ?"Owned source reader connected · No public market evidence"
                  :"No public evidence available"}
            </p>
            <p className="mt-2 text-sm leading-6 text-slate-400">
              {signal.source==="SEARCH_INTELLIGENCE" && readerStatus?.ready
                ?"Empire AI Search Intelligence is in read-only OBSERVE mode for its own website. This is not your business search data or a verified ROI claim."
                :signal.summary}
            </p>
          </li>)}
        </ul>}
      </section>

      <section aria-labelledby="help-title" className="mt-12">
        <h2 id="help-title" className="text-2xl font-semibold">Ask about your assessment</h2>
        <p className="mt-2 text-sm text-slate-400">
          An interactive, rule-based guide uses the figures you entered. This is not a live AI chat or a financial adviser.
        </p>
        <div className="mt-6 rounded-2xl border border-cyan-300/25 bg-[#0b1d39] p-5 sm:p-7">
          <p className="text-xs font-semibold uppercase tracking-[.17em] text-cyan-200">Choose a question</p>
          <div className="mt-4 flex flex-wrap gap-3" role="group" aria-label="Assessment questions">
            {([
              ["break_even","What would make this worthwhile?"],
              ["key_assumptions","Which inputs matter most?"],
              ["predictive_intelligence","Can Empire predict my outcome?"],
              ["next_steps","What happens next?"],
            ] as const).map(([key,label])=><button type="button" key={key}
              aria-pressed={question===key} disabled={Boolean(results.error)}
              onClick={()=>setQuestion(key)}
              className={"rounded-xl border px-4 py-3 text-left text-sm disabled:opacity-40 "+
                (question===key?"border-amber-200/70 bg-amber-200/10 text-white":
                "border-white/15 text-slate-200 hover:border-cyan-200/50")}>
              {label}
            </button>)}
          </div>
          {question && !results.error && <div aria-live="polite"
            className="mt-6 rounded-xl border border-white/10 bg-[#061329] p-5 text-sm leading-7 text-slate-200">
            {answerAssessmentQuestion(question,inputs,results.rows[1],currency)}
          </div>}
          <p className="mt-4 text-xs leading-6 text-slate-400">
            No chat messages, assessment inputs or downloaded files are sent to EmpireOS.
            A future optional AI concierge must use an authorised, privacy-reviewed connection.
          </p>
        </div>
        <div className="mt-5 grid gap-3">{explanation.map((item,index)=><div key={item.label} className="rounded-xl border border-white/10 bg-[#09162b]">
          <button type="button" aria-expanded={expanded===index} onClick={()=>setExpanded(expanded===index?null:index)}
            className="w-full px-5 py-4 text-left text-sm font-semibold text-white hover:text-cyan-200">
            {item.label} <span aria-hidden="true">{expanded===index?"−":"+"}</span>
          </button>
          {expanded===index&&<p className="px-5 pb-5 text-sm leading-7 text-slate-300">{item.body}</p>}
        </div>)}</div>
      </section>

      {baseCase && <RoiGuidedConversation inputs={inputs} base={baseCase} currency={currency} />}

      <section className="mt-12 rounded-3xl border border-amber-200/20 bg-[linear-gradient(125deg,#13365b,#060f21)] p-7 sm:p-10">
        <h2 className="text-2xl font-semibold sm:text-3xl">Want to explore the real opportunity?</h2>
        <p className="mt-4 max-w-3xl text-sm leading-7 text-slate-200">
          Tell our founder about your business goals and ask for a scoped, nonbinding review.
          The existing enquiry form is email-first. No calculation inputs are transferred automatically.
        </p>
        <a href="/commercial#proposal-heading" className="mt-7 inline-flex min-h-12 items-center rounded-full bg-amber-300 px-6 py-3 text-sm font-bold text-[#061127] hover:bg-white">
          Request a founder-reviewed proposal →
        </a>
      </section>
    </div>
  </main>;
}
