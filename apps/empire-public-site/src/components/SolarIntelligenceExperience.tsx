import {
  ArrowDownRight, ArrowRight, ArrowUpRight, BadgeCheck,
  Building2, ChartNoAxesCombined,
  FileCheck2, MapPin, Radar, ShieldCheck, Sun,
} from "lucide-react";
import type { IndustryPage } from "@/lib/industry-pages";
import { getBuyerEditorial } from "@/lib/industry-buying-editorial";
import { industryCommercialProposalHref } from "@/lib/commercial-entry-review";

const analysisSteps = [
  {
    number: "01", heading: "Establish the market",
    description: "Define geography, installer eligibility, property types and the buyer's actual serviceable territory before modelling demand.",
    icon: MapPin,
  },
  {
    number: "02", heading: "Cross-check the signals",
    description: "Review dated permits, property changes, search signals and public commercial activity. Distinguish an observation from an inference.",
    icon: Radar,
  },
  {
    number: "03", heading: "Assess commercial capacity",
    description: "Connect opportunities to an identified accepting installer or commercial programme, with exact qualification and geographic limits.",
    icon: Building2,
  },
  {
    number: "04", heading: "Measure accepted outcomes",
    description: "Reconcile permitted enquiries, buyer acceptance and verified fulfilment rather than treating traffic as payable solar revenue.",
    icon: FileCheck2,
  },
] as const;

const applications = [
  { label: "01 / MARKET SELECTION", title: "Where should we compete?",
    text: "Understand geographic demand, installer coverage and source quality before prioritising a territory." },
  { label: "02 / BUYER QUALIFICATION", title: "Who can accept the opportunity?",
    text: "Compare claimed interest with the partner's real coverage, exclusions, service capacity and consent requirements." },
  { label: "03 / PREDICTIVE PLANNING", title: "What could change next?",
    text: "Review market scenarios and forecast uncertainty without presenting estimates as real customer orders." },
] as const;

