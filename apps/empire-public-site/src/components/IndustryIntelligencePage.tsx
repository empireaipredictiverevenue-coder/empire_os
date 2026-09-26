import {
  ArrowRight,
  BarChart3,
  BrainCircuit,
  CircleDot,
  Radar,
  SearchCheck,
  ShieldCheck,
  Sparkles,
  Waypoints,
} from "lucide-react";
import type { IndustryPage } from "@/lib/industry-pages";

function Label({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-[10px] font-black tracking-[0.24em] text-[#7CFF00]">
      {children}
    </p>
  );
}

export default function IndustryIntelligencePage({ page }: { page: IndustryPage }) {
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "WebPage",
    name: page.title,
    description: page.summary,
    url: `https://empire-ai.co.uk/industries/${page.slug}`,
    publisher: {
      "@type": "Organization",
      name: "Empire AI",
      url: "https://empire-ai.co.uk",
    },
  };

  const forecastIcons = [Radar, BarChart3, BrainCircuit, Waypoints];

  return (
    <main className="min-h-screen overflow-hidden bg-[#020403] text-[#F4FFF9] selection:bg-[#7CFF00] selection:text-black">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      <div className="pointer-events-none fixed inset-0 bg-[radial-gradient(circle_at_82%_8%,rgba(0,229,255,0.09),transparent_30rem),radial-gradient(circle_at_8%_38%,rgba(124,255,0,0.065),transparent_34rem)]" />

      <nav className="relative z-20 mx-auto flex h-20 w-[min(1480px,calc(100%-32px))] items-center justify-between border-b border-white/[0.07]">
        <a href="/" className="flex items-center gap-3">
          <span className="grid size-10 place-items-center rounded-xl border border-[#7CFF00]/25 bg-[#7CFF00]/[0.055] font-black text-[#7CFF00]">E</span>
          <span>
            <strong className="block text-[11px] tracking-[0.22em]">EMPIRE AI</strong>
            <small className="mt-1 block text-[8px] tracking-[0.23em] text-white/30">INDUSTRY INTELLIGENCE</small>
          </span>
        </a>
        <a href="/trust" className="rounded-full border border-[#00E5FF]/20 bg-[#00E5FF]/[0.045] px-4 py-2.5 text-[11px] font-bold text-[#B8F8FF]">
          Trust Center
        </a>
      </nav>

      <section className="relative z-10 mx-auto grid min-h-[760px] w-[min(1480px,calc(100%-32px))] items-center gap-16 py-20 lg:grid-cols-[1.05fr_0.95fr]">
        <div>
          <Label>{page.eyebrow}</Label>
          <h1 className="mt-6 max-w-5xl text-[clamp(3.5rem,7vw,7.4rem)] font-[560] leading-[0.9] tracking-[-0.06em]">
            {page.title}
          </h1>
          <p className="mt-7 max-w-2xl text-[17px] leading-8 text-white/52">{page.subtitle}</p>
          <div className="mt-9 flex flex-wrap gap-3">
            <a href="#signals" className="group inline-flex min-h-12 items-center gap-2 rounded-full bg-gradient-to-r from-[#7CFF00] via-[#5CFF79] to-[#00E5FF] px-5 text-xs font-extrabold text-black">
              Explore intelligence
              <ArrowRight className="size-3.5 transition-transform group-hover:translate-x-1" />
            </a>
            <a href="mailto:founder@empire-ai.co.uk" className="inline-flex min-h-12 items-center gap-2 rounded-full border border-white/10 bg-white/[0.025] px-5 text-xs font-extrabold text-white/70">
              Talk to Empire
            </a>
          </div>
        </div>

        <div className="relative mx-auto aspect-square w-full max-w-[590px]">
          <div className="absolute inset-[4%] rounded-full border border-[#7CFF00]/10" />
          <div className="absolute inset-[16%] rounded-full border border-dashed border-[#00E5FF]/15" />
          <div className="absolute inset-[30%] rounded-full border border-white/10" />
          <div className="absolute inset-[41%] grid place-items-center rounded-full bg-[radial-gradient(circle_at_35%_30%,#D9FFB2,#7CFF00_35%,#154200_85%)] text-center text-[10px] font-black tracking-[0.15em] text-black shadow-[0_0_100px_rgba(124,255,0,.16)]">
            MARKET<br />INTELLIGENCE
          </div>
          {[
            ["SIGNALS", "top-[8%] left-[40%]"],
            ["FORECAST", "top-[28%] right-[0%]"],
            ["BUYERS", "bottom-[20%] right-[6%]"],
            ["SEARCH", "bottom-[8%] left-[34%]"],
            ["MARKET", "bottom-[26%] left-[0%]"],
            ["EVIDENCE", "top-[24%] left-[4%]"],
          ].map(([label, pos]) => (
            <span key={label} className={`absolute ${pos} rounded-full border border-white/10 bg-black/70 px-3 py-2 text-[8px] font-bold tracking-[0.15em] text-white/45 backdrop-blur-xl`}>
              {label}
            </span>
          ))}
        </div>
      </section>

      <section className="relative z-10 border-y border-white/[0.07] bg-white/[0.012]">
        <div className="mx-auto grid w-[min(1480px,calc(100%-32px))] gap-8 py-10 lg:grid-cols-[0.35fr_1fr]">
          <Label>WHAT EMPIRE SEES</Label>
          <p className="m-0 max-w-5xl text-[clamp(1.5rem,2.5vw,2.5rem)] font-[500] leading-[1.18] tracking-[-0.035em] text-white/78">
            {page.summary}
          </p>
        </div>
      </section>

      <section id="signals" className="relative z-10 mx-auto w-[min(1480px,calc(100%-32px))] py-28">
        <div className="grid gap-12 lg:grid-cols-[0.42fr_1fr]">
          <div>
            <Label>SIGNAL LAYERS</Label>
            <h2 className="mt-5 text-[clamp(2.5rem,4vw,4.4rem)] font-[560] leading-[0.96] tracking-[-0.05em]">Evidence before opinion.</h2>
            <p className="mt-5 max-w-md text-sm leading-7 text-white/42">
              Independent evidence becomes more useful when it is joined around the same market, company, property or buyer over time.
            </p>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {page.signals.map((item, index) => (
              <article key={item} className="group min-h-36 rounded-2xl border border-white/[0.08] bg-white/[0.025] p-5 transition duration-300 hover:-translate-y-1 hover:border-[#00E5FF]/25">
                <div className="flex items-center justify-between">
                  <CircleDot className="size-4 text-[#00E5FF]/60" />
                  <span className="text-[9px] font-black tracking-[0.14em] text-white/20">{String(index + 1).padStart(2, "0")}</span>
                </div>
                <p className="mt-8 text-sm font-semibold leading-6 text-white/78">{item}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="relative z-10 border-y border-white/[0.07] bg-gradient-to-br from-[#7CFF00]/[0.025] via-[#020403] to-[#00E5FF]/[0.03] py-28">
        <div className="mx-auto grid w-[min(1480px,calc(100%-32px))] gap-16 lg:grid-cols-2">
          <div>
            <Label>QUESTIONS THAT MATTER</Label>
            <div className="mt-8 border-t border-white/[0.08]">
              {page.questions.map((question, index) => (
                <div key={question} className="grid grid-cols-[38px_1fr] gap-4 border-b border-white/[0.08] py-5">
                  <span className="text-[9px] font-black tracking-[0.14em] text-[#00E5FF]/55">Q{index + 1}</span>
                  <p className="m-0 text-sm leading-6 text-white/65">{question}</p>
                </div>
              ))}
            </div>
          </div>
          <div>
            <Label>FORECAST HORIZON</Label>
            <h2 className="mt-5 max-w-xl text-[clamp(2.5rem,4vw,4.2rem)] font-[560] leading-[0.96] tracking-[-0.05em]">
              Now, next quarter, and the next two years.
            </h2>
            <div className="mt-9 grid gap-3">
              {page.forecast.map((item, index) => {
                const Icon = forecastIcons[index % forecastIcons.length];
                return (
                  <div key={item} className="flex items-center gap-4 rounded-2xl border border-white/[0.08] bg-black/20 p-5">
                    <span className="grid size-10 place-items-center rounded-xl border border-[#7CFF00]/15 bg-[#7CFF00]/[0.04]">
                      <Icon className="size-4 text-[#7CFF00]/70" />
                    </span>
                    <p className="m-0 text-sm font-semibold text-white/70">{item}</p>
                  </div>
                );
              })}
            </div>
            <p className="mt-5 text-xs leading-6 text-white/30">
              Forecasts remain forecasts. They stay separate from observed outcomes and are recalibrated as real evidence arrives.
            </p>
          </div>
        </div>
      </section>

      <section className="relative z-10 mx-auto w-[min(1480px,calc(100%-32px))] py-28">
        <div className="grid gap-12 lg:grid-cols-[0.42fr_1fr]">
          <div>
            <Label>DATA PRODUCTS</Label>
            <h2 className="mt-5 text-[clamp(2.5rem,4vw,4.2rem)] font-[560] leading-[0.96] tracking-[-0.05em]">Intelligence you can use.</h2>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            {page.products.map((product, index) => (
              <article key={product} className="min-h-52 rounded-3xl border border-white/[0.08] bg-white/[0.02] p-6 transition duration-300 hover:border-[#00E5FF]/25">
                {index % 2 === 0 ? <SearchCheck className="size-5 text-[#00E5FF]/60" /> : <Sparkles className="size-5 text-[#7CFF00]/60" />}
                <h3 className="mt-20 text-xl font-semibold tracking-[-0.02em]">{product}</h3>
                <p className="mt-3 text-[12px] leading-6 text-white/35">
                  Evidence-backed output for operators, analysts, investors and enterprise teams.
                </p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="relative z-10 border-y border-white/[0.07] bg-white/[0.012] py-24">
        <div className="mx-auto w-[min(1180px,calc(100%-32px))] text-center">
          <Label>CONNECTED INTELLIGENCE</Label>
          <h2 className="mt-5 text-[clamp(2.6rem,5vw,5rem)] font-[560] leading-[0.94] tracking-[-0.05em]">One market never moves alone.</h2>
          <div className="mt-9 flex flex-wrap justify-center gap-3">
            {page.links.map((link) => (
              <a key={link.href} href={link.href} className="group inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.025] px-5 py-3 text-xs font-bold text-white/60 transition hover:border-[#00E5FF]/30 hover:text-white">
                {link.label}
                <ArrowRight className="size-3 transition-transform group-hover:translate-x-1" />
              </a>
            ))}
          </div>
        </div>
      </section>

      <section className="relative z-10 mx-auto w-[min(1180px,calc(100%-32px))] py-32 text-center">
        <ShieldCheck className="mx-auto mb-6 size-6 text-[#00E5FF]/60" />
        <Label>EMPIRE AI</Label>
        <h2 className="mt-5 text-[clamp(3rem,5.5vw,5.6rem)] font-[560] leading-[0.93] tracking-[-0.055em]">
          See the market earlier.
          <span className="block bg-gradient-to-r from-[#7CFF00] to-[#00E5FF] bg-clip-text text-transparent">Act with better evidence.</span>
        </h2>
        <a href="mailto:founder@empire-ai.co.uk" className="group mt-9 inline-flex min-h-12 items-center gap-2 rounded-full bg-gradient-to-r from-[#7CFF00] to-[#00E5FF] px-6 text-xs font-extrabold text-black">
          Start a conversation
          <ArrowRight className="size-3.5 transition-transform group-hover:translate-x-1" />
        </a>
      </section>
    </main>
  );
}
