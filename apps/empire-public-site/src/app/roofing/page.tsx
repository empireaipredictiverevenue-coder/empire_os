import type { Metadata } from "next";
import RoofingCoverageCheck from "./coverage-check";
import { ArrowRight, Check, ChevronRight, Droplets, FileText, House, MapPin, MessageSquareText, Phone, ShieldCheck, Wind } from "lucide-react";

// SEO-ready but deliberately withheld from indexing until every activation
// gate, buyer landing review and live-service evidence is independently met.
export const metadata: Metadata = {
  title: "Roof Replacement & Installation | Roofing ZIP Check",
  description:
    "Planning a roof replacement or installation? Check recent service-area guidance by ZIP. Independent contractor availability varies and is not guaranteed.",
  alternates: { canonical: "/roofing" },
  robots: { index: false, follow: false },
  openGraph: {
    title: "Roof Replacement & Installation Service Availability",
    description: "Review roofing service-area guidance for roof replacement and installation enquiries. Contractor availability varies by ZIP.",
    url: "/roofing",
    type: "website",
  },
  twitter: { card: "summary" },
};

// The hero sends homeowners to the existing ZIP-guidance and consent flow.
// The server checks call availability at submission time; no direct-dial link
// or static compilation flag can bypass the live controls.

const roofingNeeds = [
  [
    "Roof replacement or reroofing enquiry",
    "Provide the property ZIP code and explain the existing roof and replacement scope.",
  ],
  [
    "New roof installation enquiry",
    "Share the property location and proposed new-roof installation details.",
  ],
  [
    "Roof leak repair or water entry",
    "Describe where the issue is visible and when you first noticed it.",
  ],
  [
    "Storm-damaged roof inspection",
    "Explain what changed after the weather event and the current condition of the property.",
  ],
];

const steps = [
  [
    "01",
    "Describe the roofing need",
    "Identify the roofing issue or project and the property location.",
  ],
  [
    "02",
    "Confirm service-area eligibility",
    "Availability depends on the property ZIP code and current contractor capacity.",
  ],
  [
    "03",
    "Choose whether to call",
    "When an eligible call route is available, you decide whether to place the call.",
  ],
];

