import Link from "next/link";
import { connection } from "next/server";
import { readdir, readFile, lstat } from "node:fs/promises";
import path from "node:path";

export const metadata = {
  title: "SEO Operations · Empire AI",
  description: "Original EmpireOS SEO evidence and execution lifecycle.",
};
export const runtime = "nodejs";
const ROOT = "/home/ubuntu/empire_releases/seo_daily_index_status_20261026";
const NAME = /^seo-actions-\d{4}-\d{2}-\d{2}\.json$/;
type Action = {
  id: string; url: string; state_path?: string[]; reason_code: string; priority: string; owner: string;
  state: string; outcome: string; next_action: string; published_claim: boolean;
  technical_test?: { status: string; http_status: number | null; self_canonical: boolean | null };
};
type SEOBoard = {
  schema_version: string; observed_at: string; weekly_source_as_of: string;
  original_action_count: number; resolved_existing_owner_actions: number;
  read_only_technical_tests_executed: number; state_counts: Record<string, number>; milestone_reached_counts?: Record<string, number>;
  actions: Action[]; automated_publication_authorized: false; database_writes: false;
};

async function load(): Promise<{ board: SEOBoard | null; reason: string | null }> {
  try {
    const files = (await readdir(ROOT)).filter((x) => NAME.test(x)).sort();
    if (!files.length) return { board: null, reason: "NO_PRIVATE_SEO_LIFECYCLE_RECEIPT" };
    const file = path.join(ROOT, files[files.length - 1]);
    const stat = await lstat(file);
    if (!stat.isFile() || stat.isSymbolicLink() || stat.size > 300000)
      return { board: null, reason: "UNTRUSTED_PRIVATE_SEO_RECEIPT" };
    const board = JSON.parse(await readFile(file, "utf8")) as SEOBoard;
    if (!board || board.schema_version !== "empire.search.seo_action_lifecycle.v1" ||
        board.database_writes !== false || board.automated_publication_authorized !== false ||
        !Array.isArray(board.actions) || board.actions.length > 60 ||
        board.actions.some((a) => typeof a.id !== "string" ||
          typeof a.state !== "string" || typeof a.url !== "string"))
      return { board: null, reason: "UNTRUSTED_SEO_LIFECYCLE_SCHEMA" };
    return { board, reason: null };
  } catch { return { board: null, reason: "PRIVATE_SEO_SOURCE_UNAVAILABLE" }; }
}
function safePage(url: string): string | null {
  try {
    const p = new URL(url);
    return p.protocol === "https:" && p.hostname === "empire-ai.co.uk" &&
      !p.username && !p.password && !p.search && !p.hash ? p.toString() : null;
  } catch { return null; }
}
const stages = ["detected","prioritised","staged","tested","published","verified","measured"];
function tone(state: string) {
  if (state === "verified") return "border-emerald-400/25 bg-emerald-400/10 text-emerald-200";
  if (state === "tested") return "border-cyan-400/25 bg-cyan-400/10 text-cyan-200";
  if (state === "staged") return "border-amber-400/25 bg-amber-400/10 text-amber-200";
  return "border-white/10 bg-white/[0.05] text-slate-300";
}
export default async function SEOOperationsPage() {
  await connection();
  const { board, reason } = await load();
  return <main className="min-h-screen bg-[#060e1e] text-slate-100">
    <div className="mx-auto max-w-[1500px] px-5 py-8 lg:px-10 lg:py-12">
      <Link href="/founder" className="text-xs font-semibold uppercase tracking-widest text-sky-300">← Founder Console</Link>
      <header className="mt-8 flex flex-wrap items-end justify-between gap-5 border-b border-white/10 pb-7">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-sky-300">EmpireOS · Original SEO department</p>
          <h1 className="mt-3 text-3xl font-semibold tracking-tight md:text-5xl">SEO Operations</h1>
          <p className="mt-4 max-w-3xl text-sm leading-7 text-slate-400">Eyes observe Google and the site.
          The brain prioritises evidence. The hands run bounded checks.
          Only the original website owner authorises publication. Revenue needs independent proof.</p>
        </div>
        <span className="rounded-full border border-sky-400/25 bg-sky-400/10 px-4 py-2 text-xs font-semibold text-sky-200">Daily original owner · Read-only execution</span>
      </header>
      {!board ? <section className="mt-8 rounded-xl border border-amber-400/20 p-6">
        <h2 className="font-semibold">Private SEO evidence unavailable</h2>
        <p className="mt-2 text-sm text-slate-400">No trusted lifecycle receipt. No state is inferred.</p>
        <p className="mt-3 font-mono text-xs text-amber-200">{reason}</p>
      </section> : <>
        <div className="mt-7 grid grid-cols-2 gap-3 md:grid-cols-4">
          {([["Original actions",board.original_action_count],["Live tests",board.read_only_technical_tests_executed],
             ["Verified / resolved",board.resolved_existing_owner_actions],["Measured revenue","Not verified"]] as const).map(([label,val])=>
            <div key={label} className="rounded-xl border border-white/10 bg-white/[0.025] p-5">
              <p className="text-xs uppercase tracking-wider text-slate-400">{label}</p>
              <p className="mt-3 text-2xl font-semibold tabular-nums">{val}</p>
            </div>)}
        </div>
        <section className="mt-7 rounded-xl border border-white/10 bg-white/[0.025] p-5">
          <h2 className="font-semibold">Lifecycle milestones reached · detected → prioritised → staged → tested → published → verified → measured</h2>
          <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-7">
            {stages.map(s=><div key={s} className={"rounded-xl border p-3 "+tone(s)}>
              <p className="text-lg font-semibold tabular-nums">{board.milestone_reached_counts?.[s] ?? board.actions.filter(a => a.state_path?.includes(s)).length}</p>
              <p className="mt-1 text-[11px] font-semibold uppercase tracking-wider">{s}</p>
            </div>)}
          </div>
          <p className="mt-4 text-xs text-slate-500">Source week {board.weekly_source_as_of} ·
           Observed {board.observed_at} · Automatic public publishing OFF.</p>
        </section>
        <section className="mt-7 overflow-hidden rounded-xl border border-white/10 bg-[#091426]">
          <div className="border-b border-white/10 p-5">
            <h2 className="text-xl font-semibold">Owner-assigned SEO jobs</h2>
            <p className="mt-1 text-sm text-slate-400">Actual source, next action and evidence state. Verified forms are not paid conversions.</p>
          </div>
          <div className="divide-y divide-white/10">
          {board.actions.slice(0,40).map(a=>{
            const u=safePage(a.url);
            return <article key={a.id} className="flex flex-wrap items-start justify-between gap-4 px-5 py-4">
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap gap-2">
                  <span className={"rounded-md border px-2 py-1 text-[11px] font-semibold uppercase "+tone(a.state)}>{a.state}</span>
                  <span className="rounded-md border border-white/10 px-2 py-1 text-[11px] text-slate-300">{a.priority}</span>
                  <span className="text-[11px] text-slate-500">{a.reason_code.replaceAll("_"," ")}</span>
                </div>
                <p className="mt-3 break-all text-sm font-medium">{u ? new URL(u).pathname : "Untrusted page URL"}</p>
                <p className="mt-2 text-xs text-slate-400">Owner: {a.owner.replaceAll("_"," ")}</p>
                <p className="mt-1 text-xs text-slate-500">{(a.state==="verified" ? a.outcome : a.next_action).replaceAll("_"," ")}</p>
                {a.technical_test && <p className="mt-2 text-xs text-cyan-200">GET {a.technical_test.http_status ?? "unavailable"} · Canonical {a.technical_test.self_canonical === true ? "matched" : "unverified"}</p>}
              </div>
              {u && <a href={u} target="_blank" rel="noopener noreferrer" className="rounded-lg border border-sky-400/25 px-3 py-2 text-xs font-semibold text-sky-200">Inspect page ↗</a>}
            </article>;
          })}
          </div>
        </section>
        <p className="mt-6 text-xs leading-6 text-slate-500">Read-only control board. No automatic content publication,
        customer outreach, payment, terms acceptance or Google indexing request. Existing verified release evidence
        does not authorise a new release.</p>
      </>}
    </div>
  </main>;
}
