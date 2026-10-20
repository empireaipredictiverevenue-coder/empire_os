"use client";

import { useMemo, useState } from "react";
import { ArrowRight, RefreshCcw, SlidersHorizontal } from "lucide-react";
import {
  calculateSectorFunnel, FUNNEL_EXAMPLE, FUNNEL_PRESETS,
  sectorPreset, type FunnelAssumptions, type SectorExplorer,
} from "@/lib/sector-funnel-scenario";

const copy = {
  roofing: {
    eyebrow: "COMMERCIAL ROOFING / DEMAND EXPLORER",
    title: "How many roofing enquiries could meet a buyer's requirements?",
    detail: "Change enquiry volume, job-fit and buyer-acceptance assumptions. This example is not a live campaign, an approved service-area buy box or a proven connected call.",
    last: "Hypothetically buyer-accepted enquiries",
    terms: "A buyer-accepted enquiry is not automatically a billable call. Call connection, source permission, routing, contractual acceptance and payment are separate evidence.",
  },
  solar: {
    eyebrow: "SOLAR / REFERRAL JOURNEY EXPLORER",
    title: "From local solar interest to a completed installation.",
    detail: "Explore how postcode suitability, installer acceptance and eventual completion affect a hypothetical referral funnel.",
    last: "Hypothetically completed installs",
    terms: "An upstream publisher is not the same as a verified paying installer. A public affiliate rate is not Empire AI revenue; payment depends on a real signed downstream programme.",
  },
  b2b: {
    eyebrow: "PREDICTIVE REVENUE / EVIDENCE EXPLORER",
    title: "Which opportunities make it through qualification?",
    detail: "Explore a simple sales funnel before estimating value. It is an educational scenario, not a calibrated EmpireOS customer prediction.",
    last: "Hypothetically accepted opportunities",
    terms: "A buyer-accepted opportunity, a signed agreement and collected revenue are different facts. No internal CRM, Predictive Intelligence or Economic Memory data is used here.",
  },
} as const;

type SliderKey = keyof FunnelAssumptions;
const sliders: ReadonlyArray<{
  key: SliderKey; name: string; description: string; max: number; step: number;
}> = [
  {key:"monthlyEnquiries",name:"Enquiries per month",description:"Illustrative inbound interest, not actual visits or leads",max:500,step:1},
  {key:"qualificationPct",name:"Fit qualification",description:"Percent matching your buyer's or installer's requirements",max:100,step:1},
  {key:"buyerAcceptancePct",name:"Buyer acceptance",description:"Percent of qualified enquiries hypothetically accepted",max:100,step:1},
  {key:"completionPct",name:"Installation completion",description:"Percent of accepted solar cases completed",max:100,step:1},
];

function shown(value:number) {
  return new Intl.NumberFormat("en-GB",{maximumFractionDigits:1}).format(value);
}

