import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Trust Center | Empire AI",
  description:
    "How Empire AI handles evidence, security, commercial proof and trust.",
  alternates: {
    canonical: "/trust",
  },
};

const verified = [
  ["HTTPS", "Empire AI is served over HTTPS behind Cloudflare."],
  ["Browser security", "Content Security Policy, clickjacking protection, MIME sniffing protection and a strict referrer policy are live."],
  ["Email authentication", "SPF and DMARC records are present. DMARC is currently in monitoring mode while sender alignment is hardened."],
  ["Opt-out handling", "Observed unsubscribe requests are bound to canonical suppression so they are not treated as sales conversations."],
  ["Revenue truth", "Forecasts, quotes and payment requests are not counted as revenue. Revenue requires independently verifiable commercial evidence."],
];

const building = [
  ["DMARC enforcement", "Move from monitoring to staged enforcement after every legitimate sender is verified."],
  ["Security headers", "Review HSTS and Permissions-Policy before activation."],
  ["Deal Room", "Add signed-agreement evidence and exact counterparty binding through the governed Deal Room."],
  ["Customer proof", "Publish references and case studies only after genuine outcomes exist and can be evidenced."],
];

function EvidenceList({
  items,
}: {
  items: string[][];
}) {
  return (
    <div className="mt-8 divide-y divide-white/10 border-y border-white/10">
      {items.map(([title, copy]) => (
        <div key={title} className="grid gap-2 py-5 sm:grid-cols-[180px_1fr]">
          <strong className="text-sm text-white">{title}</strong>
          <p className="m-0 text-sm leading-6 text-white/55">{copy}</p>
        </div>
      ))}
    </div>
  );
}

export default function TrustPage() {
  return (
    <main className="min-h-screen bg-[#020403] text-[#F4FFF9]">
      <div className="mx-auto w-[min(980px,calc(100%-32px))] py-16 sm:py-24">
        <a href="/" className="text-xs font-bold tracking-[0.18em] text-[#7CFF00]">
          ← EMPIRE AI
        </a>

        <section className="mt-16">
          <p className="text-[10px] font-black tracking-[0.25em] text-[#00E5FF]">
            TRUST CENTER
          </p>
          <h1 className="mt-5 max-w-4xl text-5xl font-semibold tracking-[-0.05em] sm:text-7xl">
            Trust should be evidenced, not claimed.
          </h1>
          <p className="mt-7 max-w-3xl text-base leading-8 text-white/55">
            Empire AI is a new company. We do not manufacture customer counts,
            testimonials, ratings or revenue claims to look older than we are.
            This page records what can be verified now and what is still being built.
          </p>
        </section>

        <section className="mt-20">
          <p className="text-[10px] font-black tracking-[0.2em] text-[#7CFF00]">
            VERIFIED NOW
          </p>
          <EvidenceList items={verified} />
        </section>

        <section className="mt-20">
          <p className="text-[10px] font-black tracking-[0.2em] text-[#00E5FF]">
            CURRENT HARDENING WORK
          </p>
          <EvidenceList items={building} />
        </section>

        <section className="mt-20 rounded-3xl border border-white/10 bg-white/[0.025] p-7 sm:p-10">
          <h2 className="text-2xl font-semibold tracking-[-0.03em]">
            Our evidence rules
          </h2>
          <ul className="mt-6 space-y-3 text-sm leading-6 text-white/55">
            <li>Unknown stays unknown.</li>
            <li>Forecast is never presented as actual revenue.</li>
            <li>Signed terms do not equal payment.</li>
            <li>Payment does not equal a successful customer outcome.</li>
            <li>Case studies and reviews must come from genuine observed outcomes.</li>
            <li>Opt-outs and complaints are part of the trust record, not hidden from it.</li>
          </ul>
        </section>

        <section className="mt-20 border-t border-white/10 pt-10">
          <h2 className="text-2xl font-semibold">Questions about trust or security?</h2>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-white/50">
            Enterprise buyers and partners can ask for the relevant evidence
            behind a claim rather than relying on a badge or marketing score.
          </p>
          <a
            href="mailto:founder@empire-ai.co.uk"
            className="mt-6 inline-flex rounded-full border border-[#00E5FF]/25 px-5 py-3 text-xs font-bold text-[#B8F8FF]"
          >
            Contact Empire
          </a>
        </section>
      </div>
    </main>
  );
}
