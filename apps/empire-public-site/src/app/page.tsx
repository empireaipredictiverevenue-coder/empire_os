"use client";

import { ArrowRight, ChevronDown } from "lucide-react";
import dynamic from "next/dynamic";
import { useEffect, useMemo, useState } from "react";

const EmpireWorld = dynamic(() => import("@/components/EmpireWorld"), {
  ssr: false,
  loading: () => null,
});

const CHAPTERS = [
  {
    label: "Signal Intelligence",
    eyebrow: "01 · MARKET INTELLIGENCE",
    title: "Know where revenue is forming before the market reacts.",
    body:
      "Empire continuously interprets demand, search, storm, company, buyer and competitive signals—then separates meaningful commercial movement from noise.",
  },
  {
    label: "Predictive Priority",
    eyebrow: "02 · PREDICTIVE REVENUE",
    title: "Turn evidence into a ranked commercial advantage.",
    body:
      "Omega, Cortex and the intelligence fabric score what matters now: who, where, why now, expected economics and the evidence supporting every decision.",
  },
  {
    label: "Opportunity Resolution",
    eyebrow: "03 · OPPORTUNITY RESOLUTION",
    title: "Resolve the route from signal to buyer.",
    body:
      "Identity, decision-maker, market context, intent, economics and fulfilment are assembled into one commercial opportunity before execution begins.",
  },
  {
    label: "Autonomous Execution",
    eyebrow: "04 · GOVERNED EXECUTION",
    title: "Let agents move at machine speed. Keep authority under control.",
    body:
      "Research, search, outreach, conversation, delivery and learning operate as one governed system—with material commitments still held behind explicit gates.",
  },
  {
    label: "Economic Truth",
    eyebrow: "05 · ECONOMIC TRUTH",
    title: "Close the loop on what actually created value.",
    body:
      "Verified payment, fulfilment, recognized revenue and realized gross profit become the learning signal. Forecasts remain forecasts. Revenue remains evidence.",
  },
] as const;

const CHAPTER_TARGETS = [0.24, 0.44, 0.63, 0.8, 0.94] as const;

function FallbackEngine() {
  return (
    <div className="pointer-events-none fixed inset-0 z-10 overflow-hidden bg-[#020817]">
      <div className="empire-fallback-engine">
        <div className="empire-fallback-ring empire-fallback-ring-a" />
        <div className="empire-fallback-ring empire-fallback-ring-b" />
        <div className="empire-fallback-ring empire-fallback-ring-c" />
        <div className="empire-fallback-core" />
        {Array.from({ length: 12 }, (_, index) => (
          <span
            key={index}
            className="empire-fallback-shard"
            style={{
              ["--i" as string]: index,
            }}
          />
        ))}
      </div>
    </div>
  );
}

function Brand() {
  return (
    <a
      href="/"
      className="pointer-events-auto flex items-center gap-3"
      aria-label="Empire AI home"
    >
      <span className="relative grid size-10 place-items-center overflow-hidden rounded-xl border border-[#4f8cff]/25 bg-[#06112c]/85 shadow-[0_0_40px_rgba(37,99,235,.16)] backdrop-blur-xl">
        <span className="absolute inset-[6px] rounded-[7px] border border-[#60a5fa]/35" />
        <span className="font-black text-[#93c5fd]">E</span>
      </span>
      <span>
        <strong className="block text-[11px] font-semibold tracking-[0.22em] text-white">
          EMPIRE AI
        </strong>
        <small className="mt-1 block text-[7px] font-medium tracking-[0.28em] text-white/35">
          PREDICTIVE REVENUE
        </small>
      </span>
    </a>
  );
}

function jumpToChapter(target: number) {
  window.dispatchEvent(
    new CustomEvent("empire-jump", {
      detail: { target },
    }),
  );
}

