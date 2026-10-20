import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight, Check, House, ShieldCheck } from "lucide-react";
import GuideSignup from "./signup";

export const metadata: Metadata = {
  title: "Free Roofing Repair Cost Checklist | Empire AI",
  description: "A free homeowner guide to comparing roofing estimates, repair scopes, warranties and the questions to ask a contractor. No email needed to read.",
  alternates: { canonical: "/roofing/cost-guide" },
  robots: { index: true, follow: true },
};

const steps = [
  ["1", "Describe the problem", "Note leaks, missing materials or storm damage. Take photos from a safe position on the ground. Never climb onto an unsafe roof."],
  ["2", "Ask for a written scope", "Compare what work is included, materials, repair area, disposal, site clean-up, start date and whether inspection fees apply."],
  ["3", "Check the cost drivers", "Roof size, pitch, access, local labour, materials, permits and hidden decking damage can affect the final quote."],
  ["4", "Verify the contractor", "Ask about locally required licensing, appropriate insurance, workmanship guarantees, warranties and payment milestones."],
  ["5", "Compare like for like", "Get itemised written proposals for the same scope. Ask how unexpected costs will be discussed and approved before work starts."],
] as const;

export default function RoofingCostGuidePage() {
  return <main className="min-h-screen bg-[#f4f8ff] text-[#071c3c]">
    <header className="bg-gradient-to-r from-[#04142e] via-[#08295b] to-[#0b4c97] text-white print:hidden">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-5 py-5 sm:px-8">
        <Link href="/roofing" className="text-sm font-semibold text-[#c3e9ff] hover:text-white">← Roofing service information</Link>
        <span className="rounded-full border border-[#64e2ff]/40 px-3 py-2 text-[11px] font-bold uppercase tracking-[.14em]">EMPIRE AI · HOMEOWNER GUIDE</span>
      </div>
    </header>
    <section className="border-b border-[#cfe3f9] bg-gradient-to-br from-[#dceeff] via-white to-[#e9f5ff]">
      <div className="mx-auto grid max-w-6xl gap-10 px-5 py-14 sm:px-8 sm:py-20 lg:grid-cols-[1.15fr_.85fr] lg:items-center">
        <div>
          <p className="text-xs font-extrabold uppercase tracking-[.2em] text-[#0765cb]">FREE ROOFING COST CHECKLIST</p>
          <h1 className="mt-5 text-4xl font-extrabold leading-tight tracking-[-.045em] sm:text-6xl">Know what to ask before paying for roof repairs.</h1>
          <p className="mt-6 text-lg leading-8 text-[#385575]">A practical, no-obligation guide for homeowners comparing roofing quotes. No email address, signup, or purchase is needed to read or print this information.</p>
          <a href="#checklist" className="mt-7 inline-flex items-center gap-3 rounded-xl bg-[#046bd2] px-6 py-4 font-bold text-white print:hidden">
            Read the free checklist <ArrowRight className="h-4 w-4" />
          </a>
        </div>
        <aside className="rounded-3xl border border-[#bfdefa] bg-white p-7 shadow-[0_20px_55px_rgba(17,74,132,.1)] sm:p-9">
          <House className="h-9 w-9 text-[#0475d9]" />
          <h2 className="mt-4 text-2xl font-extrabold">Inside the guide</h2>
          <ul className="mt-5 space-y-4 text-sm text-[#42607e]">
            {["Five questions before you hire a roofer","What changes a roofing quote","How to compare written estimates","Insurance and warranty checks"].map(x=><li className="flex gap-3" key={x}><Check className="h-4 w-4 shrink-0 text-[#058cd9]" />{x}</li>)}
          </ul>
          <p className="mt-6 border-t border-[#e3edf8] pt-4 text-xs leading-6 text-[#5b7290]">General information, not an inspection, contractor endorsement or guaranteed price.</p>
        </aside>
      </div>
    </section>
    <section id="checklist" className="mx-auto max-w-6xl px-5 py-16 sm:px-8">
      <div className="max-w-3xl">
        <p className="text-xs font-bold tracking-[.16em] text-[#0565c6]">YOUR FIVE-STEP CHECKLIST</p>
        <h2 className="mt-3 text-3xl font-extrabold tracking-[-.04em] sm:text-4xl">Compare quotes with confidence.</h2>
        <p className="mt-4 text-base leading-7 text-[#496482]">You can use this checklist when comparing repairs or a full roof replacement. A site inspection is needed for reliable local pricing.</p>
      </div>
      <div className="mt-9 grid gap-4 md:grid-cols-2">
        {steps.map(([n,title,detail])=><article key={n} className="rounded-2xl border border-[#d5e4f4] bg-white p-7">
          <span className="text-xs font-extrabold text-[#056cda]">{n.padStart(2,"0")}</span>
          <h3 className="mt-2 text-xl font-bold">{title}</h3>
          <p className="mt-3 text-sm leading-7 text-[#455f7c]">{detail}</p>
        </article>)}
      </div>
      <div className="mt-10 rounded-2xl border border-[#c5e0fa] bg-[#e9f5ff] p-7">
        <h2 className="text-xl font-bold">Save a copy</h2>
        <p className="mt-2 text-sm leading-7 text-[#405f80]">Press Ctrl+P or Cmd+P in your browser and choose “Save as PDF”, or print the checklist for your contractor conversations.</p>
      </div>
    </section>
    <GuideSignup />
    <section className="mx-auto max-w-6xl px-5 pb-20 sm:px-8 print:hidden">
      <div className="rounded-3xl bg-[#062957] p-8 text-white sm:p-11">
        <ShieldCheck className="h-8 w-8 text-[#7fe5ff]" />
        <h2 className="mt-4 text-2xl font-bold">Want to see if a roofing call is available?</h2>
        <p className="mt-3 max-w-2xl text-sm leading-7 text-[#d1e8ff]">You can separately check ZIP eligibility on our roofing page. The call option, if available, remains subject to its own consent and recording disclosures. No automatic dialling.</p>
        <Link href="/roofing#roofing-zip-check-heading" className="mt-6 inline-flex min-h-12 items-center gap-2 rounded-xl bg-[#6ce0ff] px-6 py-3 font-bold text-[#062957]">
          Check my ZIP <ArrowRight className="h-4 w-4" />
        </Link>
      </div>
    </section>
  </main>;
}