export default function SolarIntelligenceExperience({ page }: { page: IndustryPage }) {
  const editorial = getBuyerEditorial("solar");
  const proposal = industryCommercialProposalHref("solar");
  const schema = {
    "@context": "https://schema.org",
    "@type": "WebPage",
    name: "Solar Market Intelligence & Installer Demand | Empire AI",
    description: "Research solar market demand, territory opportunities, permitting and installer capacity with evidence-first Predictive Revenue intelligence.",
    url: "https://empire-ai.co.uk/industries/solar",
    publisher: { "@type": "Organization", name: "Empire AI", url: "https://empire-ai.co.uk" },
  };

  return (
    <main className="overflow-hidden bg-[#030916] text-[#ecf4ff] selection:bg-[#d5ad65] selection:text-[#07101f]">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }} />

      <div className="relative isolate min-h-[820px] overflow-hidden border-b border-[#a6beed]/10">
        {/* First-party, existing original solar photography. No stock overlays or speculative maps. */}
        <div aria-hidden="true" className="absolute inset-0 bg-[url('/art/sectors/solar-sunset-original.jpg')] bg-cover bg-[position:62%_center] opacity-80" />
        <div aria-hidden="true" className="absolute inset-0 bg-[linear-gradient(90deg,#030916_0%,rgba(3,9,22,.98)_23%,rgba(3,9,22,.83)_45%,rgba(3,9,22,.18)_100%),linear-gradient(0deg,#030916_0%,transparent_43%,rgba(3,9,22,.48)_100%)]" />
        <div aria-hidden="true" className="absolute inset-0 bg-[radial-gradient(ellipse_at_78%_32%,rgba(208,153,77,.18),transparent_42%)]" />

        <div className="relative z-10 mx-auto w-[min(1440px,calc(100%-40px))]">
          <div className="grid items-end gap-12 pb-24 pt-24 lg:grid-cols-[1.12fr_.88fr] lg:pb-28 lg:pt-32">
            <div className="max-w-[780px]">
              <p className="flex items-center gap-3 text-[11px] font-bold tracking-[.23em] text-[#f3d7a2]">
                <span className="h-px w-9 bg-[#e4b975]" /> SOLAR / ENERGY / PREDICTIVE INTELLIGENCE
              </p>
              <h1 className="mt-8 text-[clamp(3.55rem,7.4vw,7.6rem)] font-semibold leading-[.91] tracking-[-.067em]">
                Solar markets change.<span className="mt-2 block text-[#f3d7a2]">See the signals first.</span>
              </h1>
              <p className="mt-9 max-w-[610px] text-base leading-8 text-[#dbe7fa]/80 sm:text-lg">
                Bring property, permitting, installer coverage and real buyer requirements into one evidence-led view of solar opportunity.
                Make a better territory decision before committing budget or delivery capacity.
              </p>
              <div className="mt-10 flex flex-wrap gap-3">
                <a href={proposal} className="inline-flex min-h-13 items-center justify-center gap-3 rounded-full bg-[#dfb875] px-7 py-4 text-sm font-bold text-[#111a2a] shadow-[0_16px_45px_rgba(223,184,117,.18)] transition hover:bg-[#f4d49c]">
                  Discuss a solar market review <ArrowUpRight className="size-4" aria-hidden="true" />
                </a>
                <a href="#method" className="inline-flex min-h-13 items-center justify-center gap-3 rounded-full border border-[#b3cafa]/30 bg-[#06152b]/55 px-7 py-4 text-sm font-semibold text-white backdrop-blur-lg transition hover:border-white/50">
                  Explore the method <ArrowRight className="size-4" aria-hidden="true" />
                </a>
              </div>
              <p className="mt-6 max-w-lg text-xs leading-6 text-[#cfddf1]/65">
                Founder-reviewed, nonbinding enquiries. No claim of ready-to-buy homeowners, guaranteed installations or booked revenue.
              </p>
            </div>

            <div aria-label="Solar intelligence research dimensions" className="lg:justify-self-end">
              <div className="relative max-w-xl rounded-[28px] border border-[#cad9f3]/20 bg-[#071325]/75 p-6 shadow-[0_32px_100px_rgba(0,0,0,.40)] backdrop-blur-2xl sm:p-8">
                <div className="flex items-start justify-between gap-5 border-b border-white/10 pb-6">
                  <div>
                    <p className="text-[10px] font-bold tracking-[.22em] text-[#e9c487]">INTELLIGENCE FRAMEWORK</p>
                    <h2 className="mt-3 text-2xl font-semibold tracking-tight text-white">Connect the decision signals.</h2>
                  </div>
                  <Sun className="size-9 shrink-0 text-[#f1ca83]" strokeWidth={1.25} aria-hidden="true" />
                </div>
                <div className="grid grid-cols-2 gap-px overflow-hidden rounded-2xl border border-white/10 bg-white/10">
                  {[
                    ["01", "Property & project"], ["02", "Permits & policy"],
                    ["03", "Installer coverage"], ["04", "Buyer requirements"],
                  ].map(([number, label]) => (
                    <div key={number} className="min-h-32 bg-[#09182f]/95 p-5">
                      <p className="text-xs font-semibold text-[#e7bd79]">{number}</p>
                      <p className="mt-6 text-sm font-semibold leading-6 text-white">{label}</p>
                    </div>
                  ))}
                </div>
                <div className="mt-6 flex gap-3 text-xs leading-6 text-[#d6e4f6]/75">
                  <ShieldCheck className="mt-1 size-4 shrink-0 text-[#e7bd79]" aria-hidden="true"/>
                  <span>Research dimensions, not a live customer count or an assertion that every data source is active in every region.</span>
                </div>
              </div>
            </div>
          </div>
          <a href="#method" className="mb-9 inline-flex items-center gap-3 text-[10px] font-semibold tracking-[.2em] text-white/60">
            UNDERSTAND THE WORKFLOW <ArrowDownRight className="size-4" aria-hidden="true" />
          </a>
        </div>
      </div>

      <section id="method" className="relative mx-auto w-[min(1360px,calc(100%-40px))] scroll-mt-12 py-24 sm:py-32">
        <div className="grid gap-10 lg:grid-cols-[.66fr_1fr] lg:gap-20">
          <div>
            <p className="text-xs font-bold tracking-[.22em] text-[#e7bd79]">FROM SIGNAL TO DECISION</p>
            <h2 className="mt-6 max-w-lg text-[clamp(2.7rem,5vw,4.8rem)] font-semibold leading-[1.02] tracking-[-.055em]">
              Better data. <span className="text-[#f1ca83]">Better solar decisions.</span>
            </h2>
            <p className="mt-7 max-w-md text-base leading-8 text-[#ccd9ee]/65">
              A permit is not a purchase. Search interest is not an accepted enquiry. The useful work is joining independent evidence and knowing the difference.
            </p>
          </div>
          <div className="divide-y divide-[#a9c2f0]/15 border-y border-[#a9c2f0]/15">
            {analysisSteps.map(({number,heading,description,icon:Icon})=>
              <article key={number} className="grid gap-4 py-8 sm:grid-cols-[50px_1fr]">
                <div className="flex items-start gap-2"><span className="text-xs font-bold text-[#f1ca83]">{number}</span></div>
                <div className="flex gap-5">
                  <Icon className="mt-1 size-6 shrink-0 text-[#79b5fa]" strokeWidth={1.5} aria-hidden="true" />
                  <div>
                    <h3 className="text-xl font-semibold tracking-tight">{heading}</h3>
                    <p className="mt-3 max-w-2xl text-sm leading-7 text-[#c9d7ef]/65">{description}</p>
                  </div>
                </div>
              </article>
            )}
          </div>
        </div>
      </section>

      <section className="relative border-y border-white/10 bg-[linear-gradient(135deg,#0b1c39,#061124_56%,#0e1b30)]">
        <div className="mx-auto w-[min(1360px,calc(100%-40px))] py-24 sm:py-28">
          <div className="flex flex-wrap items-end justify-between gap-6">
            <div>
              <p className="text-xs font-bold tracking-[.22em] text-[#e7bd79]">WHAT A SCOPED REVIEW COULD COVER</p>
              <h2 className="mt-5 max-w-3xl text-[clamp(2.6rem,5vw,4.6rem)] font-semibold leading-[1.03] tracking-[-.05em]">An intelligence layer for real operators.</h2>
            </div>
            <ChartNoAxesCombined className="size-12 text-[#e7bd79]/75" strokeWidth={1.1} aria-hidden="true"/>
          </div>
          <div className="mt-12 grid gap-4 lg:grid-cols-3">
            {applications.map(item=>
              <article key={item.label} className="min-h-70 rounded-2xl border border-[#b6c8ee]/15 bg-white/[.035] p-7">
                <p className="text-[10px] font-bold tracking-[.17em] text-[#e7bd79]">{item.label}</p>
                <h3 className="mt-12 text-2xl font-semibold leading-tight tracking-[-.04em]">{item.title}</h3>
                <p className="mt-5 text-sm leading-7 text-[#d1ddf0]/65">{item.text}</p>
              </article>
            )}
          </div>
          <p className="mt-6 text-xs leading-6 text-[#cfdbeb]/60">
            Scope depends on source coverage, data rights, market and the agreed commercial question. These are illustrative research applications, not an inventory promise.
          </p>
        </div>
      </section>

      {editorial && (
        <section className="mx-auto w-[min(1360px,calc(100%-40px))] py-24 sm:py-32">
          <div className="grid items-start gap-10 lg:grid-cols-[.8fr_1fr] lg:gap-24">
            <div>
              <p className="text-xs font-bold tracking-[.22em] text-[#e7bd79]">BUYER AND REFERRAL ECONOMICS</p>
              <h2 className="mt-6 text-[clamp(2.6rem,4.7vw,4.6rem)] font-semibold leading-[1.04] tracking-[-.055em]">{editorial.heading}</h2>
              <p className="mt-6 text-base leading-8 text-[#cad8ee]/70">{editorial.introduction}</p>
            </div>
            <div className="space-y-4">
              {editorial.sections.map((item,index)=>
                <article key={item.heading} className="rounded-2xl border border-white/10 bg-[#0a1930] p-6 sm:p-8">
                  <div className="flex gap-4">
                    <span className="text-xs font-bold text-[#f1ca83]">0{index+1}</span>
                    <div>
                      <h3 className="text-xl font-semibold tracking-tight">{item.heading}</h3>
                      <p className="mt-4 text-sm leading-7 text-[#cdd9ee]/70">{item.body}</p>
                      {item.points && <ul className="mt-5 space-y-3 border-t border-white/10 pt-5">
                        {item.points.map(point=><li key={point} className="flex gap-3 text-xs leading-6 text-[#cdd9ee]/75"><BadgeCheck className="mt-1 size-4 shrink-0 text-[#e7bd79]" aria-hidden="true" />{point}</li>)}
                      </ul>}
                    </div>
                  </div>
                </article>
              )}
            </div>
          </div>
          <div className="mt-16 border-t border-white/10 pt-12">
            <h2 className="text-2xl font-semibold">Solar programme questions</h2>
            <div className="mt-5 grid gap-5 md:grid-cols-3">
              {editorial.questions.map(item=><article key={item.question} className="border-l border-[#e7bd79]/45 pl-5">
                <h3 className="text-base font-semibold">{item.question}</h3>
                <p className="mt-3 text-sm leading-7 text-[#cdd9ee]/65">{item.answer}</p>
              </article>)}
            </div>
          </div>
        </section>
      )}

      <section className="relative overflow-hidden border-t border-white/10 bg-[radial-gradient(ellipse_at_82%_25%,rgba(38,105,182,.22),transparent_45%),#061126]">
        <div className="mx-auto grid w-[min(1360px,calc(100%-40px))] items-center gap-12 py-24 lg:grid-cols-[1fr_auto] lg:py-28">
          <div>
            <p className="text-xs font-bold tracking-[.2em] text-[#e7bd79]">DISCUSS THE ACTUAL MARKET</p>
            <h2 className="mt-5 max-w-4xl text-[clamp(2.8rem,5.8vw,5.7rem)] font-semibold leading-[.98] tracking-[-.06em]">Where is your next <span className="text-[#f1ca83]">solar opportunity?</span></h2>
            <p className="mt-7 max-w-2xl text-base leading-8 text-[#d1dff2]/75">
              Tell us the territory, installer or programme context, and the commercial decision you need to make. We'll review the fit and possible scope before proposing work.
            </p>
          </div>
          <div className="flex flex-col gap-4">
            <a href={proposal} className="inline-flex min-h-14 items-center justify-center gap-3 rounded-full bg-[#dfb875] px-8 py-4 text-sm font-bold text-[#111a2a] transition hover:bg-[#f4d49c]">
              Request a scoped proposal <ArrowUpRight className="size-4" aria-hidden="true" />
            </a>
            <a href="/industries/hvac" className="inline-flex min-h-12 items-center justify-center gap-2 text-sm text-[#b9d8fb] underline-offset-4 hover:underline">
              Explore connected HVAC markets <ArrowRight className="size-4" aria-hidden="true" />
            </a>
          </div>
        </div>
        <div className="mx-auto flex w-[min(1360px,calc(100%-40px))] flex-wrap justify-between gap-4 border-t border-white/10 py-7 text-[11px] text-[#c5d2e5]/55">
          <span>EMPIRE AI / SOLAR INTELLIGENCE</span>
          <span>Source evidence · Commercial qualification · Human-approved scope</span>
          <a href="/privacy" className="hover:text-white">Privacy</a>
        </div>
      </section>
    </main>
  );
}
