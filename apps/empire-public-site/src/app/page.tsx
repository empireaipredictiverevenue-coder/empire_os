"use client";

import { motion } from "motion/react";
import {
  ArrowRight,
  Bot,
  BrainCircuit,
  ChartNoAxesCombined,
  CircleDollarSign,
  Globe2,
  Radar,
  Search,
  ShieldCheck,
  Sparkles,
  Workflow,
} from "lucide-react";
import EmpireWorld from "@/components/EmpireWorld";

const stages = [
  ["01", "Detect", "Real signals, markets, buyers, search demand and events."],
  ["02", "Discover", "Find valuable gaps across demand, supply and distribution."],
  ["03", "Predict", "Estimate economics without confusing forecast with actual."],
  ["04", "Execute", "Coordinate governed GTM, search, conversations and fulfilment."],
  ["05", "Learn", "Feed recognized revenue, realized GP and outcomes back in."],
];

const capabilities = [
  "Global Opportunity Graph",
  "Opportunity Foundry",
  "Predictive Revenue",
  "Buyer Intelligence",
  "Search / AEO / GEO",
  "Revenue Exchange",
  "Conversation Intelligence",
  "Economic Memory",
];

const pillars = [
  {
    icon: Globe2,
    number: "01",
    title: "Global Opportunity Graph",
    copy: "Markets, companies, buyers, demand, products, events and outcomes joined by provenance.",
  },
  {
    icon: Radar,
    number: "02",
    title: "Opportunity Foundry",
    copy: "Continuously discover where demand, supply, information or buyer capacity is misaligned.",
  },
  {
    icon: BrainCircuit,
    number: "03",
    title: "Economic Memory",
    copy: "Learn what actually creates recognized revenue and realized gross profit.",
  },
];

function Kicker({ children }: { children: React.ReactNode }) {
  return (
    <p className="mb-5 text-[10px] font-black tracking-[0.28em] text-[#7CFF00]">
      {children}
    </p>
  );
}

function GlowButton({
  href,
  children,
  variant = "primary",
}: {
  href: string;
  children: React.ReactNode;
  variant?: "primary" | "ghost";
}) {
  const primary =
    "bg-gradient-to-r from-[#7CFF00] via-[#5CFF79] to-[#00E5FF] text-[#020403] shadow-[0_0_40px_rgba(124,255,0,0.14)]";
  const ghost =
    "border border-white/10 bg-white/[0.025] text-white/80 hover:border-[#00E5FF]/40 hover:text-white";
  return (
    <a
      href={href}
      className={`group inline-flex min-h-12 items-center gap-2 rounded-full px-5 text-xs font-extrabold transition-all duration-300 hover:-translate-y-0.5 ${variant === "primary" ? primary : ghost}`}
    >
      {children}
      <ArrowRight className="size-3.5 transition-transform group-hover:translate-x-1" />
    </a>
  );
}

