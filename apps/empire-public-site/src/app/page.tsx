"use client";

import { ArrowRight } from "lucide-react";
import EmpireWorld from "@/components/EmpireWorld";

function Brand() {
  return (
    <a
      href="/"
      className="pointer-events-auto flex items-center gap-3"
      aria-label="Empire AI home"
    >
      <span className="relative grid size-9 place-items-center overflow-hidden rounded-[10px] border border-white/10 bg-black/40 backdrop-blur-xl">
        <span className="absolute inset-[5px] rounded-[7px] border border-[#9dff4a]/30" />
        <span className="font-black text-[#a6ff6a]">E</span>
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
  return (
    <main className="relative h-screen w-screen overflow-hidden bg-[#020403] text-white">
      <EmpireWorld />

      <div className="pointer-events-none fixed inset-0 z-20 bg-[radial-gradient(circle_at_50%_42%,transparent_0%,rgba(2,4,3,.02)_42%,rgba(2,4,3,.62)_100%)]" />
      <div className="pointer-events-none fixed inset-0 z-20 bg-[linear-gradient(90deg,rgba(2,4,3,.46),transparent_28%,transparent_72%,rgba(2,4,3,.36))]" />

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
              className="group inline-flex items-center gap-2 rounded-full border border-[#9dff4a]/25 bg-[#9dff4a]/[0.08] px-4 py-2.5 text-[8px] font-black tracking-[0.12em] text-[#cfffad] backdrop-blur-xl transition hover:border-[#9dff4a]/55"
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
