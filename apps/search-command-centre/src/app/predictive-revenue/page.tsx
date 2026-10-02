import Link from "next/link";
import { connection } from "next/server";
import { getPredictiveRevenueDemo } from "@/lib/founder-api";

const fmt = (v: unknown) => typeof v === "number" ? new Intl.NumberFormat("en-GB").format(v) : "Unknown";
const money = (v: unknown) => typeof v === "number" ? new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(v / 100) : "Unknown";

function Card({ label, value, note }: { label: string; value: string; note: string }) {
  return <div className="metric-card"><p className="text-xs uppercase tracking-[0.14em] text-slate-500">{label}</p><p className="mt-4 text-3xl font-semibold text-white">{value}</p><p className="mt-2 text-xs text-slate-500">{note}</p></div>;
}

export default async function PredictiveRevenuePage() {
  await connection();
  const result = await getPredictiveRevenueDemo();
  const data = result.data;
  const revenue = data?.revenue_operating_system;
  const cloud = data?.predictive_cloud;
  const engine = data?.predictive_engine;
  const buyers = data?.buyer_market;
  const enterprise = data?.enterprise_predictive_revenue;
  const truth = data?.revenue_truth;
  const inventory = revenue?.inventory_counts ?? {};

  return <main className="min-h-screen bg-[#07100d] text-slate-100"><div className="grid-noise" /><div className="mx-auto max-w-[1600px] px-5 py-6 lg:px-10 lg:py-9">
    <header className="border-b border-white/10 pb-7"><div className="flex flex-col justify-between gap-6 xl:flex-row xl:items-end"><div>
      <div className="flex flex-wrap gap-5"><Link href="/founder" className="text-xs font-semibold uppercase tracking-[0.16em] text-emerald-300 hover:text-emerald-200">← Founder Console</Link><Link href="/" className="text-xs font-semibold uppercase tracking-[0.16em] text-cyan-300 hover:text-cyan-200">Search Command Centre</Link></div>
      <p className="eyebrow mt-6">Empire AI · Living proof</p><h1 className="mt-2 text-4xl font-semibold tracking-[-0.04em] text-white md:text-6xl">Predictive Revenue</h1>
      <p className="mt-4 max-w-4xl text-sm leading-6 text-slate-400 md:text-base">Real acquisition → intelligence → opportunity → buyer → commercial truth → verified outcomes. Modelled value never becomes recognized revenue without evidence.</p>
    </div><div className="rounded-2xl border border-emerald-400/25 bg-emerald-400/[0.07] p-5 xl:text-right"><p className="text-xs uppercase tracking-[0.14em] text-slate-500">Recognized revenue truth</p><p className="mt-1 text-4xl font-semibold text-white">{money(truth?.recognized_revenue_cents)}</p><p className="mt-2 text-xs text-slate-500">Forecast/modelled value excluded</p></div></div></header>

    {!result.ok || !data ? <section className="panel mt-7"><p className="eyebrow">Live read model</p><h2 className="mt-1 text-xl font-semibold text-white">Predictive Revenue unavailable</h2><p className="mt-4 text-sm text-slate-400">{result.reason ?? "Live evidence unavailable."}</p></section> : <>
      <section className="mt-7 grid gap-4 sm:grid-cols-2 xl:grid-cols-6">
        <Card label="Predictive Cloud" value={fmt(cloud?.available_component_count) + "/" + fmt(cloud?.component_count)} note="Live components" />
        <Card label="Pre-qualified" value={fmt(inventory.PREQUALIFIED_LEAD)} note="Sellable PPL inventory" />
        <Card label="Buyer seats" value={fmt(buyers?.buyer_seat_count)} note="Observed market capacity" />
        <Card label="Priority targets" value={fmt(buyers?.priority_target_count)} note="Buyer queue" />
        <Card label="Enterprise pool" value={fmt(enterprise?.enterprise_candidate_count)} note="Strategic candidates" />
        <Card label="Private deployment" value={enterprise?.private_deployment?.display_price ?? "$250,000+"} note="Modelled starting floor" />
      </section>

      <section className="panel mt-5"><p className="eyebrow">Living proof chain</p><h2 className="mt-1 text-2xl font-semibold text-white">The software running the business</h2><div className="mt-5 grid gap-3 md:grid-cols-3 xl:grid-cols-6">
        {(data.proof_chain ?? []).map((row, i) => <div key={(row.stage ?? "stage") + "-" + i} className={["rounded-2xl border p-4", row.observed ? "border-emerald-400/30 bg-emerald-400/[0.07]" : "border-amber-400/20 bg-amber-400/[0.04]"].join(" ")}><p className="text-[10px] uppercase tracking-[0.14em] text-slate-500">{row.stage}</p><p className="mt-2 text-2xl font-semibold text-white">{typeof row.value === "number" ? fmt(row.value) : money(row.value_cents)}</p><p className="mt-2 text-xs text-slate-400">{row.label}</p></div>)}
      </div></section>

      <div className="mt-5 grid gap-5 xl:grid-cols-[1.2fr_.8fr]"><section className="panel"><p className="eyebrow">Canonical predictive engine</p><h2 className="mt-1 text-2xl font-semibold text-white">Predictive Revenue equation</h2><div className="mt-5 overflow-x-auto rounded-2xl border border-cyan-400/20 bg-cyan-400/[0.04] p-5 font-mono text-lg font-semibold text-cyan-100">{engine?.canonical_formula ?? "UNKNOWN"}</div><div className="mt-4 grid gap-3 sm:grid-cols-3"><Card label="Prediction state" value={engine?.prediction_state ?? "Unknown"} note="Evidence-gated" /><Card label="Quant ready" value={fmt(engine?.decision_packets_ready)} note="Decision packets" /><Card label="Quant blocked" value={fmt(engine?.decision_packets_blocked)} note="Missing evidence" /></div><p className="mt-4 text-xs text-slate-500">Missing inputs: {Object.entries(engine?.missing_inputs ?? {}).map(([k,v]) => k + " " + v).join(" · ") || "none"}</p></section>
      <section className="panel"><p className="eyebrow">Current commercial constraint</p><h2 className="mt-1 text-2xl font-semibold text-white">Buyer activation</h2><div className="mt-5 grid grid-cols-2 gap-3"><Card label="Buyer pools" value={fmt(buyers?.buyer_pool_count)} note="Demand segments" /><Card label="Exchange ready" value={fmt(buyers?.exchange_inventory_ready_count)} note="Supply" /><Card label="Verified terms" value={fmt(buyers?.terms_verified)} note="Current blocker" /><Card label="Activated buyers" value={fmt(buyers?.commercially_activated_buyers)} note="Commercially ready" /></div><p className="mt-4 rounded-xl border border-amber-400/20 bg-amber-400/[0.05] p-4 text-sm text-amber-100">Blocker: {(buyers?.highest_priority_blocker ?? "UNKNOWN").replaceAll("_", " ")}</p></section></div>

      <section className="panel mt-5"><p className="eyebrow">Predictive Cloud runtime</p><h2 className="mt-1 text-2xl font-semibold text-white">Live component matrix</h2><div className="mt-5 flex flex-wrap gap-2">{(cloud?.component_matrix ?? []).map((c,i) => <span key={(c.component ?? "component") + "-" + i} className={["rounded-xl border px-3 py-2 text-xs", c.available ? "border-emerald-400/25 bg-emerald-400/[0.07] text-emerald-100" : "border-rose-400/25 bg-rose-400/[0.06] text-rose-100"].join(" ")}>{c.component}<span className="ml-2 text-[10px] text-slate-500">{c.freshness ?? "unknown"}</span></span>)}</div></section>

      <div className="mt-5 grid gap-5 xl:grid-cols-2"><section className="panel"><p className="eyebrow">Enterprise Predictive Revenue</p><h2 className="mt-1 text-2xl font-semibold text-white">High-value strategic lane</h2><p className="mt-3 text-sm text-slate-400">{enterprise?.private_deployment?.display_price ?? "$250,000+"} starting floor is modelled economics, not revenue.</p><div className="mt-5 divide-y divide-white/8">{(enterprise?.targets ?? []).slice(0,5).map((t,i) => <div className="py-4" key={(t.account_name ?? "target") + "-" + i}><p className="font-semibold text-white">{t.account_name}</p><p className="mt-1 text-xs text-slate-500">{(t.target_product_codes ?? []).join(" · ") || "research"}</p></div>)}</div></section>
      <section className="panel"><p className="eyebrow">Commercial catalogue</p><h2 className="mt-1 text-2xl font-semibold text-white">Binding-ready products</h2><p className="mt-3 text-sm text-slate-400">{fmt(data.commercial_catalog?.binding_terms_ready_count)} products pass the terms gate.</p><div className="mt-5 divide-y divide-white/8">{(data.commercial_catalog?.active_binding_products ?? []).slice(0,7).map((p,i) => <div className="flex items-center justify-between gap-4 py-4" key={(p.product_code ?? "product") + "-" + i}><div><p className="font-semibold text-white">{p.product_name ?? p.product_code}</p><p className="mt-1 text-xs text-slate-500">{p.product_family}</p></div><p className="text-sm font-semibold text-emerald-200">{p.amount_cents == null ? "Verified terms" : money(p.amount_cents)}</p></div>)}</div></section></div>

      <footer className="mt-6 flex flex-col justify-between gap-3 border-t border-white/10 pt-5 text-xs text-slate-600 md:flex-row"><p>Empire AI Predictive Revenue · live read-only proof · USDT/BSC</p><p>Observed ≠ predicted ≠ recognized revenue · unknown stays unknown</p></footer>
    </>}
  </div></main>;
}