export default function Home() {
  const [mountWorld, setMountWorld] = useState(false);
  const [worldReady, setWorldReady] = useState(false);
  const [webglSupported, setWebglSupported] = useState<boolean | null>(null);
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    const canvas = document.createElement("canvas");
    let supported = false;
    try {
      supported = Boolean(
        canvas.getContext("webgl2") || canvas.getContext("webgl"),
      );
    } catch {
      supported = false;
    }
    setWebglSupported(supported);

    if (!supported) return;
    const id = window.requestAnimationFrame(() => setMountWorld(true));
    return () => window.cancelAnimationFrame(id);
  }, []);

  const activeChapter = useMemo(() => {
    if (progress < 0.14) return -1;
    if (progress < 0.34) return 0;
    if (progress < 0.54) return 1;
    if (progress < 0.73) return 2;
    if (progress < 0.88) return 3;
    return 4;
  }, [progress]);

  const active = activeChapter < 0 ? null : CHAPTERS[activeChapter as 0 | 1 | 2 | 3 | 4];

  return (
    <main className="relative h-screen w-screen overflow-hidden bg-[#020817] text-white">
      {mountWorld && webglSupported ? (
        <EmpireWorld
          onReady={() => setWorldReady(true)}
          onProgress={setProgress}
        />
      ) : null}

      {!worldReady ? <FallbackEngine /> : null}

      <div className="pointer-events-none fixed inset-0 z-20 bg-[radial-gradient(circle_at_62%_45%,rgba(37,99,235,.06),transparent_34%,rgba(2,8,23,.74)_100%)]" />
      <div className="pointer-events-none fixed inset-0 z-20 bg-[linear-gradient(90deg,rgba(2,8,23,.72),rgba(2,8,23,.28)_42%,rgba(2,8,23,.06)_67%,rgba(2,8,23,.34))]" />

      <header className="pointer-events-none fixed inset-x-0 top-0 z-50 px-5 py-5 md:px-8 lg:px-12">
        <div className="mx-auto flex max-w-[1560px] items-center justify-between">
          <Brand />
          <div className="pointer-events-auto flex items-center gap-2">
            <a href="/industries" className="hidden rounded-full border border-white/[0.09] bg-[#07142f]/70 px-4 py-2.5 text-[9px] font-semibold tracking-[0.14em] text-white/55 backdrop-blur-2xl transition hover:border-[#60a5fa]/35 hover:text-white sm:inline-flex">
              INDUSTRIES
            </a>
            <a href="/trust" className="hidden rounded-full border border-white/[0.09] bg-[#07142f]/70 px-4 py-2.5 text-[9px] font-semibold tracking-[0.14em] text-white/55 backdrop-blur-2xl transition hover:border-[#60a5fa]/35 hover:text-white md:inline-flex">
              TRUST
            </a>
            <a href="mailto:founder@empire-ai.co.uk" className="group inline-flex items-center gap-2 rounded-full border border-[#60a5fa]/35 bg-[#2563eb]/15 px-4 py-2.5 text-[9px] font-semibold tracking-[0.12em] text-[#dbeafe] shadow-[0_0_30px_rgba(37,99,235,.12)] backdrop-blur-2xl transition hover:border-[#7dd3fc]/60 hover:bg-[#2563eb]/22">
              START A CONVERSATION
              <ArrowRight className="size-3 transition-transform group-hover:translate-x-0.5" />
            </a>
          </div>
        </div>
      </header>

      <aside className="pointer-events-auto fixed right-5 top-1/2 z-50 hidden -translate-y-1/2 flex-col gap-2 xl:flex">
        {CHAPTERS.map((chapter, index) => {
          const target = CHAPTER_TARGETS[index];
          const selected = activeChapter === index;
          return (
            <button
              key={chapter.label}
              type="button"
              onClick={() => jumpToChapter(target)}
              className={"group flex items-center justify-end gap-3 rounded-full px-3 py-2 text-right transition " + (selected ? "bg-[#0b1f4b]/82 text-white shadow-[0_0_30px_rgba(37,99,235,.14)]" : "text-white/28 hover:bg-white/[0.04] hover:text-white/65")}
            >
              <span className="max-w-0 overflow-hidden whitespace-nowrap text-[8px] font-semibold tracking-[0.12em] transition-all duration-300 group-hover:max-w-40">
                {chapter.label.toUpperCase()}
              </span>
              <span className={"block rounded-full transition-all " + (selected ? "h-2 w-2 bg-[#7dd3fc] shadow-[0_0_16px_rgba(125,211,252,.75)]" : "h-1.5 w-1.5 bg-white/25")} />
            </button>
          );
        })}
      </aside>

      <div className="pointer-events-none fixed inset-0 z-30 flex items-end px-5 pb-14 md:px-8 md:pb-16 lg:px-12 lg:pb-20">
        <div className="mx-auto w-full max-w-[1560px]">
          <div className="max-w-[780px]">
            {active ? (
              <div key={active.eyebrow} className="animate-[fadeIn_.45s_ease-out]">
                <div className="mb-5 flex items-center gap-3 text-[9px] font-semibold tracking-[0.22em] text-[#60a5fa]">
                  <span className="h-px w-8 bg-gradient-to-r from-[#60a5fa] to-transparent" />
                  {active.eyebrow}
                </div>
                <h2 className="max-w-[780px] text-[clamp(3rem,6vw,6.8rem)] font-medium leading-[0.88] tracking-[-0.055em] text-[#f8fbff]">
                  {active.title}
                </h2>
                <p className="mt-6 max-w-[620px] text-[14px] leading-7 text-[#b7c5dd]/72 sm:text-[16px]">
                  {active.body}
                </p>
              </div>
            ) : (
              <div>
                <div className="mb-5 flex items-center gap-3 text-[9px] font-semibold tracking-[0.22em] text-[#60a5fa]">
                  <span className="size-1.5 rounded-full bg-[#60a5fa] shadow-[0_0_18px_rgba(96,165,250,.8)]" />
                  PREDICTIVE REVENUE INFRASTRUCTURE
                </div>
                <h1 className="max-w-[980px] text-[clamp(4rem,8.4vw,9.2rem)] font-medium leading-[0.82] tracking-[-0.068em] text-[#f8fbff]">
                  Intelligence that
                  <span className="block bg-gradient-to-r from-[#f8fbff] via-[#bfdbfe] to-[#67e8f9] bg-clip-text text-transparent">
                    moves before revenue does.
                  </span>
                </h1>
                <p className="mt-7 max-w-[650px] text-[15px] leading-7 text-[#b7c5dd]/72 sm:text-[18px]">
                  Empire is the predictive revenue infrastructure layer for discovering where value is forming, deciding what deserves action, and turning verified market evidence into governed commercial execution.
                </p>
                <div className="pointer-events-auto mt-8 flex flex-wrap gap-3">
                  <button type="button" onClick={() => jumpToChapter(CHAPTER_TARGETS[0])} className="group inline-flex min-h-12 items-center gap-3 rounded-full bg-[#eaf2ff] px-5 text-[9px] font-semibold tracking-[0.13em] text-[#07132c] shadow-[0_10px_45px_rgba(59,130,246,.22)] transition hover:-translate-y-0.5 hover:bg-white">
                    ENTER THE SYSTEM
                    <ChevronDown className="size-3.5 transition-transform group-hover:translate-y-0.5" />
                  </button>
                  <a href="/industries" className="inline-flex min-h-12 items-center rounded-full border border-white/10 bg-[#08152f]/65 px-5 text-[9px] font-semibold tracking-[0.13em] text-white/60 backdrop-blur-2xl transition hover:border-[#60a5fa]/30 hover:text-white">
                    EXPLORE INDUSTRIES
                  </a>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {webglSupported === false ? (
        <div className="pointer-events-none fixed bottom-5 left-5 z-40 text-[7px] font-medium tracking-[0.18em] text-white/25 md:left-12">
          MOTION FALLBACK ACTIVE
        </div>
      ) : null}

      <div className="pointer-events-none fixed bottom-5 right-5 z-40 hidden items-center gap-3 text-[7px] font-medium tracking-[0.18em] text-white/25 md:flex lg:right-12">
        SCROLL TO TRAVEL
        <span className="h-px w-8 bg-white/15" />
      </div>
    </main>
  );
}