import type { Metadata } from "next";
import {
  ArrowDownRight,
  ArrowRight,
  BadgeCheck,
  ClipboardCheck,
  Droplets,
  Hammer,
  Home,
  ShieldCheck,
  Wind,
} from "lucide-react";

/**
 * First-party UK homeowner roofing editorial preview.
 *
 * NOT released: the production public gateway does not admit /uk/roofing.
 * No affiliate outbound redirect, form submission, phone call, API or tracking.
 * A later separately reviewed partner release must implement attribution,
 * disclosures, legal policy links and consent requirements from real evidence.
 */
export const metadata: Metadata = {
  title: "UK Roofing | Plan a Repair or Replacement — Empire AI",
  description:
    "A practical, independent checklist for UK homeowners comparing roof repair and replacement options. Prelaunch review copy; no quotes or matching service offered.",
  alternates: { canonical: "/uk/roofing" },
  robots: { index: false, follow: false, googleBot: { index: false, follow: false } },
  openGraph: {
    title: "Understand the roof work before requesting a quote | Empire AI",
    description: "Independent UK roofing homeowner checklist. Prelaunch editorial preview.",
    url: "/uk/roofing",
    type: "website",
  },
};

const enquiries = [
  {
    name: "Roof repairs",
    detail:
      "Describe the affected area, the visible symptoms and when the problem began. A qualified tradesperson needs to assess the cause.",
    icon: Hammer,
  },
  {
    name: "Roof replacement",
    detail:
      "Ask what is being replaced, how the roof structure will be checked, and how weatherproofing and waste removal will be handled.",
    icon: Home,
  },
  {
    name: "Flat roofing",
    detail:
      "Clarify the roof covering, drainage, roof access and any visible ponding before asking for an assessment.",
    icon: Droplets,
  },
  {
    name: "Storm-related damage",
    detail:
      "Record what you can observe safely from the ground. Avoid climbing onto a potentially damaged roof.",
    icon: Wind,
  },
];

const steps = [
  {
    num: "01",
    title: "Describe the job",
    detail: "Explain the roof type, approximate age if known, property type and visible issue.",
  },
  {
    num: "02",
    title: "Compare the scope",
    detail: "Ask for the work specification, materials, estimated timing, access and disposal arrangements.",
  },
  {
    num: "03",
    title: "Check the tradesperson",
    detail: "Confirm relevant insurance, written quotations, references and how any guarantees are provided.",
  },
];

const questions = [
  "Is a targeted repair reasonable, or does the roof need more extensive work?",
  "Does the quotation clearly separate labour, materials, access and waste costs?",
  "Who is responsible for scaffolding, protection and leaving the site tidy?",
  "What should happen if hidden damage is discovered after work begins?",
  "Are any permissions or building-control notifications likely to be relevant?",
];

