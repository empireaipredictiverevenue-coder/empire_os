import type { Metadata } from "next";
import { ArrowRight, Check, ChevronRight, Droplets, FileText, House, MapPin, MessageSquareText, Phone, ShieldCheck, Wind } from "lucide-react";

export const metadata: Metadata = {
  title: "Roofing Service Help",
  description:
    "Information for homeowners looking for roofing service availability in their area.",
  robots: { index: false, follow: false },
};

const TRACKING_NUMBER_E164 = "+18883579305";
const TRACKING_NUMBER_DISPLAY = "(888) 357-9305";

/*
 * Fail closed.
 *
 * Assignment of a Ringba tracking number is not verification.
 * Neither this source nor its materialized worker copy can activate
 * calls until the separately evidenced gates are changed.
 */
const TRACKING_VERIFIED = false;
const ZIP_COVERAGE_VERIFIED = false;
const ROUTING_VERIFIED = false;
const FOUNDER_LIVE_TRAFFIC_AUTHORIZED = false;

const CALL_ROUTE_ENABLED =
  TRACKING_VERIFIED &&
  ZIP_COVERAGE_VERIFIED &&
  ROUTING_VERIFIED &&
  FOUNDER_LIVE_TRAFFIC_AUTHORIZED;

const roofingNeeds = [
  [
    "Roof leak or water entry",
    "Describe where the issue is visible and when you first noticed it.",
  ],
  [
    "Storm or wind damage",
    "Explain what changed after the weather event and the current condition of the property.",
  ],
  [
    "Missing or damaged roofing materials",
    "Provide a short description of the visible roofing issue.",
  ],
  [
    "Roof replacement enquiry",
    "Provide the property location and basic project information.",
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
    { name: roofingNeeds[0][0], info: roofingNeeds[0][1], Icon: Droplets, tone: "from-[#d9edff] to-[#c7ecff]", ink: "text-[#0757ca]" },
    { name: roofingNeeds[1][0], info: roofingNeeds[1][1], Icon: Wind, tone: "from-[#d5fbff] to-[#b4f2f9]", ink: "text-[#004caa]" },
    { name: roofingNeeds[2][0], info: roofingNeeds[2][1], Icon: FileText, tone: "from-[#dbfff1] to-[#c1f6e1]", ink: "text-[#07595c]" },
    { name: roofingNeeds[3][0], info: roofingNeeds[3][1], Icon: House, tone: "from-[#d8efff] to-[#bde7ff]", ink: "text-[#064bc0]" },
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
              Need help with a roofing issue?
            </h1>
            <p className="mt-6 max-w-[610px] text-[17px] leading-[1.65] text-[#345078] sm:text-[19px]">
              Tell us what is happening and where the property is located. Service availability depends on location and current provider capacity.
            </p>
            <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:flex-wrap">
              {CALL_ROUTE_ENABLED ? (
                <a
                  href={`tel:${TRACKING_NUMBER_E164}`}
                  className="inline-flex min-h-14 items-center justify-center gap-4 rounded-xl bg-gradient-to-b from-[#0fb3ff] via-[#087af5] to-[#0057d8] px-7 py-4 text-center text-base font-bold text-white shadow-[0_11px_24px_rgba(0,94,223,.25)]"
                >
                  Call {TRACKING_NUMBER_DISPLAY} <ArrowRight className="h-5 w-5" aria-hidden="true" />
                </a>
              ) : (
                <button type="button" disabled aria-disabled="true" className="inline-flex min-h-14 cursor-not-allowed items-center justify-center gap-4 rounded-xl bg-gradient-to-b from-[#10acfb] via-[#0877ee] to-[#0050c9] px-7 py-4 text-base font-bold text-white opacity-80 shadow-[0_10px_24px_rgba(0,91,213,.2)]">
                  Call route pending verification <ArrowRight className="h-5 w-5" aria-hidden="true" />
                </button>
              )}
              <a href="#how-it-works" className="inline-flex min-h-14 items-center justify-center gap-2 rounded-xl border border-[#b7d6ef] bg-white/90 px-5 py-4 text-center text-sm font-bold text-[#06285b] shadow-sm">
                How it works <ArrowRight className="h-4 w-4 text-[#0069e5]" aria-hidden="true" />
              </a>
            </div>
            <p className="mt-5 max-w-[570px] text-xs leading-6 text-[#435c82]">
              Calling remains unavailable until current service-area eligibility and the assigned call route have been verified.
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
        </div>
      </footer>
    </main>
  );
}