export default function SectorOpportunityExplorer({
  sector,
}: {sector:SectorExplorer}) {
  const [inputs,setInputs] = useState<FunnelAssumptions>(()=>({...FUNNEL_EXAMPLE[sector]}));
  const [preset,setPreset] = useState("example");
  const result = useMemo(()=>calculateSectorFunnel(sector,inputs),[sector,inputs]);
  const stages = [
    {label:"Enquiries",value:result.monthlyEnquiries},
    {label:"Fit requirements",value:result.qualified},
    {label:"Buyer-accepted",value:result.accepted},
    ...(sector==="solar"?[{label:"Completed installs",value:result.completed ?? 0}]:[]),
  ];
  const context=copy[sector];

  const change = (key:SliderKey,value:number) => {
    const limit = key==="monthlyEnquiries"?10000:100;
    if(!Number.isFinite(value) || value<0 || value>limit) return;
    setInputs(previous=>({...previous,[key]:value}));
    setPreset("custom");
  };

  return <section id={`scenario-${sector}`} aria-labelledby={`scenario-${sector}-title`}
    className="relative z-10 mx-auto max-w-[1380px] px-5 py-20 md:px-10 lg:py-28">
    <div className="relative overflow-hidden rounded-[2rem] border border-cyan-300/25 bg-[radial-gradient(circle_at_95%_0%,rgba(28,113,195,.22),transparent_38%),linear-gradient(135deg,#0b213e,#040b1c_72%)] p-5 shadow-[0_30px_110px_rgba(0,0,0,.28)] sm:p-9 lg:p-12">
      <div className="flex flex-wrap items-center gap-2 text-[10px] font-bold uppercase tracking-[.18em] text-cyan-200">
        <SlidersHorizontal className="size-4" aria-hidden="true"/>{context.eyebrow}
        <span className="rounded-full border border-amber-300/35 px-3 py-1 text-amber-200">Illustrative · Not live buyer data</span>
      </div>
      <div className="mt-5 grid gap-8 lg:grid-cols-[1fr_.9fr] lg:gap-16">
        <div>
          <h2 id={`scenario-${sector}-title`} className="max-w-xl text-[clamp(2rem,3.8vw,3.6rem)] font-semibold leading-[1.08] tracking-[-.045em] text-white">{context.title}</h2>
          <p className="mt-5 max-w-xl text-sm leading-7 text-slate-300">{context.detail}</p>
          <div role="group" aria-label={`Example assumption presets for ${sector}`} className="mt-7 flex flex-wrap gap-2">
            {FUNNEL_PRESETS.map(item=><button type="button" key={item.id}
              aria-pressed={preset===item.id}
              onClick={()=>{setInputs(sectorPreset(sector,item.id));setPreset(item.id);}}
              className={`min-h-11 rounded-full border px-4 py-2 text-xs font-semibold transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-cyan-200 ${preset===item.id?"border-amber-300/70 bg-amber-300/15 text-amber-100":"border-white/20 text-slate-200 hover:border-cyan-300/60"}`}>
              {item.label}</button>)}
            <button type="button" aria-label="Reset illustrative enquiry figures"
              onClick={()=>{setInputs({...FUNNEL_EXAMPLE[sector]});setPreset("example");}}
              className="inline-flex min-h-11 items-center gap-2 rounded-full border border-white/20 px-4 py-2 text-xs text-slate-300 hover:border-cyan-300/60">
              <RefreshCcw className="size-3" aria-hidden="true"/> Reset</button>
          </div>
          <div className="mt-8 grid gap-6" aria-label="Editable scenario sliders">
            {sliders.filter(item=>item.key!=="completionPct"||sector==="solar").map(item=>{
              const max=Math.max(item.max,inputs[item.key]);
              return <div key={item.key}>
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <label htmlFor={`${sector}-${item.key}`} className="text-sm font-semibold text-white">{item.name}</label>
                  <output htmlFor={`${sector}-${item.key}`} className="font-mono text-lg font-semibold tabular-nums text-amber-200">{shown(inputs[item.key])}{item.key==="monthlyEnquiries"?"":"%"}</output>
                </div>
                <p className="mt-1 text-xs leading-5 text-slate-400">{item.description}</p>
                <input id={`${sector}-${item.key}`} type="range" min={0} max={max} step={item.step}
                  value={inputs[item.key]}
                  onChange={e=>change(item.key,Number(e.target.value))}
                  aria-valuetext={`${shown(inputs[item.key])}${item.key==="monthlyEnquiries"?" enquiries":" percent"}`}
                  style={{accentColor:"#64d9ff"}}
                  className="mt-3 h-8 w-full cursor-pointer rounded-full touch-pan-y focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cyan-200"/>
              </div>;
            })}
          </div>
        </div>

        <div className="flex flex-col">
          <div aria-live="polite" aria-atomic="true"
            className="rounded-3xl border border-amber-200/25 bg-[#07152a]/80 p-6">
            <p className="text-xs font-semibold uppercase tracking-[.15em] text-amber-200">YOUR ASSUMPTIONS / MONTH</p>
            <p className="mt-3 text-sm text-slate-300">{context.last}</p>
            <p data-testid={`funnel-${sector}-result`} className="mt-2 font-mono text-[clamp(2.8rem,5vw,5rem)] font-semibold leading-none tracking-[-.04em] text-white">{shown(result.completed ?? result.accepted)}</p>
            <p className="mt-3 text-xs leading-6 text-slate-400">Hypothetical count, not a verified person, billable event or real sale.</p>
          </div>
          <div className="mt-7 space-y-5" aria-label="Illustrative funnel stages">
            {stages.map((stage,index)=>{
              const share = result.monthlyEnquiries>0 ? stage.value/result.monthlyEnquiries*100 : 0;
              return <div key={stage.label}>
                <div className="flex justify-between gap-2 text-sm">
                  <span className="text-slate-300">{String(index+1).padStart(2,"0")} · {stage.label}</span>
                  <span className="font-mono tabular-nums text-white">{shown(stage.value)}</span>
                </div>
                <div role="meter" aria-label={stage.label+" relative to enquiries"} aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(share)}
                  className="mt-2 h-2.5 overflow-hidden rounded-full bg-[#1d3251]">
                  <div className={`h-full rounded-full transition-[width] duration-300 ${index===stages.length-1?"bg-gradient-to-r from-amber-400 to-amber-200":"bg-gradient-to-r from-blue-600 to-cyan-300"}`}
                    style={{width:`${share}%`}}/>
                </div>
              </div>;
            })}
          </div>
          <p className="mt-8 border-l-2 border-amber-300/55 pl-4 text-xs leading-6 text-slate-300">{context.terms}</p>
          <div className="mt-7 flex flex-wrap gap-3">
            <a href="/insights/revenue-opportunity-assessment" className="inline-flex min-h-12 items-center gap-2 rounded-full border border-cyan-300/40 px-5 py-3 text-xs font-bold text-cyan-100 transition hover:bg-cyan-300/10">
              Explore the full ROI calculator <ArrowRight className="size-4" aria-hidden="true"/></a>
            <a href="/commercial" className="inline-flex min-h-12 items-center rounded-full bg-amber-300 px-5 py-3 text-xs font-bold text-[#0b1730] hover:bg-white">
              Request a scoped assessment</a>
          </div>
        </div>
      </div>
    </div>
  </section>;
}
