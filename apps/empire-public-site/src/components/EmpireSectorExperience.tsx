import { ArrowUpRight, CheckCircle2, ChevronRight, ShieldCheck } from "lucide-react";
import type { IndustryPage } from "@/lib/industry-pages";
import solarHero from "../../public/art/sectors/solar-sunset-original.jpg";
import roofingHero from "../../public/art/sectors/roofing-work-original.jpg";
import { industryEditorialLinks } from "@/lib/industry-editorial-links";
import { getBuyerEditorial } from "@/lib/industry-buying-editorial";
import IndustryBuyerEditorialSection from "@/components/IndustryBuyerEditorialSection";
import SectorOpportunityExplorer from "@/components/SectorOpportunityExplorer";

type Sector = "solar" | "roofing";

const sectorContent: Record<Sector, {
  eyebrow: string; title: string; highlight: string; description: string;
  sectors: [string, string, string]; inquiries: [string, string, string];
  process: [string, string, string]; disclosures: string;
  accent: string; related: { label: string; href: string };
}> = {
  solar: {
    eyebrow: "EMPIRE AI / SOLAR INTELLIGENCE",
    title: "Solar growth starts with",
    highlight: "the right territory.",
    description: "For solar installers, operators and growth teams: study local demand, property suitability, installer coverage and enquiry qualification before spending on acquisition.",
    sectors: [
      "Roof condition, shading and property suitability",
      "Installer service territory and delivery capacity",
      "Finance, ownership and enquiry permission",
    ],
    inquiries: [
      "Which postcodes can your installers actually serve?",
      "What makes an enquiry sales-ready for your team?",
      "Which verification steps must happen before a referral?",
    ],
    process: [
      "Scope territory and installation criteria",
      "Review observable signals and evidence gaps",
      "Agree a qualified-enquiry definition before a proposal",
    ],
    disclosures: "Opportunity signals are research inputs, not verified solar installations, generated leads or guaranteed financial outcomes.",
    accent: "from-[#f0ba67] via-[#ffe0a2] to-[#79bfff]",
    related: { label: "Property signals", href: "/industries/property" },
  },
  roofing: {
    eyebrow: "EMPIRE AI / ROOFING INTELLIGENCE",
    title: "Commercial roofing demand intelligence,",
    highlight: "grounded in buyer fit.",
    description: "Find out which roofing territories, property types and project signals deserve attention before you commit time to acquisition. Empire AI combines first-party search observations, property and contractor-market research, and explicit buyer-acceptance criteria into a scoped commercial assessment. A signal is a reason to investigate—not a guaranteed roofing job, signed buyer or payable lead.",
    sectors: [
      "Commercial installation, replacement and restoration fit",
      "Storm, location and serviceability evidence",
      "Authorised property decision-maker and source permission",
    ],
    inquiries: [
      "Which service territories and commercial roofing projects are accepted?",
      "Who can authorise a survey, and when is the project viable?",
      "How will buyer acceptance and payable outcomes be verified?",
    ],
    process: [
      "Agree eligible geography and job categories",
      "Review demand and business-capacity evidence",
      "Define acceptance, attribution and compliance requirements",
    ],
    disclosures: "Storm and property signals do not prove roof damage or a homeowner's buying intent. No live call inventory or buyer settlement is claimed.",
    accent: "from-[#80b6ff] via-[#d0e6ff] to-[#68d4ed]",
    related: { label: "HVAC intelligence", href: "/industries/hvac" },
  },
};

