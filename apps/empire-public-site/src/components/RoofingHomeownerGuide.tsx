import { ArrowLeft, ArrowRight, CheckCircle2, House, ShieldCheck } from "lucide-react";

export type RoofingGuideSection = {
  heading: string;
  paragraphs: string[];
  checklist?: string[];
};

type Props = {
  eyebrow: string;
  title: string;
  introduction: string;
  takeaway: string;
  sections: RoofingGuideSection[];
  nextGuide: { href: string; label: string };
};

export default function RoofingHomeownerGuide({
  eyebrow,
  title,
  introduction,
  takeaway,
  sections,
  nextGuide,
}: Props) {
  return (
    <main className="min-h-screen overflow-x-hidden bg-[#f7fbff] text-[#081b39]">
      <header className="border-b border-[#255ab3]/30 bg-gradient-to-r from-[#04152c] via-[#06295c] to-[#0754ab] text-white">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-5 py-5 sm:px-8">
          <a href="/roofing" className="inline-flex items-center gap-3 text-sm font-bold tracking-wide hover:text-[#b4e6ff]">
            <House size={19} aria-hidden="true" /> Roofing homeowner information
          </a>
          <span className="rounded-full border border-[#67c9ff]/35 px-3 py-1.5 text-xs font-semibold text-[#cceaff]">
            Educational guide · No live call service
          </span>
        </div>
      </header>

      <section className="relative isolate overflow-hidden border-b border-[#cbdff5] bg-[#eaf4ff]">
        <div className="pointer-events-none absolute inset-y-0 right-0 w-2/3 bg-[url('/roofing-hero.webp')] bg-cover bg-center opacity-20 sm:opacity-35" aria-hidden="true" />
        <div className="pointer-events-none absolute inset-0 bg-gradient-to-r from-[#f7fbff] via-[#f7fbff]/95 to-[#f7fbff]/45" aria-hidden="true" />
        <div className="relative mx-auto max-w-6xl px-5 pb-14 pt-12 sm:px-8 sm:pb-20 sm:pt-20">
          <nav aria-label="Breadcrumb" className="mb-10 flex flex-wrap items-center gap-2 text-xs font-semibold text-[#315b90]">
            <a href="/" className="hover:underline">Empire AI</a><span>/</span>
            <a href="/roofing" className="hover:underline">Roofing</a><span>/</span>
            <span aria-current="page">Homeowner guide</span>
          </nav>
          <p className="mb-4 text-xs font-extrabold uppercase tracking-[.2em] text-[#0863bd]">{eyebrow}</p>
          <h1 className="max-w-4xl text-[clamp(2.3rem,5.4vw,4.7rem)] font-extrabold leading-[1.07] tracking-[-.05em]">{title}</h1>
          <p className="mt-7 max-w-3xl text-lg leading-8 text-[#365474]">{introduction}</p>
          <div className="mt-9 max-w-3xl rounded-2xl border border-[#b5d9f6] bg-white/95 p-6 shadow-[0_16px_40px_rgba(8,45,104,.08)]">
            <p className="text-xs font-bold uppercase tracking-[.16em] text-[#0a66bd]">The practical takeaway</p>
            <p className="mt-3 text-base font-semibold leading-7 text-[#09234b]">{takeaway}</p>
          </div>
        </div>
      </section>

      <div className="mx-auto grid max-w-6xl gap-12 px-5 py-14 sm:px-8 lg:grid-cols-[220px_minmax(0,1fr)] lg:gap-16">
        <aside className="h-fit lg:sticky lg:top-8">
          <nav aria-label="On this page" className="rounded-2xl border border-[#d1e4f8] bg-white p-5 shadow-sm">
            <p className="mb-4 text-xs font-extrabold uppercase tracking-[.14em] text-[#0b5da8]">In this guide</p>
            <ol className="space-y-3 text-sm leading-6">
              {sections.map((section, i) => (
                <li key={section.heading}><a className="text-[#345777] hover:text-[#0568cf] hover:underline" href={`#section-${i + 1}`}>{section.heading}</a></li>
              ))}
            </ol>
          </nav>
          <div className="mt-5 rounded-2xl border border-[#d4e5f6] bg-[#f0f7ff] p-5 text-xs leading-6 text-[#4b6683]">
            <ShieldCheck size={19} className="mb-3 text-[#0864c2]" aria-hidden="true" />
            General homeowner information, not an inspection, contractor recommendation, insurance opinion or legal advice.
          </div>
        </aside>

        <article className="min-w-0 space-y-12">
          {sections.map((section, i) => (
            <section key={section.heading} id={`section-${i + 1}`} className="scroll-mt-10">
              <p className="text-xs font-extrabold uppercase tracking-[.16em] text-[#1376cb]">Guide section {String(i + 1).padStart(2, "0")}</p>
              <h2 className="mt-3 text-2xl font-bold tracking-tight sm:text-3xl">{section.heading}</h2>
              <div className="mt-5 space-y-4 text-base leading-8 text-[#34506e]">
                {section.paragraphs.map((paragraph) => <p key={paragraph}>{paragraph}</p>)}
              </div>
              {section.checklist && (
                <ul className="mt-7 space-y-3 rounded-2xl border border-[#c3dff6] bg-white p-6">
                  {section.checklist.map((item) => (
                    <li key={item} className="flex items-start gap-3 text-sm leading-7 text-[#244568]">
                      <CheckCircle2 size={18} className="mt-1 shrink-0 text-[#0871ca]" aria-hidden="true" />
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          ))}
          <div className="rounded-2xl border border-[#b6d9f5] bg-[#e9f5ff] p-6 sm:p-8">
            <h2 className="text-xl font-bold">What to do next</h2>
            <p className="mt-3 text-sm leading-7 text-[#325575]">
              Keep written notes and photographs taken safely from the ground. Ask a suitably qualified local roofer to explain the findings, scope, permits and warranty terms. Availability, pricing and suitability vary by property and region.
            </p>
            <div className="mt-6 flex flex-wrap gap-4 text-sm font-bold">
              <a href={nextGuide.href} className="inline-flex items-center gap-2 text-[#075cba] hover:underline">{nextGuide.label}<ArrowRight size={16} aria-hidden="true" /></a>
              <a href="/roofing" className="inline-flex items-center gap-2 text-[#075cba] hover:underline"><ArrowLeft size={16} aria-hidden="true" />Back to roofing information</a>
            </div>
          </div>
          <p className="text-xs leading-6 text-[#61768d]">
            Empire AI provides this editorial information without asserting contractor availability or an active call service.
            See our <a href="/privacy" className="font-semibold text-[#0a62b8] underline">Privacy Notice</a> and <a href="/terms" className="font-semibold text-[#0a62b8] underline">Website Terms</a>.
          </p>
        </article>
      </div>
    </main>
  );
}
