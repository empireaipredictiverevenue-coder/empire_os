import Link from "next/link";
import { connection } from "next/server";
import { getAuthorityData } from "@/lib/search-api";

function text(value: unknown, fallback = "Unknown") {
  return value == null || value === "" ? fallback : String(value);
}

function domain(value: unknown) {
  if (typeof value !== "string" || !value.trim()) return "Unknown";
  try {
    return new URL(value).hostname.replace(/^www\./, "");
  } catch {
    return "Unknown";
  }
}

function Metric({ label, value, detail }: {
  label: string;
  value: string;
  detail: string;
}) {
  return (
    <div className="metric-card">
      <p className="eyebrow">{label}</p>
      <p className="mt-4 text-3xl font-semibold text-white">{value}</p>
      <p className="mt-2 text-xs text-slate-500">{detail}</p>
    </div>
  );
}

export default async function AuthorityPage() {
  await connection();
  const data = await getAuthorityData();
  const backlinks = data.backlinks.data?.items ?? [];
  const citations = data.aiVisibility.data?.items ?? [];
  const gated = !data.backlinks.ok && !data.aiVisibility.ok;

  const referringDomains = new Set(
    backlinks
      .map((row) => domain(row.source_url))
      .filter((value) => value !== "Unknown"),
  );
  const engines = new Set(
    citations
      .map((row) => text(row.engine, ""))
      .filter(Boolean),
  );

  return (
    <main className="min-h-screen bg-[#07100d] text-slate-100">
      <div className="grid-noise" />
      <div className="mx-auto max-w-[1500px] px-5 py-6 lg:px-10 lg:py-9">
        <header className="border-b border-white/10 pb-7">
          <Link
            href="/"
            className="text-xs font-semibold uppercase tracking-[0.16em] text-emerald-300 hover:text-emerald-200"
          >
            ← Search Command Centre
          </Link>
          <p className="eyebrow mt-6">Phase 5 · Authority evidence</p>
          <h1 className="mt-2 text-4xl font-semibold tracking-[-0.04em] text-white md:text-5xl">
            Authority & citations
          </h1>
          <p className="mt-4 max-w-3xl text-sm leading-6 text-slate-400">
            Observed backlink and AI-citation evidence only. No synthetic
            authority score, inferred mention, or fabricated visibility metric
            is shown.
          </p>
        </header>

        {gated ? (
          <section className="panel mt-7">
            <p className="eyebrow">Canonical evidence</p>
            <h2 className="mt-1 text-lg font-semibold text-white">
              Authority evidence gated
            </h2>
            <p className="mt-4 text-sm text-slate-400">
              The evidence views are ready, but the canonical Search reader is
              not activated in production yet.
            </p>
          </section>
        ) : (
          <>
            <section className="mt-7 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <Metric
                label="Observed backlinks"
                value={data.backlinks.ok ? String(backlinks.length) : "—"}
                detail="Canonical backlink observations"
              />
              <Metric
                label="Referring domains"
                value={data.backlinks.ok ? String(referringDomains.size) : "—"}
                detail="Unique observed source domains"
              />
              <Metric
                label="AI citations"
                value={data.aiVisibility.ok ? String(citations.length) : "—"}
                detail="Observed cited URLs only"
              />
              <Metric
                label="Citing engines"
                value={data.aiVisibility.ok ? String(engines.size) : "—"}
                detail="Observed engine identities"
              />
            </section>

            <section className="mt-4 grid gap-4 xl:grid-cols-2">
              <div className="panel">
                <p className="eyebrow">Authority graph</p>
                <h2 className="mt-1 text-lg font-semibold text-white">
                  Observed backlinks
                </h2>
                {!data.backlinks.ok ? (
                  <p className="mt-5 text-sm text-slate-500">
                    {data.backlinks.reason ?? "Backlink evidence unavailable."}
                  </p>
                ) : backlinks.length ? (
                  <div className="mt-5 overflow-x-auto">
                    <table className="w-full min-w-[720px] text-left text-sm">
                      <thead className="border-b border-white/10 text-xs uppercase tracking-wider text-slate-600">
                        <tr>
                          <th className="pb-3 pr-4 font-medium">Referrer</th>
                          <th className="pb-3 pr-4 font-medium">Target</th>
                          <th className="pb-3 pr-4 font-medium">Anchor / rel</th>
                          <th className="pb-3 font-medium">Observed</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-white/8">
                        {backlinks.slice(0, 50).map((row, index) => (
                          <tr key={String(row.id ?? index)}>
                            <td className="max-w-[240px] py-4 pr-4">
                              <p className="font-medium text-slate-200">
                                {domain(row.source_url)}
                              </p>
                              <p className="truncate text-xs text-slate-600">
                                {text(row.source_url)}
                              </p>
                            </td>
                            <td className="max-w-[240px] py-4 pr-4 text-slate-400">
                              <p className="truncate">{text(row.target_url)}</p>
                            </td>
                            <td className="py-4 pr-4 text-slate-500">
                              <p>{text(row.anchor_text)}</p>
                              <p className="mt-1 font-mono text-[10px]">
                                {text(row.rel, "rel not observed")}
                              </p>
                            </td>
                            <td className="py-4 font-mono text-xs text-slate-500">
                              {text(row.observed_at, "Timestamp unknown")}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="mt-5 text-sm text-slate-500">
                    No observed canonical backlink evidence is stored yet.
                  </p>
                )}
              </div>

              <div className="panel">
                <p className="eyebrow">AEO / GEO evidence</p>
                <h2 className="mt-1 text-lg font-semibold text-white">
                  Observed AI citations
                </h2>
                {!data.aiVisibility.ok ? (
                  <p className="mt-5 text-sm text-slate-500">
                    {data.aiVisibility.reason ?? "AI-citation evidence unavailable."}
                  </p>
                ) : citations.length ? (
                  <div className="mt-5 overflow-x-auto">
                    <table className="w-full min-w-[720px] text-left text-sm">
                      <thead className="border-b border-white/10 text-xs uppercase tracking-wider text-slate-600">
                        <tr>
                          <th className="pb-3 pr-4 font-medium">Query</th>
                          <th className="pb-3 pr-4 font-medium">Engine</th>
                          <th className="pb-3 pr-4 font-medium">Cited URL</th>
                          <th className="pb-3 font-medium">Position</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-white/8">
                        {citations.slice(0, 50).map((row, index) => (
                          <tr key={String(row.id ?? index)}>
                            <td className="max-w-[220px] py-4 pr-4 text-slate-200">
                              <p className="truncate">{text(row.query)}</p>
                            </td>
                            <td className="py-4 pr-4 text-slate-400">
                              {text(row.engine)}
                            </td>
                            <td className="max-w-[280px] py-4 pr-4 text-slate-500">
                              <p className="truncate">{text(row.cited_url)}</p>
                              <p className="mt-1 font-mono text-[10px] text-slate-600">
                                {text(row.observed_at, "Timestamp unknown")}
                              </p>
                            </td>
                            <td className="py-4 font-mono text-xs text-slate-500">
                              {text(row.citation_position)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="mt-5 text-sm text-slate-500">
                    No observed canonical AI-citation evidence is stored yet.
                  </p>
                )}
              </div>
            </section>

            <section className="panel mt-4">
              <p className="eyebrow">Evidence boundary</p>
              <p className="mt-2 text-sm leading-6 text-slate-400">
                Counts on this page are observed records, not market-size,
                authority, ranking, or AI-visibility estimates. Competitor
                citation-gap analysis remains evidence-bound in the governed
                Search API and requires explicit competitor domains.
              </p>
            </section>
          </>
        )}
      </div>
    </main>
  );
}
