import type { Metadata } from "next";
import { ArrowRight, CircleDot } from "lucide-react";
import { industryPages } from "@/lib/industry-pages";

export const metadata: Metadata = {
  title: "Industry Intelligence | Empire AI",
  description:
    "Evidence-backed market intelligence across property, private capital, solar, HVAC, roofing and legal markets.",
  alternates: {
    canonical: "/industries",
  },
  openGraph: {
    title: "Industry Intelligence | Empire AI",
    description:
      "Evidence-backed market intelligence across property, private capital, solar, HVAC, roofing and legal markets.",
    url: "https://empire-ai.co.uk/industries",
    siteName: "Empire AI",
    type: "website",
    images: [
      {
        url: "/brand/empire-logo.svg",
        width: 560,
        height: 128,
        alt: "Empire AI Predictive Revenue",
      },
    ],
  },
};

export default function IndustriesPage() {
  return (
    <main className="min-h-screen bg-[#020403] text-[#F4FFF9]">
      <div className="pointer-events-none fixed inset-0 bg-[radial-gradient(circle_at_80%_8%,rgba(0,229,255,0.08),transparent_30rem),radial-gradient(circle_at_10%_35%,rgba(124,255,0,0.055),transparent_34rem)]" />
      <div className="relative z-10 mx-auto w-[min(1380px,calc(100%-32px))] py-16 sm:py-24">
        <a href="/" className="text-xs font-black tracking-[0.2em] text-[#7CFF00]">
          ← EMPIRE AI
        </a>
        <p className="mt-20 text-[10px] font-black tracking-[0.24em] text-[#00E5FF]">
          INTELLIGENCE NODES
        </p>
        <h1 className="mt-6 max-w-5xl text-[clamp(3.4rem,7vw,7rem)] font-[560] leading-[0.91] tracking-[-0.06em]">
          Markets become more useful when the signals connect.
        </h1>
        <p className="mt-7 max-w-3xl text-[16px] leading-8 text-white/48">
          Empire combines market, company, property, buyer, search and event evidence into
          specialist intelligence nodes. These pages are the public surface of that system.
        </p>

        <div className="mt-16 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {industryPages.map((page) => (
            <a
              key={page.slug}
              href={`/industries/${page.slug}`}
              className="group min-h-[310px] rounded-3xl border border-white/[0.08] bg-white/[0.02] p-7 transition duration-300 hover:-translate-y-1 hover:border-[#00E5FF]/25 hover:bg-[#00E5FF]/[0.025]"
            >
              <div className="flex items-center justify-between">
                <CircleDot className="size-4 text-[#7CFF00]/65" />
                <ArrowRight className="size-4 text-white/20 transition group-hover:translate-x-1 group-hover:text-[#00E5FF]" />
              </div>
              <p className="mt-20 text-[9px] font-black tracking-[0.18em] text-[#00E5FF]/65">
                {page.eyebrow}
              </p>
              <h2 className="mt-4 text-2xl font-semibold leading-tight tracking-[-0.03em]">
                {page.title}
              </h2>
              <p className="mt-4 text-sm leading-6 text-white/38">{page.subtitle}</p>
            </a>
          ))}
        </div>
      </div>
    </main>
  );
}
