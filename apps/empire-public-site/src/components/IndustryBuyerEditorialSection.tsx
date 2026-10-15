import { ArrowRight, CircleCheck, ShieldCheck } from "lucide-react";
import type { BuyerEditorial } from "@/lib/industry-buying-editorial";

/** A useful, crawlable B2B educational section. Never a buyer activation. */
export default function IndustryBuyerEditorialSection({
  editorial,
  industry,
}: {
  editorial: BuyerEditorial;
  industry: "roofing" | "solar";
}) {
  const headingId = `${industry}-buyer-evidence`;
  return (
    <section
      aria-labelledby={headingId}
      className="relative z-10 border-y border-[#00E5FF]/[0.09] bg-[linear-gradient(125deg,rgba(0,229,255,0.025),transparent_48%,rgba(124,255,0,0.02))] py-24 sm:py-32"
    >
      <div className="mx-auto w-[min(1330px,calc(100%-32px))]">
        <p className="text-[10px] font-black tracking-[0.24em] text-[#00E5FF]">
          {editorial.eyebrow}
        </p>
        <div className="mt-6 grid gap-10 lg:grid-cols-[1fr_0.7fr] lg:gap-20">
          <h2
            id={headingId}
            className="m-0 max-w-3xl text-[clamp(2.4rem,4.7vw,4.9rem)] font-[560] leading-[0.99] tracking-[-0.05em] text-white"
          >
            {editorial.heading}
          </h2>
          <p className="max-w-xl self-end text-base leading-8 text-white/55">
            {editorial.introduction}
          </p>
        </div>
        <div className="mt-16 grid gap-4 lg:grid-cols-3">
          {editorial.sections.map((section, idx) => (
            <article
              key={section.heading}
              className="rounded-3xl border border-white/[0.08] bg-black/25 p-7 sm:p-8"
            >
              <span className="text-[10px] font-black tracking-[0.17em] text-[#7CFF00]/80">
                {String(idx + 1).padStart(2, "0")}
              </span>
              <h3 className="mt-8 text-xl font-semibold leading-tight tracking-[-0.025em] text-white/90">
                {section.heading}
              </h3>
              <p className="mt-4 text-sm leading-7 text-white/55">{section.body}</p>
              {section.points && (
                <ul className="mt-6 space-y-4 border-t border-white/[0.08] pt-6">
                  {section.points.map((point) => (
                    <li key={point} className="flex gap-3 text-xs leading-6 text-white/60">
                      <CircleCheck
                        aria-hidden="true"
                        className="mt-1 size-4 shrink-0 text-[#00E5FF]/70"
                      />
                      <span>{point}</span>
                    </li>
                  ))}
                </ul>
              )}
            </article>
          ))}
        </div>
        <div className="mt-14 grid gap-10 border-t border-white/[0.08] pt-12 lg:grid-cols-[0.34fr_1fr]">
          <div>
            <p className="text-[10px] font-black tracking-[0.21em] text-[#7CFF00]">
              FREQUENT QUESTIONS
            </p>
            <p className="mt-4 text-sm leading-7 text-white/40">
              Commercial evidence and a forecast are never interchangeable.
            </p>
          </div>
          <div className="space-y-0">
            {editorial.questions.map(({ question, answer }) => (
              <div key={question} className="border-b border-white/[0.08] py-5 first:pt-0">
                <h3 className="text-base font-semibold text-white/85">{question}</h3>
                <p className="mt-3 max-w-3xl text-sm leading-7 text-white/55">{answer}</p>
              </div>
            ))}
          </div>
        </div>
        <div className="mt-14 flex flex-col gap-6 rounded-3xl border border-[#00E5FF]/20 bg-[#00E5FF]/[0.035] p-7 sm:flex-row sm:items-center sm:justify-between sm:p-9">
          <div className="flex max-w-3xl items-start gap-4">
            <ShieldCheck aria-hidden="true" className="mt-1 size-6 shrink-0 text-[#7CFF00]" />
            <div>
              <h3 className="text-lg font-semibold text-white">Explore a commercial review.</h3>
              <p className="mt-2 text-sm leading-7 text-white/55">{editorial.commercialPrompt}</p>
            </div>
          </div>
          <a
            href="/commercial"
            className="inline-flex min-h-12 shrink-0 items-center justify-center gap-2 rounded-full bg-gradient-to-r from-[#7CFF00] to-[#00E5FF] px-6 text-sm font-bold text-black focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[#00E5FF]"
          >
            Request a scoped proposal
            <ArrowRight aria-hidden="true" className="size-4" />
          </a>
        </div>
      </div>
    </section>
  );
}