export default function EmpireSectorExperience({ page }: { page: IndustryPage }) {
  if (page.slug !== "solar" && page.slug !== "roofing") return null;
  const sector = page.slug as Sector;
  const content = sectorContent[sector];
  const buyerEditorial = getBuyerEditorial(sector);
  const relatedResearch = industryEditorialLinks[sector] ?? [];
  return <main className="empire-surface min-h-screen overflow-hidden bg-[#030917] text-[#eef5ff]">
    <div className="pointer-events-none fixed inset-0 bg-[radial-gradient(ellipse_at_75%_5%,rgba(21,80,173,.23),transparent_44%),radial-gradient(ellipse_at_0%_65%,rgba(36,83,140,.13),transparent_42%)]"/>
    <section className="relative mx-auto grid min-h-[640px] max-w-[1380px] items-center gap-3 px-5 pb-20 pt-16 md:px-10 lg:grid-cols-[1.08fr_.92fr] lg:py-20">
      <div className="relative z-10">
        <p className="mb-7 flex items-center gap-3 text-[10px] font-bold uppercase tracking-[.28em] text-[#7dc8ff]"><span className="h-px w-9 bg-[#72c8ff]"/>{content.eyebrow}</p>
        <h1 className="max-w-[780px] text-[clamp(3.4rem,5.8vw,6.8rem)] font-semibold leading-[.96] tracking-[-.064em]">
          {content.title} <span className={"bg-gradient-to-r bg-clip-text text-transparent " + content.accent}>{content.highlight}</span>
        </h1>
        <p className="mt-7 max-w-[650px] text-base leading-8 text-[#b6c6dc] md:text-lg">{content.description}</p>
        <div className="mt-9 flex flex-wrap gap-3">
          <a href="/commercial" className="inline-flex items-center gap-2 rounded-full bg-[#83c9ff] px-6 py-4 text-sm font-bold text-[#031326] transition hover:bg-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-white">
            {sector === "roofing" ? "Request a roofing demand assessment" : "Discuss solar demand"} <ArrowUpRight className="size-4"/>
          </a>
          <a href="#qualification" className="inline-flex items-center gap-2 rounded-full border border-[#a3ccf2]/25 px-6 py-4 text-sm font-semibold text-[#d5e9ff] transition hover:border-[#a3ccf2]/70">How qualification works <ChevronRight className="size-4"/></a>
        </div>
        <p className="mt-6 max-w-lg text-xs leading-6 text-[#8ea0bd]">Evidence-led research and nonbinding consultation. No claim of available or payable enquiries.</p>
      </div>
      <div className="relative mx-auto w-full max-w-[650px] self-center">
        <div className="absolute inset-[10%] rounded-full bg-[#1b6ad0]/15 blur-[100px]"/>
        <div className="relative aspect-[6/5] overflow-hidden rounded-[2.4rem] border border-[#82bfff]/[.13] bg-[linear-gradient(150deg,rgba(42,97,172,.19),rgba(4,13,31,.91)_65%)] shadow-[0_25px_110px_rgba(0,0,0,.45)]">
          <img
            src={sector === "solar" ? solarHero.src : roofingHero.src}
            alt={sector === "solar" ? "Real solar arrays illuminated by a warm sunset" : "Roofing contractors fitting roof tiles during a real installation"}
            width={sector === "solar" ? solarHero.width : roofingHero.width}
            height={sector === "solar" ? solarHero.height : roofingHero.height}
            loading="eager"
            fetchPriority="high"
            className="absolute inset-0 h-full w-full object-cover object-center"
          />
          <div className={sector === "solar"
            ? "pointer-events-none absolute inset-0 bg-[linear-gradient(180deg,rgba(3,13,28,.08)_10%,rgba(2,9,23,.2)_53%,rgba(1,7,19,.86)_100%)]"
            : "pointer-events-none absolute inset-0 bg-[linear-gradient(145deg,rgba(2,11,31,.42),rgba(10,57,115,.18)_44%,rgba(2,8,24,.84)_100%)]"} />
          <div className="pointer-events-none absolute inset-0 shadow-[inset_0_0_100px_20px_rgba(1,7,24,.5)]" />
          <span className="absolute bottom-6 left-6 rounded-full border border-white/20 bg-[#061329]/85 px-4 py-2 text-[10px] font-bold uppercase tracking-[.16em] text-[#c6deff] backdrop-blur-xl">{sector === "solar" ? "Solar territory / Property evidence" : "Roofing / Weather / Service Area"}</span>
        </div>
      </div>
    </section>

    <section className="relative border-y border-[#8fc6ff]/[.12] bg-[#07142b]/50">
      <div className="mx-auto grid max-w-[1380px] gap-7 px-5 py-12 md:grid-cols-3 md:px-10">
        {content.sectors.map((item, index) => <div key={item} className="flex items-start gap-4">
          <span className="mt-1 text-xs font-bold text-[#71bcf7]">0{index + 1}</span>
          <p className="max-w-sm text-sm leading-6 text-[#d3e2f5]">{item}</p>
        </div>)}
      </div>
    </section>

    <section id="signals" className="relative mx-auto max-w-[1380px] px-5 py-24 md:px-10 lg:py-32">
      <div className="grid items-end gap-8 lg:grid-cols-[.9fr_1.1fr]">
        <div>
          <p className="text-[11px] font-bold uppercase tracking-[.2em] text-[#76c3fc]">Signal layers</p>
          <h2 className="mt-5 text-[clamp(2.4rem,4vw,4.5rem)] font-semibold leading-[1.02] tracking-[-.05em]">Evidence before opinion.</h2>
        </div>
        <p className="max-w-3xl text-base leading-8 text-[#a9bdd5]">{page.summary}</p>
      </div>
      <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {page.signals.map((signal, index) => <article key={signal} className="rounded-2xl border border-[#82bfff]/[.15] bg-[#0a1a33]/65 p-6">
          <span className="text-[11px] font-bold text-[#75bfff]">0{index + 1}</span>
          <h3 className="mt-6 text-base font-semibold leading-7 text-[#e3f1ff]">{signal}</h3>
        </article>)}
      </div>
    </section>
    <section className="relative border-y border-white/10 bg-[linear-gradient(130deg,rgba(4,26,60,.85),rgba(3,10,26,.96))]">
      <div className="mx-auto grid max-w-[1380px] gap-14 px-5 py-24 md:px-10 lg:grid-cols-2 lg:py-32">
        <div>
          <p className="text-[11px] font-bold uppercase tracking-[.2em] text-[#76c3fc]">Questions that matter</p>
          <div className="mt-8 space-y-4">
            {page.questions.map((question, index) => <p key={question} className="flex gap-4 border-b border-[#82bfff]/[.15] pb-4 text-sm leading-7 text-[#c4d9f0]">
              <span className="text-xs font-semibold text-[#79c5ff]">Q{index + 1}</span>{question}
            </p>)}
          </div>
        </div>
        <div>
          <p className="text-[11px] font-bold uppercase tracking-[.2em] text-[#76c3fc]">Forecast horizon</p>
          <h2 className="mt-5 text-[clamp(2rem,3.4vw,3.6rem)] font-semibold leading-tight tracking-[-.04em]">Now, next quarter, and the next two years.</h2>
          <div className="mt-8 grid gap-3">
            {page.forecast.map((forecast, index) => <div key={forecast} className="flex items-center gap-4 rounded-xl border border-[#6eaaff]/[.15] bg-[#08182f]/80 p-5">
              <span className="text-xs font-bold text-[#7abdf0]">0{index + 1}</span>
              <p className="text-sm font-semibold text-[#d4e5f9]">{forecast}</p>
            </div>)}
          </div>
          <p className="mt-5 text-xs leading-6 text-[#9eb6d1]">Forecasts remain estimates, not verified transactions, appointments, installations or revenue.</p>
        </div>
      </div>
    </section>
    <section className="relative mx-auto max-w-[1380px] px-5 py-24 md:px-10 lg:py-32">
      <p className="text-[11px] font-bold uppercase tracking-[.2em] text-[#76c3fc]">Potential intelligence applications</p>
      <h2 className="mt-5 text-[clamp(2.4rem,4vw,4.5rem)] font-semibold leading-tight tracking-[-.04em]">Intelligence you can use.</h2>
      <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {page.products.map((product) => <article key={product} className="rounded-[1.5rem] border border-[#82bfff]/[.16] bg-white/[.035] p-7">
          <h3 className="text-lg font-semibold leading-7 text-[#e7f4ff]">{product}</h3>
        </article>)}
      </div>
      <p className="mt-7 max-w-3xl text-xs leading-6 text-[#a9bdd5]">These are possible research applications, not proof that every example is available to purchase. Confirm actual catalogue scope and current delivery readiness before an engagement.</p>
    </section>
    <section id="qualification" className="relative mx-auto grid max-w-[1380px] gap-14 px-5 py-24 md:px-10 lg:grid-cols-2 lg:py-32">
      <div>
        <p className="text-[11px] font-bold uppercase tracking-[.2em] text-[#76c3fc]">Buyer-first qualification</p>
        <h2 className="mt-5 max-w-xl text-[clamp(2.5rem,4.1vw,4.7rem)] font-semibold leading-[1.02] tracking-[-.052em]">{sector === "roofing" ? "What makes a commercial roofing lead qualified?" : "What must be true before a lead has value?"}</h2>
        <p className="mt-6 max-w-xl leading-8 text-[#9cb1ca]">A traffic report is not buyer acceptance. Define eligible geography, the evidence needed for an enquiry, and the exact downstream commercial event before valuing it.</p>
        <a href={content.related.href} className="mt-7 inline-flex items-center gap-2 text-sm font-semibold text-[#92d4ff]">{content.related.label}<ArrowUpRight className="size-4"/></a>
      </div>
      <div className="space-y-4">
        {content.inquiries.map((question, index) => <article key={question} className="rounded-2xl border border-[#8bb5ef]/[.16] bg-white/[.035] p-6">
          <span className="text-[11px] font-bold text-[#70bbfa]">QUESTION 0{index + 1}</span>
          <h3 className="mt-3 text-lg font-semibold leading-snug text-[#e3f1ff]">{question}</h3>
        </article>)}
      </div>
    </section>

    <section className="relative border-y border-white/10 bg-[linear-gradient(120deg,rgba(6,30,67,.98),rgba(3,9,23,.98))]">
      <div className="mx-auto max-w-[1380px] px-5 py-24 md:px-10">
        <p className="text-[11px] font-bold uppercase tracking-[.2em] text-[#76c3fc]">The evidence-to-proposal journey</p>
        <h2 className="mt-5 text-[clamp(2.4rem,4.2vw,4.4rem)] font-semibold tracking-[-.05em]">A qualified decision. Not a promise.</h2>
        <div className="mt-11 grid gap-4 md:grid-cols-3">
          {content.process.map((step, index) => <article key={step} className="rounded-[1.5rem] border border-[#6eaaff]/[.19] bg-[#0b1d3a]/70 p-7">
            <CheckCircle2 className="mb-9 size-5 text-[#8acbff]"/>
            <span className="block text-[10px] font-bold tracking-[.22em] text-[#6eaaff]">STEP 0{index + 1}</span>
            <h3 className="mt-3 text-lg font-semibold text-[#f0f7ff]">{step}</h3>
          </article>)}
        </div>
      </div>
    </section>
    {buyerEditorial && <IndustryBuyerEditorialSection industry={sector} editorial={buyerEditorial}/>}
    <SectorOpportunityExplorer sector={sector}/>
    <section aria-labelledby="industry-research-links" className="relative mx-auto max-w-[1380px] px-5 py-20 md:px-10">
      <p className="text-[11px] font-bold uppercase tracking-[.2em] text-[#76c3fc]">Related research and answers</p>
      <h2 id="industry-research-links" className="mt-4 max-w-3xl text-3xl font-semibold tracking-[-.03em] md:text-5xl">Follow the evidence into a connected market.</h2>
      <p className="mt-5 max-w-3xl text-sm leading-7 text-[#a9bdd5]">Related first-party research helps frame questions; it is not proof of leads, buyers, revenue or outcomes.</p>
      <div className="mt-8 grid gap-4 md:grid-cols-2">
        {relatedResearch.map((link) => <article key={link.href} className="rounded-2xl border border-[#87baff]/[.18] bg-[#08162e]/70 p-6">
          <h3 className="text-lg font-semibold"><a href={link.href} className="text-[#dbefff] underline decoration-[#76c3fc]/50 underline-offset-4">{link.label}</a></h3>
          <p className="mt-3 text-sm leading-7 text-[#9fb6d1]">{link.context}</p>
        </article>)}
      </div>
      <div className="mt-7 flex flex-wrap gap-4 text-sm text-[#b8dcfa]">
        <a href="/industries">All industries</a>
      </div>
    </section>
    <div className="relative mx-auto max-w-[1380px] px-5 text-sm text-[#b8dcfa] md:px-10">
      {sector === "roofing" ? <a href="/industries/property">Property intelligence</a> : <a href="/industries/hvac">HVAC intelligence</a>}
    </div>
    <section aria-label="Discuss sector requirements" className="relative mx-auto max-w-[1380px] px-5 py-20 md:px-10">
      <div className="flex flex-col items-start justify-between gap-8 rounded-3xl border border-[#659ada]/[.25] bg-[radial-gradient(circle_at_88%_20%,rgba(63,130,217,.18),transparent_42%)] p-8 md:flex-row md:items-end md:p-12">
        <div className="max-w-2xl">
          <ShieldCheck className="size-6 text-[#89d1ff]"/>
          <h2 className="mt-5 text-3xl font-semibold tracking-[-.03em] md:text-5xl">See the evidence. Then decide.</h2>
          <p className="mt-4 text-sm leading-7 text-[#a9bdd5]">{content.disclosures}</p>
        </div>
        <a href="/commercial" className="inline-flex shrink-0 items-center gap-2 rounded-full bg-[#b3dcff] px-6 py-4 text-sm font-bold text-[#051329] hover:bg-white">Start a conversation <ArrowUpRight className="size-4"/></a>
      </div>
    </section>
  </main>;
}
