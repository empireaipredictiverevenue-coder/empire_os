import Link from "next/link";
import { connection } from "next/server";
import { getInternalLinkData } from "@/lib/search-api";

function label(value: unknown, fallback: string) {
  return value == null || value === "" ? fallback : String(value);
}

export default async function InternalLinksPage() {
  await connection();
  const data = await getInternalLinkData();
  const pages = data.pages.data?.items ?? [];
  const links = data.links.data?.items ?? [];
  const pageByUrl = new Map(
    pages.map((page) => [
      String(page.canonical_url ?? page.url ?? ""),
      page,
    ]),
  );

  const gated = !data.links.ok;
  const unknownTargets = links.filter(
    (edge) => !pageByUrl.has(String(edge.target_url ?? "")),
  ).length;

  return (
    <main className="min-h-screen bg-[#07100d] text-slate-100">
      <div className="grid-noise" />
      <div className="mx-auto max-w-[1500px] px-5 py-6 lg:px-10 lg:py-9">
        <header className="border-b border-white/10 pb-7">
          <Link href="/" className="text-xs font-semibold uppercase tracking-[0.16em] text-emerald-300 hover:text-emerald-200">
            ← Search Command Centre
          </Link>
          <p className="eyebrow mt-6">Phase 5 · Internal-link intelligence</p>
          <h1 className="mt-2 text-4xl font-semibold tracking-[-0.04em] text-white md:text-5xl">
            Internal-link graph
          </h1>
          <p className="mt-4 max-w-3xl text-sm leading-6 text-slate-400">
            Observed canonical link edges only. No similarity-derived or synthetic connections are drawn.
          </p>
        </header>
        {gated ? (
          <section className="panel mt-7">
            <p className="eyebrow">Canonical link evidence</p>
            <h2 className="mt-1 text-lg font-semibold text-white">Link graph gated</h2>
            <p className="mt-4 text-sm text-slate-400">
              {data.links.reason === "canonical_search_repository_not_activated"
                ? "The graph is ready, but the canonical Search reader is not activated in production yet."
                : data.links.reason ?? "Observed internal-link evidence is unavailable."}
            </p>
          </section>
        ) : links.length ? (
          <>
            <div className="mt-7 grid gap-3 md:grid-cols-3">
              <Metric label="Observed pages" value={String(pages.length)} />
              <Metric label="Observed edges" value={String(links.length)} />
              <Metric label="Unknown targets" value={String(unknownTargets)} />
            </div>

            <section className="panel mt-4">
              <div className="overflow-x-auto">
                <table className="w-full min-w-[800px] text-left text-sm">
                  <thead className="border-b border-white/10 text-xs uppercase tracking-wider text-slate-600">
                    <tr>
                      <th className="pb-3 pr-4 font-medium">Source</th>
                      <th className="pb-3 pr-4 font-medium">Target</th>
                      <th className="pb-3 pr-4 font-medium">Anchor</th>
                      <th className="pb-3 font-medium">Observed</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/8">
                    {links.map((edge, index) => (
                      <tr key={String(edge.id ?? index)}>
                        <td className="max-w-[320px] py-4 pr-4 text-slate-200">
                          <p className="truncate">{label(edge.source_url, "Unknown source")}</p>
                        </td>
                        <td className="max-w-[320px] py-4 pr-4 text-slate-300">
                          <p className="truncate">{label(edge.target_url, "Unknown target")}</p>
                        </td>
                        <td className="py-4 pr-4 text-slate-500">
                          {label(edge.anchor_text, "Unknown")}
                        </td>
                        <td className="py-4 font-mono text-xs text-slate-500">
                          {label(edge.last_observed_at, "Timestamp unknown")}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          </>
        ) : (
          <section className="panel mt-7">
            <p className="text-sm text-slate-500">
              No observed canonical internal-link edges are stored yet.
            </p>
          </section>
        )}
      </div>
    </main>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-white/8 bg-white/[0.025] p-4">
      <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-600">
        {label}
      </p>
      <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
    </div>
  );
}
