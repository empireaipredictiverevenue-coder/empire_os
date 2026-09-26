import Link from "next/link";
import { connection } from "next/server";
import {
  type ApiResult,
  type CollectionEnvelope,
  getTechnicalData,
} from "@/lib/search-api";

function TechnicalPanel({
  title,
  description,
  result,
}: {
  title: string;
  description: string;
  result: ApiResult<CollectionEnvelope>;
}) {
  return (
    <section className="panel">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="eyebrow">Technical evidence</p>
          <h2 className="mt-1 text-lg font-semibold text-white">{title}</h2>
          <p className="mt-2 max-w-xl text-sm text-slate-500">{description}</p>
        </div>
        <span
          className={[
            "rounded-full border px-3 py-1 text-xs font-semibold",
            result.ok
              ? "border-emerald-400/30 bg-emerald-400/10 text-emerald-200"
              : "border-amber-400/30 bg-amber-400/10 text-amber-200",
          ].join(" ")}
        >
          {result.ok ? "LIVE READ" : "GATED"}
        </span>
      </div>

      {!result.ok ? (
        <div className="mt-7 rounded-2xl border border-dashed border-white/10 bg-black/20 p-5">
          <p className="text-sm text-slate-300">
            {result.reason === "canonical_search_repository_not_activated"
              ? "Canonical repository activation is still gated."
              : result.reason ?? "Evidence unavailable."}
          </p>
        </div>
      ) : result.data?.items.length ? (
        <div className="mt-6 overflow-x-auto">
          <table className="w-full min-w-[620px] text-left text-sm">
            <thead className="border-b border-white/10 text-xs uppercase tracking-wider text-slate-600">
              <tr>
                <th className="pb-3 pr-4 font-medium">Record</th>
                <th className="pb-3 pr-4 font-medium">State / signal</th>
                <th className="pb-3 font-medium">Evidence</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/8">
              {result.data.items.map((item, index) => (
                <tr key={title + "-" + index}>
                  <td className="max-w-[320px] py-4 pr-4 text-slate-200">
                    <p className="truncate">
                      {String(item.url ?? item.query ?? item.page_id ?? "Record " + (index + 1))}
                    </p>
                  </td>
                  <td className="py-4 pr-4 text-slate-400">
                    {String(item.state ?? item.refresh_required ?? item.page_count ?? "observed")}
                  </td>
                  <td className="py-4 font-mono text-xs text-slate-500">
                    {String(item.source ?? item.target_query ?? item.topic ?? "canonical")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="mt-8 text-sm text-slate-500">No matching canonical records observed.</p>
      )}
    </section>
  );
}

export default async function TechnicalPage() {
  await connection();
  const data = await getTechnicalData();
  const observe =
    data.health.data?.execution_mode === "OBSERVE" ||
    data.health.data?.execution_mode === "observe";

  return (
    <main className="min-h-screen bg-[#07100d] text-slate-100">
      <div className="grid-noise" />
      <div className="mx-auto max-w-[1500px] px-5 py-6 lg:px-10 lg:py-9">
        <header className="border-b border-white/10 pb-7">
          <div className="flex flex-col justify-between gap-5 md:flex-row md:items-end">
            <div>
              <Link
                href="/"
                className="text-xs font-semibold uppercase tracking-[0.16em] text-emerald-300 hover:text-emerald-200"
              >
                ← Search Command Centre
              </Link>
              <p className="eyebrow mt-6">Phase 5 · Technical search intelligence</p>
              <h1 className="mt-2 text-4xl font-semibold tracking-[-0.04em] text-white md:text-5xl">
                Indexation & content health
              </h1>
              <p className="mt-4 max-w-2xl text-sm leading-6 text-slate-400">
                Read-only operational evidence for indexation, refresh decay and query cannibalisation. No automatic SEO mutation is available from this surface.
              </p>
            </div>
            <span
              className={[
                "w-fit rounded-full border px-3 py-1 text-xs font-semibold",
                observe
                  ? "border-emerald-400/30 bg-emerald-400/10 text-emerald-200"
                  : "border-amber-400/30 bg-amber-400/10 text-amber-200",
              ].join(" ")}
            >
              {observe ? "OBSERVE" : "MODE UNKNOWN"}
            </span>
          </div>
        </header>

        <div className="mt-7 grid gap-4">
          <TechnicalPanel
            title="Indexation evidence"
            description="Observed lifecycle states and their evidence source, ordered from the canonical repository."
            result={data.indexation}
          />
          <TechnicalPanel
            title="Content decay queue"
            description="Pages already marked refresh-required by governed Search Intelligence evidence."
            result={data.decay}
          />
          <TechnicalPanel
            title="Cannibalisation signals"
            description="Queries currently mapped to more than one canonical page. Review-only; no redirect or canonical changes are executed."
            result={data.cannibalisation}
          />
        </div>
      </div>
    </main>
  );
}
