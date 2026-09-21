"use client";

import { motion, useScroll, useSpring } from "motion/react";
import {
  ArrowDown,
  ArrowRight,
  Braces,
  CircleDollarSign,
  Crosshair,
  Gauge,
  Radar,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import EmpireWorld from "@/components/EmpireWorld";

const chapters = [
  {
    id: "signals",
    number: "01",
    kicker: "SIGNAL FIELD",
    title: "See the market before the market sees itself.",
    copy:
      "Storms. Search demand. buyer intent. competitor movement. company change. Empire turns fragmented evidence into a live commercial field.",
    proof: "REAL SIGNALS · PROVENANCE ATTACHED",
    align: "left",
  },
  {
    id: "reactor",
    number: "02",
    kicker: "REVENUE REACTOR",
    title: "Evidence becomes commercial priority.",
    copy:
      "Omega, Cortex and the intelligence fabric compress thousands of observations into the few opportunities worth acting on now.",
    proof: "UNKNOWN STAYS UNKNOWN",
    align: "right",
  },
  {
    id: "opportunity",
    number: "03",
    kicker: "OPPORTUNITY TUNNEL",
    title: "Move from possibility to a route into revenue.",
    copy:
      "Empire resolves the company, decision-maker, why-now evidence, market context and economics before GTM is allowed to move.",
    proof: "IDENTITY · INTENT · ECONOMICS",
    align: "left",
  },
  {
    id: "execution",
    number: "04",
    kicker: "EXECUTION CHAMBER",
    title: "Agents work. Authority stays governed.",
    copy:
      "Search, outreach, conversation, fulfilment and learning coordinate through one control fabric—with irreversible actions remaining explicit gates.",
    proof: "AUTOMATION WITHOUT FICTION",
    align: "right",
  },
  {
    id: "truth",
    number: "05",
    kicker: "REVENUE MONOLITH",
    title: "Forecast is not revenue. Revenue is evidence.",
    copy:
      "Delivery, payment, fulfilment, recognized revenue and realized GP are kept separate from scores and forecasts, then fed back into the system.",
    proof: "VERIFIED PAYMENT · RECOGNIZED REVENUE",
    align: "left",
  },
];

function Mark() {
  return (
    <a href="#top" className="flex items-center gap-3">
      <span className="relative grid size-9 place-items-center overflow-hidden rounded-[10px] border border-white/10 bg-white/[0.035]">
        <span className="absolute inset-[5px] rounded-[7px] border border-[#91ff43]/30" />
        <span className="font-black text-[#a6ff6a]">E</span>
      </span>
      <span>
        <strong className="block text-[10px] tracking-[0.24em] text-white">EMPIRE AI</strong>
        <small className="mt-1 block text-[7px] tracking-[0.24em] text-white/35">
          PREDICTIVE REVENUE
        </small>
      </span>
    </a>
  );
}

function Chapter({
  chapter,
}: {
  chapter: (typeof chapters)[number];
}) {
  const right = chapter.align === "right";
  return (
    <section
      id={chapter.id}
      className="relative z-10 flex min-h-[108vh] items-center px-5 py-24 md:px-10 lg:px-14"
    >
      <motion.div
        initial={{ opacity: 0, y: 42 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ amount: 0.45 }}
        transition={{ duration: 0.75, ease: [0.22, 1, 0.36, 1] }}
        className={`w-full max-w-[1480px] mx-auto flex ${right ? "justify-end" : "justify-start"}`}
      >
        <div className={`max-w-[620px] ${right ? "lg:mr-[4vw]" : "lg:ml-[3vw]"}`}>
          <div className="mb-5 flex items-center gap-4">
            <span className="text-[9px] font-black tracking-[0.24em] text-[#9dff4a]">
              {chapter.number}
            </span>
            <span className="h-px w-10 bg-gradient-to-r from-[#9dff4a]/70 to-transparent" />
            <span className="text-[9px] font-black tracking-[0.24em] text-white/45">
              {chapter.kicker}
            </span>
          </div>

          <h2 className="max-w-[600px] text-[clamp(2.7rem,5.2vw,5.6rem)] font-[540] leading-[0.91] tracking-[-0.055em] text-[#f4fff6]">
            {chapter.title}
          </h2>

          <p className="mt-7 max-w-[560px] text-[14px] leading-7 text-white/48 sm:text-[16px]">
            {chapter.copy}
          </p>

          <div className="mt-8 inline-flex items-center gap-3 border-t border-white/10 pt-4 text-[8px] font-black tracking-[0.2em] text-white/35">
            <span className="size-1.5 rounded-full bg-[#9dff4a] shadow-[0_0_14px_rgba(157,255,74,.75)]" />
            {chapter.proof}
          </div>
        </div>
      </motion.div>
    </section>
  );
}

export default function Home() {
  const { scrollYProgress } = useScroll();
  const progress = useSpring(scrollYProgress, {
    stiffness: 90,
    damping: 22,
    mass: 0.24,
  });

  return (
    <main
      id="top"
      className="relative min-h-screen overflow-x-hidden bg-[#020403] text-white selection:bg-[#9dff4a] selection:text-black"
    >
      <div className="fixed inset-0 z-0">
        <EmpireWorld />
      </div>

      <div className="pointer-events-none fixed inset-0 z-[1] bg-[radial-gradient(circle_at_50%_38%,transparent_0%,rgba(2,4,3,.08)_36%,rgba(2,4,3,.7)_100%)]" />
      <div className="pointer-events-none fixed inset-0 z-[2] bg-[linear-gradient(90deg,rgba(2,4,3,.72),transparent_30%,transparent_70%,rgba(2,4,3,.64))]" />
      <div className="pointer-events-none fixed inset-0 z-[3] opacity-[0.055] [background-image:linear-gradient(rgba(255,255,255,.22)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,.22)_1px,transparent_1px)] [background-size:64px_64px]" />

      <motion.div
        className="fixed left-0 top-0 z-50 h-[2px] w-full origin-left bg-gradient-to-r from-[#9dff4a] via-[#d7ffc3] to-[#00d9ff]"
        style={{ scaleX: progress }}
      />

      <nav className="fixed inset-x-0 top-0 z-40 px-5 py-5 md:px-10 lg:px-14">
        <div className="mx-auto flex w-full max-w-[1480px] items-center justify-between rounded-2xl border border-white/[0.07] bg-black/20 px-4 py-3 backdrop-blur-2xl">
          <Mark />
          <div className="hidden items-center gap-6 text-[9px] font-bold tracking-[0.14em] text-white/45 lg:flex">
            <a href="#reactor" className="transition hover:text-white">SYSTEM</a>
            <a href="#opportunity" className="transition hover:text-white">OPPORTUNITY</a>
            <a href="/industries" className="transition hover:text-white">INDUSTRIES</a>
            <a href="/trust" className="transition hover:text-white">TRUST</a>
          </div>
          <a
            href="mailto:founder@empire-ai.co.uk"
            className="group flex items-center gap-2 rounded-full border border-[#9dff4a]/25 bg-[#9dff4a]/[0.07] px-4 py-2.5 text-[9px] font-black tracking-[0.12em] text-[#cfffad] transition hover:border-[#9dff4a]/55 hover:bg-[#9dff4a]/[0.12]"
          >
            START A CONVERSATION
            <ArrowRight className="size-3 transition-transform group-hover:translate-x-0.5" />
          </a>
        </div>
      </nav>

      <section className="relative z-10 flex min-h-[112vh] items-center px-5 pb-20 pt-32 md:px-10 lg:px-14">
        <div className="mx-auto w-full max-w-[1480px]">
          <motion.div
            initial={{ opacity: 0, y: 34 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.9, ease: [0.22, 1, 0.36, 1] }}
            className="max-w-[850px]"
          >
            <div className="mb-7 flex items-center gap-3 text-[9px] font-black tracking-[0.23em] text-white/42">
              <span className="size-1.5 rounded-full bg-[#9dff4a] shadow-[0_0_18px_rgba(157,255,74,.85)]" />
              PREDICTIVE REVENUE INFRASTRUCTURE
            </div>

            <h1 className="text-[clamp(4rem,8.5vw,9.6rem)] font-[520] leading-[0.82] tracking-[-0.072em] text-[#f5fff6]">
              See value
              <span className="block bg-gradient-to-r from-[#f5fff6] via-[#cfffad] to-[#00d9ff] bg-clip-text text-transparent">
                before it moves.
              </span>
            </h1>

            <p className="mt-8 max-w-[610px] text-[15px] leading-7 text-white/50 sm:text-[18px]">
              Empire turns live market evidence into commercial priority, governed action
              and verified economic truth.
            </p>

            <div className="mt-9 flex flex-wrap gap-3">
              <a
                href="#signals"
                className="group inline-flex min-h-12 items-center gap-3 rounded-full bg-[#b5ff7f] px-5 text-[10px] font-black tracking-[0.1em] text-[#061004] shadow-[0_0_50px_rgba(157,255,74,.11)] transition hover:-translate-y-0.5"
              >
                ENTER THE SYSTEM
                <ArrowDown className="size-3.5 transition-transform group-hover:translate-y-0.5" />
              </a>
              <a
                href="/industries"
                className="inline-flex min-h-12 items-center gap-3 rounded-full border border-white/10 bg-black/20 px-5 text-[10px] font-black tracking-[0.1em] text-white/62 backdrop-blur-xl transition hover:border-white/20 hover:text-white"
              >
                EXPLORE INDUSTRIES
              </a>
            </div>
          </motion.div>

          <div className="mt-20 grid max-w-[760px] grid-cols-2 gap-px overflow-hidden rounded-2xl border border-white/[0.07] bg-white/[0.07] sm:grid-cols-4">
            {[
              [Radar, "SIGNALS", "live evidence"],
              [Crosshair, "PRIORITY", "why now"],
              [Braces, "EXECUTION", "governed"],
              [CircleDollarSign, "TRUTH", "recognized"],
            ].map(([Icon, label, sub]) => {
              const ItemIcon = Icon as typeof Gauge;
              return (
                <div key={String(label)} className="bg-[#050806]/85 p-4 backdrop-blur-xl">
                  <ItemIcon className="size-3.5 text-[#9dff4a]/70" />
                  <div className="mt-5 text-[9px] font-black tracking-[0.18em] text-white/70">
                    {String(label)}
                  </div>
                  <div className="mt-1 text-[9px] text-white/28">{String(sub)}</div>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {chapters.map((chapter) => (
        <Chapter key={chapter.id} chapter={chapter} />
      ))}

      <section className="relative z-10 flex min-h-screen items-center px-5 py-28 md:px-10 lg:px-14">
        <div className="mx-auto w-full max-w-[1480px]">
          <div className="max-w-[940px]">
            <div className="mb-6 flex items-center gap-3 text-[9px] font-black tracking-[0.22em] text-[#9dff4a]">
              <Sparkles className="size-3.5" />
              THE MACHINE LEARNS FROM ECONOMIC TRUTH
            </div>
            <h2 className="text-[clamp(3.4rem,7vw,8.2rem)] font-[520] leading-[0.86] tracking-[-0.064em]">
              Build the loop.
              <span className="block text-white/24">Own the intelligence.</span>
            </h2>
            <div className="mt-10 flex flex-wrap gap-3">
              <a
                href="mailto:founder@empire-ai.co.uk"
                className="group inline-flex min-h-12 items-center gap-3 rounded-full bg-[#b5ff7f] px-5 text-[10px] font-black tracking-[0.1em] text-[#061004] transition hover:-translate-y-0.5"
              >
                TALK TO EMPIRE
                <ArrowRight className="size-3.5 transition-transform group-hover:translate-x-1" />
              </a>
              <a
                href="/trust"
                className="inline-flex min-h-12 items-center gap-3 rounded-full border border-white/10 bg-black/25 px-5 text-[10px] font-black tracking-[0.1em] text-white/65 backdrop-blur-xl"
              >
                <ShieldCheck className="size-3.5" />
                TRUST & EVIDENCE
              </a>
            </div>
          </div>
        </div>
      </section>

      <footer className="relative z-10 border-t border-white/[0.07] bg-black/35 px-5 py-8 backdrop-blur-2xl md:px-10 lg:px-14">
        <div className="mx-auto flex max-w-[1480px] flex-col justify-between gap-6 sm:flex-row sm:items-center">
          <Mark />
          <p className="max-w-xl text-[10px] leading-5 text-white/30">
            Predictive revenue infrastructure · evidence before action · economic truth before claims.
          </p>
        </div>
      </footer>
    </main>
  );
}