export default function Home() {
  return (
    <main className="min-h-screen overflow-hidden bg-[#020403] text-[#F4FFF9] selection:bg-[#7CFF00] selection:text-black">
      <div className="pointer-events-none fixed inset-0 z-0 bg-[radial-gradient(circle_at_78%_5%,rgba(0,229,255,0.09),transparent_30rem),radial-gradient(circle_at_8%_32%,rgba(124,255,0,0.07),transparent_34rem)]" />

      <nav className="relative z-40 mx-auto flex h-20 w-[min(1480px,calc(100%-32px))] items-center justify-between border-b border-white/[0.07]">
        <a href="#top" className="flex items-center gap-3">
          <span className="grid size-10 place-items-center rounded-xl border border-[#7CFF00]/25 bg-[#7CFF00]/[0.055] font-black text-[#7CFF00] shadow-[inset_0_1px_0_rgba(255,255,255,.07)]">
            E
          </span>
          <span>
            <strong className="block text-[11px] tracking-[0.22em]">EMPIRE AI</strong>
            <small className="mt-1 block text-[8px] tracking-[0.23em] text-white/35">
              PREDICTIVE REVENUE
            </small>
          </span>
        </a>

        <div className="hidden items-center gap-8 text-[11px] font-semibold text-white/45 lg:flex">
          <a className="transition hover:text-[#7CFF00]" href="#system">System</a>
          <a className="transition hover:text-[#7CFF00]" href="#opportunity">Opportunity</a>
          <a className="transition hover:text-[#00E5FF]" href="#global">Global</a>
          <a className="transition hover:text-[#00E5FF]" href="/agent-web/capabilities">Agent Web</a>
        </div>

        <a
          href="#contact"
          className="rounded-full border border-[#00E5FF]/20 bg-[#00E5FF]/[0.045] px-4 py-2.5 text-[11px] font-bold text-[#B8F8FF] transition hover:border-[#00E5FF]/50"
        >
          Talk to Empire
        </a>
      </nav>

      <section
        id="top"
        className="relative z-10 mx-auto grid min-h-[780px] w-[min(1480px,calc(100%-32px))] items-center gap-4 lg:grid-cols-[0.95fr_1.05fr]"
      >
        <div className="relative z-10 py-20 lg:py-28">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7 }}
          >
            <Kicker>GLOBAL PREDICTIVE REVENUE INFRASTRUCTURE</Kicker>
            <h1 className="max-w-[900px] text-[clamp(3.4rem,6.5vw,7rem)] font-[560] leading-[0.91] tracking-[-0.06em]">
              Find the opportunity.
              <span className="block bg-gradient-to-r from-white via-[#B6FFDD] to-[#00E5FF] bg-clip-text text-transparent">
                Predict the economics.
              </span>
              Turn evidence into revenue.
            </h1>

            <p className="mt-8 max-w-2xl text-[15px] leading-7 text-white/50 sm:text-[17px]">
              Empire AI connects real commercial signals, global market intelligence,
              buyer demand and governed AI execution into one continuously learning revenue system.
            </p>

            <div className="mt-8 flex flex-wrap gap-3">
              <GlowButton href="#opportunity">Explore the system</GlowButton>
              <GlowButton href="/.well-known/agent-card.json" variant="ghost">
                Agent access
              </GlowButton>
            </div>
          </motion.div>

          <div className="mt-14 flex flex-wrap items-center gap-3 text-[8px] font-black tracking-[0.18em] text-white/30">
            {["REAL DATA", "VERIFIED EVIDENCE", "RECOGNIZED REVENUE", "REALIZED GP"].map(
              (item, index) => (
                <div key={item} className="flex items-center gap-3">
                  <span>{item}</span>
                  {index < 3 && <span className="size-1 rounded-full bg-[#7CFF00]/35" />}
                </div>
              ),
            )}
          </div>
        </div>

        <motion.div
          initial={{ opacity: 0, scale: 0.96 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 1, delay: 0.12 }}
          className="relative -mt-10 h-[470px] lg:mt-0 lg:h-[720px]"
        >
          <EmpireWorld />
          <div className="pointer-events-none absolute inset-x-[14%] bottom-[8%] h-16 rounded-full bg-[#00E5FF]/10 blur-3xl" />
          <div className="pointer-events-none absolute inset-x-[25%] bottom-[12%] h-12 rounded-full bg-[#7CFF00]/10 blur-3xl" />
        </motion.div>
      </section>

      <section className="relative z-10 overflow-hidden border-y border-white/[0.07] bg-white/[0.012]">
        <motion.div
          className="flex w-max gap-7 py-4"
          animate={{ x: ["0%", "-50%"] }}
          transition={{ duration: 28, repeat: Infinity, ease: "linear" }}
        >
          {capabilities.concat(capabilities).map((item, index) => (
            <span
              key={`${item}-${index}`}
              className="flex items-center gap-7 text-[9px] font-extrabold uppercase tracking-[0.17em] text-white/35"
            >
              {item}
              <Sparkles className="size-3 text-[#7CFF00]/50" />
            </span>
          ))}
        </motion.div>
      </section>

      <section
        id="system"
        className="relative z-10 mx-auto w-[min(1480px,calc(100%-32px))] py-28 lg:py-36"
      >
        <div className="max-w-4xl">
          <Kicker>ONE OPERATING SYSTEM</Kicker>
          <h2 className="text-[clamp(2.8rem,5vw,5rem)] font-[560] leading-[0.96] tracking-[-0.05em]">
            From signal to economic truth.
          </h2>
          <p className="mt-6 max-w-2xl text-[15px] leading-7 text-white/45">
            Not another dashboard full of predictions. Empire separates what might happen
            from what actually happened — then learns from the difference.
          </p>
        </div>

        <div className="mt-16 grid border-t border-white/[0.08] sm:grid-cols-2 lg:grid-cols-5">
          {stages.map(([number, title, copy], index) => (
            <motion.article
              key={number}
              initial={{ opacity: 0, y: 24 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-10%" }}
              transition={{ duration: 0.45, delay: index * 0.06 }}
              className="min-h-60 border-b border-white/[0.08] py-7 pr-6 sm:border-r lg:border-b-0 [&:nth-child(even)]:sm:pl-6 lg:[&:nth-child(even)]:pl-6"
            >
              <span className="text-[10px] text-white/25">{number}</span>
              <h3 className="mt-20 text-xl font-semibold">{title}</h3>
              <p className="mt-3 text-[13px] leading-6 text-white/40">{copy}</p>
            </motion.article>
          ))}
        </div>
      </section>

      <section
        id="opportunity"
        className="relative z-10 border-y border-white/[0.07] bg-gradient-to-br from-[#7CFF00]/[0.035] via-[#020403] to-[#00E5FF]/[0.035] py-28"
      >
        <div className="mx-auto grid w-[min(1480px,calc(100%-32px))] items-center gap-16 lg:grid-cols-2">
          <div>
            <Kicker>OPPORTUNITY FOUNDRY</Kicker>
            <h2 className="max-w-3xl text-[clamp(2.8rem,5vw,5rem)] font-[560] leading-[0.96] tracking-[-0.05em]">
              Empire looks for where value is missing.
            </h2>
            <p className="mt-6 max-w-xl text-[15px] leading-7 text-white/45">
              Across markets, cities, industries, buyers, supply, search demand,
              distribution and pricing — then validates opportunities before scale.
            </p>
          </div>

          <div className="relative mx-auto grid aspect-square w-full max-w-[560px] place-items-center">
            <div className="absolute inset-[8%] rounded-full border border-[#7CFF00]/10" />
            <div className="absolute inset-[20%] rounded-full border border-dashed border-[#00E5FF]/15" />
            <div className="absolute inset-[32%] rounded-full border border-[#7CFF00]/15" />
            <motion.div
              className="absolute inset-[8%] rounded-full border-t border-[#7CFF00]/60"
              animate={{ rotate: 360 }}
              transition={{ duration: 18, repeat: Infinity, ease: "linear" }}
            />
            <motion.div
              className="absolute inset-[20%] rounded-full border-b border-[#00E5FF]/65"
              animate={{ rotate: -360 }}
              transition={{ duration: 25, repeat: Infinity, ease: "linear" }}
            />

            <div className="grid size-32 place-items-center rounded-full bg-[radial-gradient(circle_at_35%_30%,#D9FFB2,#7CFF00_35%,#154200_85%)] text-[9px] font-black tracking-[0.17em] text-black shadow-[0_0_80px_rgba(124,255,0,.17)]">
              OPPORTUNITY
            </div>

            {[
              ["DEMAND", "top-[9%] left-[43%]"],
              ["SUPPLY", "top-[31%] right-[2%]"],
              ["BUYERS", "bottom-[14%] right-[14%]"],
              ["SEARCH", "bottom-[8%] left-[24%]"],
              ["EVENTS", "top-[42%] left-[0%]"],
              ["PRICING", "top-[20%] left-[13%]"],
            ].map(([label, position]) => (
              <span
                key={label}
                className={`absolute ${position} rounded-full border border-white/10 bg-black/70 px-3 py-2 text-[8px] font-bold tracking-[0.15em] text-white/45 backdrop-blur-xl`}
              >
                {label}
              </span>
            ))}
          </div>
        </div>
      </section>
      <section
        id="global"
        className="relative z-10 mx-auto w-[min(1480px,calc(100%-32px))] py-28 lg:py-36"
      >
        <div className="grid items-end gap-10 lg:grid-cols-[1.2fr_0.8fr]">
          <div>
            <Kicker>GLOBAL BY DESIGN</Kicker>
            <h2 className="max-w-4xl text-[clamp(2.8rem,5vw,5rem)] font-[560] leading-[0.96] tracking-[-0.05em]">
              Build once. Enter markets evidence-first.
            </h2>
          </div>
          <p className="max-w-xl text-[15px] leading-7 text-white/45">
            Countries, regions, metros, niches, currencies, languages and jurisdiction-specific
            rules plug into one operating system rather than becoming disconnected stacks.
          </p>
        </div>

        <div className="mt-16 grid gap-3 lg:grid-cols-3">
          {pillars.map((pillar, index) => {
            const Icon = pillar.icon;
            return (
              <motion.article
                key={pillar.title}
                initial={{ opacity: 0, y: 24 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: index * 0.08 }}
                className="group min-h-[320px] rounded-3xl border border-white/[0.08] bg-white/[0.02] p-7 transition duration-500 hover:border-[#00E5FF]/25 hover:bg-[#00E5FF]/[0.025]"
              >
                <div className="flex items-center justify-between">
                  <span className="text-[10px] text-white/25">{pillar.number}</span>
                  <Icon className="size-5 text-[#7CFF00]/60 transition group-hover:text-[#00E5FF]" />
                </div>
                <h3 className="mt-32 text-2xl font-semibold tracking-[-0.025em]">
                  {pillar.title}
                </h3>
                <p className="mt-3 max-w-sm text-[13px] leading-6 text-white/40">
                  {pillar.copy}
                </p>
              </motion.article>
            );
          })}
        </div>
      </section>

      <section className="relative z-10 border-y border-white/[0.07] bg-white/[0.012] py-28">
        <div className="mx-auto grid w-[min(1480px,calc(100%-32px))] gap-16 lg:grid-cols-[0.9fr_1.1fr]">
          <div>
            <Kicker>EVIDENCE-FIRST AI</Kicker>
            <h2 className="text-[clamp(2.8rem,5vw,5rem)] font-[560] leading-[0.96] tracking-[-0.05em]">
              Unknown stays unknown.
            </h2>
          </div>

          <div className="border-t border-white/[0.08]">
            {[
              [ChartNoAxesCombined, "FORECAST", "never masquerades as actual revenue."],
              [ShieldCheck, "PAYMENT", "is independently verified."],
              [CircleDollarSign, "REVENUE", "is recognized only from governed evidence."],
              [Workflow, "GP", "appears only when observed cost evidence exists."],
            ].map(([Icon, label, copy]) => {
              const ItemIcon = Icon as typeof Search;
              return (
                <div
                  key={String(label)}
                  className="grid grid-cols-[32px_110px_1fr] items-center gap-4 border-b border-white/[0.08] py-5"
                >
                  <ItemIcon className="size-4 text-[#00E5FF]/55" />
                  <span className="text-[9px] font-black tracking-[0.16em] text-[#7CFF00]/80">
                    {String(label)}
                  </span>
                  <p className="m-0 text-[13px] text-white/45">{String(copy)}</p>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      <section
        id="contact"
        className="relative z-10 mx-auto w-[min(1180px,calc(100%-32px))] py-36 text-center lg:py-44"
      >
        <Bot className="mx-auto mb-7 size-7 text-[#00E5FF]/60" />
        <Kicker>BUILD THE NEXT REVENUE ENGINE</Kicker>
        <h2 className="text-[clamp(3rem,6vw,6rem)] font-[560] leading-[0.92] tracking-[-0.055em]">
          Your market is moving.
          <span className="block bg-gradient-to-r from-[#7CFF00] to-[#00E5FF] bg-clip-text text-transparent">
            Empire is built to see it first.
          </span>
        </h2>
        <p className="mx-auto mt-7 max-w-xl text-[15px] leading-7 text-white/45">
          For enterprise buyers, strategic partners and companies building predictable growth.
        </p>
        <div className="mt-9 flex flex-wrap justify-center gap-3">
          <GlowButton href="mailto:founder@empire-ai.co.uk">Start a conversation</GlowButton>
          <GlowButton href="/agent-web/capabilities" variant="ghost">
            Explore Agent Web
          </GlowButton>
        </div>
      </section>
      <footer className="relative z-10 mx-auto flex min-h-32 w-[min(1480px,calc(100%-32px))] flex-col justify-between gap-6 border-t border-white/[0.07] py-8 sm:flex-row sm:items-center">
        <div className="flex items-center gap-3">
          <span className="grid size-10 place-items-center rounded-xl border border-[#7CFF00]/25 bg-[#7CFF00]/[0.055] font-black text-[#7CFF00]">
            E
          </span>
          <span>
            <strong className="block text-[11px] tracking-[0.22em]">EMPIRE AI</strong>
            <small className="mt-1 block text-[8px] tracking-[0.23em] text-white/30">
              PREDICTIVE REVENUE
            </small>
          </span>
        </div>
        <p className="text-[11px] text-white/30">
          Global predictive revenue infrastructure · governed by evidence.
        </p>
      </footer>
    </main>
  );
}