export default function UkRoofingEditorialPreview() {
  return (
    <main className="min-h-screen bg-[#f5f9ff] text-[#092347] [font-family:ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,'Segoe_UI',sans-serif]">
      <header className="border-b border-[#2461af] bg-[#061a38] text-white">
        <div className="mx-auto flex max-w-[1260px] flex-wrap items-center justify-between gap-4 px-5 py-5 sm:px-8">
          <div className="flex items-center gap-3">
            <img
              src="/brand/empire-mark.svg"
              alt="Empire AI"
              width={40}
              height={40}
              className="h-10 w-10 rounded-lg border border-[#54caff]/30 bg-white/5 p-1"
            />
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#56d8ff]">Empire AI</p>
              <p className="text-sm font-semibold">UK Roofing Guide</p>
            </div>
          </div>
          <span className="rounded-full border border-[#66caff]/35 bg-[#0b3670] px-4 py-2 text-xs font-semibold tracking-wide text-[#d6efff]">
            Prelaunch · editorial preview only
          </span>
        </div>
      </header>

      <section className="relative isolate overflow-hidden bg-[#061a38] text-white">
        <div aria-hidden="true" className="pointer-events-none absolute -right-20 top-0 h-[520px] w-[680px] rounded-full bg-[#087dfa]/20 blur-[90px]" />
        <div aria-hidden="true" className="pointer-events-none absolute -left-36 bottom-0 h-[350px] w-[500px] rounded-full bg-[#06bad2]/10 blur-[80px]" />
        <div className="relative mx-auto grid max-w-[1260px] gap-12 px-5 py-16 sm:px-8 sm:py-20 lg:grid-cols-[1.05fr_.95fr] lg:items-center lg:py-24">
          <div>
            <p className="inline-flex items-center gap-2 text-xs font-bold uppercase tracking-[0.21em] text-[#61d9fa]">
              <span className="h-2 w-2 rounded-full bg-[#54ecd0]" />
              UK homeowner roofing decisions
            </p>
            <h1 className="mt-6 max-w-[740px] text-[45px] font-bold leading-[1.08] tracking-[-0.055em] sm:text-[66px]">
              Know what your roof needs.
              <span className="block bg-gradient-to-r from-[#5fe1ff] to-[#69a8ff] bg-clip-text text-transparent">
                Then compare the right work.
              </span>
            </h1>
            <p className="mt-7 max-w-[575px] text-[17px] leading-8 text-[#d4e5fb]">
              From a persistent leak to a complete replacement, make a clearer
              roofing enquiry with a practical checklist for UK properties.
              This is information, not an inspection or contractor recommendation.
            </p>
            <div className="mt-9 flex flex-wrap gap-3">
              <a
                href="#roofing-checklist"
                className="inline-flex min-h-12 items-center gap-3 rounded-xl bg-[#d7f8ff] px-6 py-3 text-sm font-bold text-[#063b75] shadow-[0_16px_32px_rgba(3,8,22,.2)] hover:bg-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-white"
              >
                Read the homeowner checklist
                <ArrowRight className="h-4 w-4" aria-hidden="true" />
              </a>
              <a
                href="#roof-types"
                className="inline-flex min-h-12 items-center gap-2 rounded-xl border border-[#6993c4] px-5 py-3 text-sm font-semibold text-white hover:bg-white/10 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-white"
              >
                Explore common projects <ArrowDownRight className="h-4 w-4" aria-hidden="true" />
              </a>
            </div>
            <p className="mt-6 text-xs leading-6 text-[#a8c7eb]">
              Partner links, quotation submissions and call connections are not enabled on this preview.
            </p>
          </div>

          <aside className="relative rounded-[28px] border border-[#78b8f5]/35 bg-gradient-to-br from-[#103e77] via-[#0d2b56] to-[#092449] p-6 shadow-[0_35px_90px_rgba(0,7,29,.46)] sm:p-8">
            <div className="mb-8 flex items-center justify-between">
              <p className="text-xs font-extrabold uppercase tracking-[0.19em] text-[#76e0ff]">
                Before you request a quote
              </p>
              <ClipboardCheck className="h-6 w-6 text-[#7be6f7]" aria-hidden="true" />
            </div>
            <div className="space-y-4">
              {[
                ["01", "Identify the roof area", "Pitched or flat? Tiles, slate or another covering?"],
                ["02", "Describe the issue", "Leaks, missing materials, wear or planned replacement."],
                ["03", "Prepare the property details", "Town or postcode area, access constraints and timeframe."],
              ].map(([number, name, detail]) => (
                <div key={number} className="flex gap-4 border-b border-white/15 pb-4 last:border-0 last:pb-0">
                  <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[#134e91] text-sm font-bold text-[#8ae6ff]">
                    {number}
                  </span>
                  <div>
                    <h2 className="text-sm font-bold text-white">{name}</h2>
                    <p className="mt-1 text-sm leading-6 text-[#bfd3ea]">{detail}</p>
                  </div>
                </div>
              ))}
            </div>
            <div className="mt-8 rounded-2xl border border-[#97cfff]/30 bg-white/5 p-4">
              <p className="flex items-center gap-2 text-sm font-bold text-[#b0efff]">
                <ShieldCheck className="h-5 w-5" aria-hidden="true" /> Homeowner-first guidance
              </p>
              <p className="mt-2 text-xs leading-5 text-[#c5d8ed]">
                We do not currently collect roofing job details, transfer personal data to a lead buyer, or promise local contractor availability.
              </p>
            </div>
          </aside>
        </div>
      </section>

      <section id="roof-types" className="mx-auto max-w-[1260px] px-5 py-16 sm:px-8 sm:py-20">
        <p className="text-xs font-extrabold uppercase tracking-[0.2em] text-[#086ad6]">Plan the right enquiry</p>
        <h2 className="mt-3 max-w-3xl text-3xl font-bold tracking-[-0.045em] sm:text-4xl">
          Different roof problems call for different questions.
        </h2>
        <p className="mt-4 max-w-3xl text-sm leading-7 text-[#466383]">
          These examples help you describe a potential project. They do not confirm which types of jobs any affiliate partner currently accepts.
        </p>
        <div className="mt-8 grid gap-4 sm:grid-cols-2">
          {enquiries.map(({ name, detail, icon: Icon }) => (
            <article key={name} className="rounded-[24px] border border-[#d5e6f5] bg-white p-6 shadow-[0_10px_36px_rgba(6,41,82,.05)] sm:p-7">
              <div className="mb-5 flex h-12 w-12 items-center justify-center rounded-2xl bg-[#e4f5ff] text-[#0568ca]">
                <Icon className="h-6 w-6" aria-hidden="true" />
              </div>
              <h3 className="text-xl font-bold tracking-tight">{name}</h3>
              <p className="mt-3 text-sm leading-7 text-[#476384]">{detail}</p>
            </article>
          ))}
        </div>
      </section>

      <section id="roofing-checklist" className="border-y border-[#d8e9f9] bg-white">
        <div className="mx-auto max-w-[1260px] px-5 py-16 sm:px-8 sm:py-20">
          <p className="text-xs font-extrabold uppercase tracking-[0.2em] text-[#086ad6]">A clearer way to compare</p>
          <h2 className="mt-3 text-3xl font-bold tracking-[-0.045em] sm:text-4xl">Three steps before you commit.</h2>
          <div className="mt-8 grid gap-4 md:grid-cols-3">
            {steps.map((step) => (
              <div key={step.num} className="rounded-[24px] border border-[#d7e6f4] bg-[#f6faff] p-6 sm:p-7">
                <span className="text-3xl font-extrabold text-[#0874df]">{step.num}</span>
                <h3 className="mt-5 text-lg font-bold">{step.title}</h3>
                <p className="mt-3 text-sm leading-7 text-[#446080]">{step.detail}</p>
              </div>
            ))}
          </div>
          <div className="mt-9 rounded-[24px] border border-[#c9e1f8] bg-[#eef7ff] p-6 sm:p-8">
            <p className="flex items-center gap-2 text-lg font-bold">
              <BadgeCheck className="h-6 w-6 text-[#076ad3]" aria-hidden="true" />
              Questions worth asking
            </p>
            <ul className="mt-5 grid gap-3 sm:grid-cols-2">
              {questions.map((question) => (
                <li key={question} className="flex gap-3 text-sm leading-6 text-[#365674]">
                  <span aria-hidden="true" className="mt-2 h-2 w-2 shrink-0 rounded-full bg-[#0673de]" />
                  {question}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-[1260px] px-5 py-16 sm:px-8 sm:py-20">
        <div className="rounded-[28px] border border-[#2a72c5] bg-gradient-to-r from-[#082b56] to-[#0758ae] p-8 text-white sm:p-12">
          <p className="text-xs font-extrabold uppercase tracking-[0.19em] text-[#8be5fb]">
            UK roofing quote comparison · planned service
          </p>
          <h2 className="mt-3 max-w-2xl text-3xl font-bold tracking-[-0.04em] sm:text-4xl">
            A better enquiry starts with better information.
          </h2>
          <p className="mt-4 max-w-2xl text-sm leading-7 text-[#d9e8fa]">
            We are reviewing a potential paid affiliate arrangement. No matching
            service or quotation request is active on this page. Partner
            acceptance, consumer disclosure, applicable privacy notices,
            tracked-link attribution and commercial terms must be approved first.
          </p>
          <div
            role="note"
            aria-label="Planned affiliate advertisement disclosure"
            className="mt-7 max-w-2xl rounded-2xl border border-[#76d4fb]/40 bg-[#031c3e]/80 p-5"
          >
            <p className="inline-flex rounded-md bg-[#d5f7ff] px-3 py-1.5 text-xs font-extrabold uppercase tracking-[0.16em] text-[#062d54]">
              Ad · planned partner link (inactive)
            </p>
            <p className="mt-3 text-sm leading-7 text-[#e1efff]">
              If a MyJobQuote referral link is approved here, Empire AI may earn
              commission when a qualifying referral meets the agreed terms.
              No affiliate link is currently active and no job details are
              collected on this page.
            </p>
          </div>
          <button
            type="button"
            disabled
            aria-disabled="true"
            className="mt-7 inline-flex cursor-not-allowed items-center gap-3 rounded-xl border border-[#afdfff]/50 bg-[#bddcf3]/25 px-6 py-4 text-sm font-bold text-white/80"
          >
            Quote enquiry unavailable during affiliate review <ArrowRight className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>
      </section>

      <footer className="bg-[#041a34] px-5 py-9 text-[#bcd4ec] sm:px-8">
        <div className="mx-auto flex max-w-[1260px] flex-col justify-between gap-3 sm:flex-row">
          <p className="text-sm font-semibold text-white">Empire AI · UK homeowner information</p>
          <p className="max-w-3xl text-xs leading-6">
            Prelaunch editorial preview. Not a contractor, insurer, inspection service or live referral programme.
            Future affiliate links would be clearly disclosed if introduced following approval.
            No lead form, external affiliate link, telephone routing or paid advertising is enabled.
          </p>
        </div>
      </footer>
    </main>
  );
}
