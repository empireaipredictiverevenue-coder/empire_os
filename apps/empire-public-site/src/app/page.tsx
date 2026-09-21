"use client";

import { ArrowRight } from "lucide-react";
import dynamic from "next/dynamic";
import { useEffect, useState } from "react";

const EmpireWorld = dynamic(() => import("@/components/EmpireWorld"), {
  ssr: false,
  loading: () => null,
});

function Brand() {
  return (
    <a
      href="/"
      className="pointer-events-auto flex items-center gap-3"
      aria-label="Empire AI home"
    >
      <span className="relative grid size-9 place-items-center overflow-hidden rounded-[10px] border border-white/10 bg-black/40 backdrop-blur-xl">
        <span className="absolute inset-[5px] rounded-[7px] border border-[#4f8cff]/30" />
        <span className="font-black text-[#60a5fa]">E</span>
      </span>
      <span>
        <strong className="block text-[10px] tracking-[0.24em] text-white">
          EMPIRE AI
        </strong>
        <small className="mt-1 block text-[7px] tracking-[0.24em] text-white/35">
          PREDICTIVE REVENUE
        </small>
      </span>
    </a>
  );
}

export default function Home() {
  const [mountWorld, setMountWorld] = useState(false);
  const [worldReady, setWorldReady] = useState(false);

  useEffect(() => {
    const start = () => setMountWorld(true);
    const id = window.requestAnimationFrame(start);
    return () => window.cancelAnimationFrame(id);
  }, []);

  return (
    <main className="relative h-screen w-screen overflow-hidden bg-[#020817] text-white">
      {mountWorld ? <EmpireWorld onReady={() => setWorldReady(true)} /> : null}

      <div
        className={
          "pointer-events-none fixed inset-0 z-10 flex items-end px-5 pb-14 transition-opacity duration-1000 md:px-10 md:pb-20 lg:px-14 " +
          (worldReady ? "opacity-0" : "opacity-100")
        }
        aria-hidden={worldReady}
      >
        <div className="max-w-[820px]">
          <div className="mb-5 flex items-center gap-3 text-[9px] font-black tracking-[0.24em] text-[#60a5fa]">
            <span className="size-1.5 rounded-full bg-[#60a5fa] shadow-[0_0_18px_rgba(96,165,250,.8)]" />
            ENTER EMPIRE
          </div>
          <h1 className="text-[clamp(3.8rem,8vw,8.8rem)] font-[520] leading-[0.82] tracking-[-0.07em] text-[#f7fbff]">
            Step inside
            <span className="block bg-gradient-to-r from-[#f7fbff] via-[#bfdbfe] to-[#5ee7ff] bg-clip-text text-transparent">
              predictive revenue.
            </span>
          </h1>
          <p className="mt-6 max-w-xl text-[14px] leading-7 text-white/45 sm:text-[16px]">
            Loading the live revenue world. Scroll becomes camera travel once the 3D engine is ready.
          </p>
          <div className="mt-7 h-px w-52 overflow-hidden bg-white/10">
            <div className="h-full w-2/3 animate-pulse bg-gradient-to-r from-[#2563eb] via-[#60a5fa] to-[#5ee7ff]" />
          </div>
        </div>
      </div>

      <div className="pointer-events-none fixed inset-0 z-20 bg-[radial-gradient(circle_at_50%_42%,transparent_0%,rgba(2,8,23,.03)_42%,rgba(2,8,23,.68)_100%)]" />
      <div className="pointer-events-none fixed inset-0 z-20 bg-[linear-gradient(90deg,rgba(2,8,23,.54),transparent_28%,transparent_72%,rgba(2,8,23,.46))]" />

      <header className="pointer-events-none fixed inset-x-0 top-0 z-50 px-5 py-5 md:px-10 lg:px-14">
        <div className="mx-auto flex max-w-[1500px] items-center justify-between">
          <Brand />
          <div className="pointer-events-auto flex items-center gap-3">
            <a
              href="/industries"
              className="hidden rounded-full border border-white/10 bg-black/30 px-4 py-2.5 text-[8px] font-black tracking-[0.12em] text-white/50 backdrop-blur-xl transition hover:border-white/20 hover:text-white sm:inline-flex"
            >
              INDUSTRIES
            </a>
            <a
              href="mailto:founder@empire-ai.co.uk"
              className="group inline-flex items-center gap-2 rounded-full border border-[#4f8cff]/25 bg-[#4f8cff]/[0.08] px-4 py-2.5 text-[8px] font-black tracking-[0.12em] text-[#bfdbfe] backdrop-blur-xl transition hover:border-[#4f8cff]/55"
            >
              START A CONVERSATION
              <ArrowRight className="size-3 transition-transform group-hover:translate-x-0.5" />
            </a>
          </div>
        </div>
      </header>

      <div className="pointer-events-none fixed bottom-5 left-5 z-40 hidden items-center gap-3 text-[7px] font-black tracking-[0.18em] text-white/25 md:flex lg:left-14">
        <span className="h-px w-9 bg-white/15" />
        SCROLL = CAMERA TRAVEL
      </div>
    </main>
  );
}