export default function RoofingServicePage() {
  const needs = [
    { name: roofingNeeds[0][0], info: roofingNeeds[0][1], Icon: House, tone: "from-[#d9edff] to-[#c7ecff]", ink: "text-[#0757ca]" },
    { name: roofingNeeds[1][0], info: roofingNeeds[1][1], Icon: FileText, tone: "from-[#d5fbff] to-[#b4f2f9]", ink: "text-[#004caa]" },
    { name: roofingNeeds[2][0], info: roofingNeeds[2][1], Icon: Droplets, tone: "from-[#dbfff1] to-[#c1f6e1]", ink: "text-[#07595c]" },
    { name: roofingNeeds[3][0], info: roofingNeeds[3][1], Icon: Wind, tone: "from-[#d8efff] to-[#bde7ff]", ink: "text-[#064bc0]" },
  ];
  const stepIcons = [MessageSquareText, MapPin, Phone];

  return (
    <main className="min-h-screen overflow-x-hidden bg-[#f8fbff] text-[#071a3a] [font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,'Segoe_UI',sans-serif]">
      <header className="relative z-20 border-b border-[#126ce5]/40 bg-gradient-to-r from-[#041630] via-[#082859] to-[#014fbb] text-white">
        <div className="mx-auto flex max-w-[1260px] flex-wrap items-center justify-between gap-3 px-5 py-4 sm:px-8">
          <div className="flex items-center gap-3" aria-label="Roofing service information">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl border border-[#24d5ff]/45 bg-[#1a80f9]/25 shadow-[0_0_22px_rgba(9,179,255,.24)]">
              <House className="h-5 w-5 text-[#61deff]" aria-hidden="true" />
            </span>
            <span className="text-sm font-bold uppercase tracking-[0.18em] sm:text-base">Roofing service information</span>
          </div>
          <span className="rounded-full border border-[#5dddff] bg-[#0559bf] px-3 py-2 text-[10px] font-bold uppercase tracking-[0.11em] text-white shadow-[inset_0_0_14px_rgba(39,210,255,.26)] sm:px-5 sm:text-xs">
            Review only · Traffic disabled
          </span>
          <span className="hidden text-xs text-[#dcefff] xl:block">No live calls · no routing · no spend</span>
        </div>
      </header>

      <section className="relative isolate overflow-hidden border-b border-[#cce4fc] bg-[#eaf5ff]">
        {/* Image is a self-hosted crop of the founder-owned buyer review mockup. */}
        <div className="pointer-events-none absolute inset-y-0 right-0 w-[64%] opacity-70 sm:w-[53%] sm:opacity-90 lg:w-[52%]" aria-hidden="true">
          <img src="/roofing-hero.webp" alt="" className="h-full w-full object-cover object-[50%_48%]" />
        </div>
        <div aria-hidden="true" className="pointer-events-none absolute inset-0 bg-gradient-to-r from-white via-white/95 to-white/20 lg:via-white/80 lg:to-white/5" />
        <div aria-hidden="true" className="pointer-events-none absolute inset-x-0 bottom-0 h-20 bg-gradient-to-t from-[#f8fbff] to-transparent" />
        <div className="relative mx-auto grid max-w-[1260px] gap-9 px-5 pb-12 pt-12 sm:px-8 sm:pb-16 sm:pt-16 lg:grid-cols-[1.12fr_.88fr] lg:items-center lg:gap-14 lg:pb-20 lg:pt-20">
          <div className="max-w-[650px]">
            <p className="text-xs font-extrabold uppercase tracking-[0.23em] text-[#0667df] sm:text-sm">Roofing service information</p>
            <h1 className="mt-5 max-w-[660px] text-[42px] font-extrabold leading-[1.02] tracking-[-0.055em] text-[#061633] sm:text-[60px] lg:text-[69px]">
              Planning a roof replacement or installation?
            </h1>
            <p className="mt-6 max-w-[610px] text-[17px] leading-[1.65] text-[#345078] sm:text-[19px]">
              Check whether your property's ZIP code appears in recent roofing coverage guidance for roof installation or replacement. Other roofing issues may be considered, but a local contractor or live call route is not guaranteed.
            </p>
            <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:flex-wrap">
              <a
                href="#roofing-zip-check-heading"
                className="inline-flex min-h-14 items-center justify-center gap-4 rounded-xl bg-gradient-to-b from-[#0fb3ff] via-[#087af5] to-[#0057d8] px-7 py-4 text-center text-base font-bold text-white shadow-[0_11px_24px_rgba(0,94,223,.25)]"
              >
                Check ZIP &amp; request a roofing call <ArrowRight className="h-5 w-5" aria-hidden="true" />
              </a>
              <a href="#how-it-works" className="inline-flex min-h-14 items-center justify-center gap-2 rounded-xl border border-[#b7d6ef] bg-white/90 px-5 py-4 text-center text-sm font-bold text-[#06285b] shadow-sm">
                How it works <ArrowRight className="h-4 w-4 text-[#0069e5]" aria-hidden="true" />
              </a>
            </div>
            <p className="mt-5 max-w-[570px] text-xs leading-6 text-[#435c82]">
Check your property's ZIP code to see current coverage guidance. If a call is available, you will see its recording/privacy notice and choose whether to proceed. No automatic dialling.
            </p>
          </div>

          <aside aria-label="Roofing service needs" className="rounded-[26px] border border-[#d0e4f8] bg-white/95 p-4 shadow-[0_28px_65px_rgba(6,36,88,.15)] backdrop-blur-sm sm:p-6 lg:p-7">
            <p className="px-1 pb-4 text-xs font-extrabold uppercase tracking-[0.18em] text-[#0762d7]">Start with the roof issue</p>
            <div className="grid gap-2.5">
              {needs.map(({ name, info, Icon, tone, ink }) => (
                <div key={name} className="flex min-h-[92px] items-center gap-3 rounded-2xl border border-[#d9e8f6] bg-gradient-to-r from-white to-[#fbfdff] p-3 shadow-[0_2px_9px_rgba(11,52,107,.03)] sm:gap-4">
                  <span className={`flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br ${tone}`}>
                    <Icon className={`h-7 w-7 ${ink}`} strokeWidth={2.1} aria-hidden="true" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <h2 className="text-[14px] font-bold leading-5 text-[#091c3b] sm:text-[15px]">{name}</h2>
                    <p className="mt-1 text-xs leading-5 text-[#486184] sm:text-[13px]">{info}</p>
                  </div>
                  <ChevronRight className="h-5 w-5 shrink-0 text-[#1471de]" aria-hidden="true" />
                </div>
              ))}
            </div>
          </aside>
        </div>
      </section>

      <RoofingCoverageCheck />

      <section id="how-it-works" className="border-b border-[#deecf9] bg-white">
        <div className="mx-auto max-w-[1260px] px-5 py-14 sm:px-8 sm:py-16">
          <p className="text-xs font-extrabold uppercase tracking-[0.22em] text-[#086be5]">How it works</p>
          <h2 className="mt-3 max-w-[940px] text-[28px] font-extrabold leading-tight tracking-[-0.04em] text-[#081b3a] sm:text-[37px]">
            A straightforward homeowner-initiated service request.
          </h2>
          <div className="mt-7 grid gap-4 md:grid-cols-3">
            {steps.map(([number, title, body], index) => {
              const Icon = stepIcons[index];
              return (
                <div key={number} className="relative rounded-2xl border border-[#dce8f6] bg-gradient-to-br from-white to-[#f7fbff] p-6 shadow-[0_8px_26px_rgba(6,45,96,.05)]">
                  <div className="flex items-center justify-between">
                    <span className={`flex h-11 w-11 items-center justify-center rounded-full text-sm font-extrabold ${index === 1 ? "bg-[#d8efff] text-[#0557cb]" : "bg-[#d4faeb] text-[#075349]"}`}>{number}</span>
                    <span className="flex h-10 w-10 items-center justify-center rounded-full bg-[#e2f2ff] text-[#075aca]">
                      <Icon className="h-5 w-5" aria-hidden="true" />
                    </span>
                  </div>
                  <h3 className="mt-5 text-lg font-bold text-[#092348]">{title}</h3>
                  <p className="mt-2 text-sm leading-6 text-[#4b6183]">{body}</p>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      <section aria-labelledby="roofing-homeowner-questions" className="border-b border-[#dce8f6] bg-white">
        <div className="mx-auto max-w-[1260px] px-5 py-14 sm:px-8">
          <p className="text-xs font-extrabold uppercase tracking-[0.21em] text-[#086be5]">Roofing service questions</p>
          <h2 id="roofing-homeowner-questions" className="mt-3 max-w-3xl text-3xl font-extrabold tracking-[-0.04em] text-[#081a38] sm:text-4xl">
            Understand the next step before choosing a contractor.
          </h2>
          <div className="mt-8 grid gap-4 lg:grid-cols-3">
            <article className="rounded-2xl border border-[#dce8f6] bg-[#f7fbff] p-6">
              <h3 className="text-lg font-bold text-[#091c3b]">How can I check roof replacement services near me?</h3>
              <p className="mt-3 text-sm leading-7 text-[#405b7e]">Enter the property's five-digit ZIP code to see whether it appears in recent coverage guidance. This does not confirm a local roofer, available appointment or live call route.</p>
            </article>
            <article className="rounded-2xl border border-[#dce8f6] bg-[#f7fbff] p-6">
              <h3 className="text-lg font-bold text-[#091c3b]">Does storm damage mean I need a new roof?</h3>
              <p className="mt-3 text-sm leading-7 text-[#405b7e]">Storm conditions alone cannot establish the condition of a particular roof. Explain the visible issue and ask an appropriately licensed and insured professional to assess the property.</p>
            </article>
            <article className="rounded-2xl border border-[#dce8f6] bg-[#f7fbff] p-6">
              <h3 className="text-lg font-bold text-[#091c3b]">Can I request a roof installation or replacement call?</h3>
              <p className="mt-3 text-sm leading-7 text-[#405b7e]">Calls are not currently enabled on this preview. A later call option would require service-area, routing, buyer and operating-hours checks. You would choose whether to place the call.</p>
            </article>
          </div>
          <p className="mt-6 text-xs leading-6 text-[#547092]">
            These answers describe the service-check process; they are not a promise of contractor availability or roofing outcomes.
          </p>
        </div>
      </section>

      <section className="bg-[#f8fbff]">
        <div className="mx-auto grid max-w-[1260px] gap-8 px-5 py-14 sm:px-8 lg:grid-cols-[.93fr_1.07fr] lg:items-center">
          <div>
            <p className="text-xs font-extrabold uppercase tracking-[0.21em] text-[#086be5]">Before calling</p>
            <h2 className="mt-3 text-3xl font-extrabold tracking-[-0.04em] text-[#081a38] sm:text-4xl">Have the basics ready.</h2>
            <p className="mt-3 max-w-[550px] text-sm leading-7 text-[#496285]">A concise description of the roofing issue and property location helps determine whether an eligible service route is available.</p>
            <ul className="mt-5 grid gap-3 text-sm text-[#294669]">
              {[
                "Property ZIP code or service location",
                "Type of roofing issue or project",
                "When the issue started or was observed",
                "Relevant property access information",
              ].map((item) => (
                <li key={item} className="flex items-start gap-2.5">
                  <span className="mt-[3px] flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[#0876ef] text-white"><Check className="h-3.5 w-3.5" aria-hidden="true" /></span>
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </div>
          <div className="rounded-[25px] border border-[#bedfff] bg-gradient-to-br from-[#e8f5ff] via-[#e9f6ff] to-[#dceeff] p-6 shadow-[0_18px_42px_rgba(10,117,206,.09)] sm:p-8">
            <div className="flex items-start gap-4">
              <span className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-[#bde4ff] text-[#0869d9]"><ShieldCheck className="h-7 w-7" aria-hidden="true" /></span>
              <div>
                <p className="text-xs font-extrabold uppercase tracking-[0.17em] text-[#0864d4]">Service disclosure</p>
                <p className="mt-3 text-sm leading-6 text-[#395477]">
                  This site is a free service to assist homeowners in connecting with local service contractors. All contractors are independent and this site does not warrant or guarantee any work performed. It is the responsibility of the homeowner to verify that the hired contractor furnishes the necessary license and insurance required for the work being performed. All persons depicted in a photo or video are actors or models and not contractors listed on this site.
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      <footer className="border-t border-[#1d5da0] bg-gradient-to-r from-[#031830] via-[#052450] to-[#05377a] text-white">
        <div className="mx-auto max-w-[1260px] px-5 py-9 sm:px-8">
          <p className="text-[11px] font-extrabold uppercase tracking-[0.17em] text-[#62dcff]">Buyer review · Pre-activation</p>
          <div className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {[
              "Generic and unbranded consumer creative",
              "No commercial incentives or unsupported claims",
              "No unsupported quality, price or ranking claims",
              "Consumer initiates the call",
              "Traffic remains off until buyer approval",
            ].map((item) => (
              <p key={item} className="flex items-center gap-2 rounded-lg border border-[#2a6ba8] bg-white/5 px-3 py-2 text-xs text-[#d5ebff]">
                <Check className="h-4 w-4 shrink-0 text-[#6cf5d4]" aria-hidden="true" />{item}
              </p>
            ))}
          </div>
          <p className="mt-5 text-xs leading-6 text-[#acc8e9]">Service availability, contractor participation, call qualification and coverage may vary by location and program. No publication authority · no live traffic · no commercial terms inferred.</p>
          <nav aria-label="Service policies" className="mt-5 flex flex-wrap gap-x-6 gap-y-3 text-xs text-[#d5ebff]">
            <a className="underline decoration-[#62dcff]/60 underline-offset-4 hover:text-white" href="/privacy">Privacy Policy</a>
            <a className="underline decoration-[#62dcff]/60 underline-offset-4 hover:text-white" href="/terms">Terms &amp; Conditions</a>
          </nav>
        </div>
      </footer>
    </main>
  );
}
