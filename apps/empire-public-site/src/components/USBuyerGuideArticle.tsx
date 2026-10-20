import { ArrowRight, ArrowUpRight, CheckCheck, ShieldCheck, FileSearch, ClipboardList, Info } from "lucide-react";
import type { BuyerGuide } from "@/lib/us-buyer-guides";

// The live site has a reachable B2B form but no reliable proposal-heading anchor yet.
const proposal = "/commercial";

function SectionNav({ guide }: { guide: BuyerGuide }) {
  return <nav aria-label="Guide sections" className="rounded-2xl border border-sky-300/15 bg-[#09162b]/90 p-5">
    <p className="mb-4 text-xs font-semibold uppercase tracking-[.17em] text-sky-300">Jump to a section</p>
    <ol className="grid gap-3 text-sm text-slate-300">
      <li><a className="hover:text-white" href="#evidence-ladder">Evidence ladder</a></li>
      {guide.sections.map((section, i) =>
        <li key={section.heading}><a className="hover:text-white" href={`#guide-section-${i+1}`}>{section.heading}</a></li>)}
      <li><a className="hover:text-white" href="#frequently-asked">Frequently asked questions</a></li>
    </ol>
  </nav>;
}

export default function USBuyerGuideArticle({ guide }: { guide: BuyerGuide }) {
  const related = `/industries/${guide.industry}`;
  return <main className="empire-surface min-h-screen bg-[#020817] text-slate-100">
    <header className="relative isolate overflow-hidden border-b border-cyan-300/20">
      <div className="pointer-events-none absolute inset-0 -z-20 bg-cover bg-center opacity-35"
        style={{ backgroundImage: "url('/art/earth-detail-v2.webp')" }} aria-hidden="true"/>
      <div className="pointer-events-none absolute inset-0 -z-10 bg-[linear-gradient(102deg,#020817_1%,rgba(2,8,23,.94)_52%,rgba(2,8,23,.58)_100%)]" />
      <div className="mx-auto max-w-7xl px-5 pb-20 pt-16 sm:px-10 sm:pt-24 lg:px-12">
        <nav aria-label="Breadcrumb" className="mb-11 flex flex-wrap items-center gap-2 text-xs text-slate-300">
          <a href="/" className="hover:text-white">Empire AI</a><span aria-hidden="true">/</span>
          <a href={related} className="hover:text-white">{guide.industry === "roofing" ? "Roofing intelligence" : "Solar intelligence"}</a>
          <span aria-hidden="true">/</span><span className="text-cyan-200">Guide</span>
        </nav>
        <div className="max-w-5xl">
          <p className="mb-6 flex items-center gap-3 text-xs font-semibold uppercase tracking-[.18em] text-cyan-300">
            <FileSearch size={18} aria-hidden="true" /> {guide.eyebrow}
          </p>
          <h1 className="max-w-5xl text-[clamp(2.45rem,5.4vw,5.4rem)] font-semibold leading-[1.07] tracking-[-.049em] text-white">
            {guide.title}
          </h1>
          <p className="mt-6 max-w-3xl text-xl font-medium text-amber-200">{guide.accent}</p>
          <p className="mt-5 max-w-3xl text-base leading-8 text-slate-200 sm:text-lg">{guide.description}</p>
          <div className="mt-9 flex flex-wrap gap-4">
            <a href={proposal} className="inline-flex min-h-12 items-center gap-3 rounded-full bg-amber-300 px-6 py-3 text-sm font-bold text-[#06112c] transition hover:bg-white focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-sky-300">
              Request a business assessment <ArrowRight size={18} aria-hidden="true"/>
            </a>
            <a href={related} className="inline-flex min-h-12 items-center gap-2 rounded-full border border-sky-300/35 px-6 py-3 text-sm font-semibold text-sky-100 transition hover:border-white hover:text-white">
              Explore {guide.industry} intelligence <ArrowUpRight size={17} aria-hidden="true"/>
            </a>
          </div>
          <p className="mt-5 max-w-2xl text-xs leading-6 text-slate-400">
            For business operators and commercial teams. Nonbinding enquiry only; no consumer intake, order or payment.
          </p>
        </div>
      </div>
    </header>

    <div className="mx-auto grid max-w-7xl gap-12 px-5 py-14 sm:px-10 lg:grid-cols-[250px_minmax(0,1fr)] lg:gap-16 lg:px-12">
      <aside className="h-fit lg:sticky lg:top-7">
        <SectionNav guide={guide} />
        <div className="mt-5 rounded-2xl border border-amber-200/20 bg-amber-300/[.045] p-5">
          <ShieldCheck size={22} className="mb-3 text-amber-200" aria-hidden="true"/>
          <p className="text-sm font-semibold text-white">Evidence before forecasts</p>
          <p className="mt-2 text-xs leading-6 text-slate-300">{guide.disclaimer}</p>
        </div>
      </aside>
      <article className="min-w-0 space-y-14">
        <section aria-label="Who this guide is for" className="grid gap-5 rounded-2xl border border-cyan-300/20 bg-[#081a30] p-6 md:grid-cols-2 md:p-8">
          <div><span className="text-xs font-semibold uppercase tracking-[.14em] text-cyan-300">Designed for</span>
            <p className="mt-3 text-sm leading-7 text-slate-100">{guide.audience}</p>
          </div>
          <div><span className="text-xs font-semibold uppercase tracking-[.14em] text-cyan-300">Core distinction</span>
            <p className="mt-3 text-sm leading-7 text-slate-100">{guide.focus}</p>
          </div>
        </section>
        <p className="max-w-3xl text-lg leading-9 text-slate-200">{guide.lead}</p>
        <section id="evidence-ladder" className="scroll-mt-28">
          <p className="mb-3 text-xs font-semibold uppercase tracking-[.16em] text-sky-300">Decision framework</p>
          <h2 className="text-3xl font-semibold tracking-tight text-white sm:text-4xl">Six stages: what the evidence really proves</h2>
          <p className="mt-4 max-w-3xl text-base leading-8 text-slate-300">Use these stages to separate early interest from qualified, accepted and paid commercial outcomes.</p>
          <div className="mt-7 overflow-x-auto rounded-2xl border border-white/15">
            <table className="w-full min-w-[690px] border-collapse text-left text-sm leading-7">
              <thead className="bg-cyan-300/[.09] text-cyan-100"><tr>
                <th scope="col" className="w-1/4 p-4">Stage</th><th scope="col" className="p-4">Evidence to check</th><th scope="col" className="p-4">What is not sufficient</th>
              </tr></thead>
              <tbody>{guide.steps.map((step) => <tr key={step.name} className="border-t border-white/10">
                <th scope="row" className="p-4 align-top font-semibold text-amber-100">{step.name}</th>
                <td className="p-4 align-top text-slate-200">{step.evidence}</td>
                <td className="p-4 align-top text-slate-400">{step.notEnough}</td>
              </tr>)}</tbody>
            </table>
          </div>
        </section>
        {guide.sections.map((section, i) => <section key={section.heading} id={`guide-section-${i+1}`} className="scroll-mt-28">
          <p className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-[.16em] text-sky-300">
            <ClipboardList size={16} aria-hidden="true"/> Practical qualification · {i+1}
          </p>
          <h2 className="text-2xl font-semibold tracking-tight text-white sm:text-3xl">{section.heading}</h2>
          <div className="mt-5 space-y-5">
            {section.paragraphs.map(paragraph => <p key={paragraph} className="text-base leading-8 text-slate-300">{paragraph}</p>)}
          </div>
          {section.checks && <div className="mt-7 rounded-2xl border border-sky-300/20 bg-sky-300/[.045] p-6">
            <h3 className="mb-5 flex items-center gap-2 text-lg font-semibold text-slate-100">
              <CheckCheck size={19} className="text-cyan-300" aria-hidden="true"/> Review checklist
            </h3>
            <ul className="space-y-3 text-sm leading-7 text-slate-200">
              {section.checks.map(check => <li key={check} className="flex items-start gap-3">
                <span aria-hidden="true" className="mt-2 size-1.5 shrink-0 rounded-full bg-amber-300"/>
                <span>{check}</span>
              </li>)}
            </ul>
          </div>}
        </section>)}
        <section id="frequently-asked" className="scroll-mt-28">
          <h2 className="text-3xl font-semibold tracking-tight text-white">Frequently asked questions</h2>
          <div className="mt-6 divide-y divide-white/10 border-y border-white/10">
            {guide.faq.map(item => <div key={item.question} className="py-5">
              <h3 className="text-lg font-semibold text-amber-100">{item.question}</h3>
              <p className="mt-3 text-sm leading-7 text-slate-300">{item.answer}</p>
            </div>)}
          </div>
        </section>
        <section aria-labelledby="business-proposal-cta" className="overflow-hidden rounded-3xl border border-cyan-300/25 bg-[linear-gradient(120deg,#0b3664,#061126_72%)] p-7 sm:p-10">
          <p className="text-xs font-semibold uppercase tracking-[.15em] text-cyan-200">Next step for businesses</p>
          <h2 id="business-proposal-cta" className="mt-4 text-2xl font-semibold tracking-tight text-white sm:text-3xl">
            Bring us your business problem. We’ll review the evidence first.
          </h2>
          <p className="mt-5 max-w-2xl text-base leading-8 text-slate-200">
            Tell us your service region, current lead or appointment definition, existing systems and the decision you need to make. If there is a credible fit, the next step is an email discussion and a nonbinding founder-reviewed proposal—not an automatic sale or promised lead volume.
          </p>
          <a href={proposal} className="mt-7 inline-flex min-h-12 items-center gap-3 rounded-full bg-amber-300 px-6 py-3 text-sm font-bold text-[#06112c] hover:bg-white focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-sky-300">
            Request a founder-reviewed proposal <ArrowRight size={18} aria-hidden="true"/>
          </a>
          <p className="mt-5 text-xs leading-6 text-slate-300">
            Business enquiries only. Contact consent is collected on the existing commercial form. See <a className="text-sky-200 underline underline-offset-4" href="/privacy">privacy</a> and <a className="text-sky-200 underline underline-offset-4" href="/trust">our trust commitments</a>.
          </p>
        </section>
        <aside className="flex items-start gap-3 rounded-xl border border-amber-200/10 p-4 text-xs leading-6 text-slate-400">
          <Info size={19} aria-hidden="true" className="mt-1 shrink-0 text-amber-200"/>
          <p>{guide.disclaimer} This article does not collect individual consumer contact details and does not certify partner capacity.</p>
        </aside>
      </article>
    </div>
  </main>;
}
