import Link from "next/link";
import { connection } from "next/server";
import { getEvidenceTimelineData } from "@/lib/search-api";

type TimelineItem = {
  kind: string;
  label: string;
  detail: string;
  observedAt: string | null;
};

function text(value: unknown, fallback = "Unknown") {
  return value == null || value === "" ? fallback : String(value);
}

function timestamp(value: unknown): string | null {
  if (typeof value !== "string" || !value.trim()) return null;
  return value;
}

export default async function EvidencePage() {
  await connection();
  const data = await getEvidenceTimelineData();
  const sources = [
    data.opportunities,
    data.indexation,
    data.alerts,
    data.revenue,
  ];

  const gated = sources.every((source) => !source.ok);
  const timeline: TimelineItem[] = [];

  for (const item of data.opportunities.data?.items ?? []) {
    timeline.push({
      kind: "Opportunity",
      label: text(item.query ?? item.topic, "Observed opportunity"),
      detail: text(item.score_reason, "Canonical opportunity evidence"),
      observedAt: timestamp(item.observed_at),
    });
  }

  for (const item of data.indexation.data?.items ?? []) {
    timeline.push({
      kind: "Indexation",
      label: text(item.url ?? item.page_id, "Page evidence"),
      detail: `${text(item.state, "Unknown state")} · ${text(item.source, "Unknown source")}`,
      observedAt: timestamp(item.observed_at),
    });
  }
  for (const item of data.alerts.data?.items ?? []) {
    timeline.push({
      kind: "Alert",
      label: text(item.alert_type, "Search alert"),
      detail: `${text(item.severity, "Unknown severity")} · ${text(item.evidence, "No evidence text")}`,
      observedAt: timestamp(item.created_at),
    });
  }

  for (const item of data.revenue.data?.items ?? []) {
    timeline.push({
      kind: "Revenue",
      label: text(item.url ?? item.query ?? item.page_id, "Attributed revenue"),
      detail: `${text(item.revenue_cents, "Unknown")} cents · ${text(item.attribution_kind, "Unknown attribution")}`,
      observedAt: timestamp(item.occurred_at ?? item.recorded_at),
    });
  }

  timeline.sort((a, b) => {
    if (!a.observedAt && !b.observedAt) return 0;
    if (!a.observedAt) return 1;
    if (!b.observedAt) return -1;
    return b.observedAt.localeCompare(a.observedAt);
  });

  return (
    <main className="min-h-screen bg-[#07100d] text-slate-100">
      <div className="grid-noise" />
      <div className="mx-auto max-w-[1200px] px-5 py-6 lg:px-10 lg:py-9">
        <header className="border-b border-white/10 pb-7">
          <Link href="/" className="text-xs font-semibold uppercase tracking-[0.16em] text-emerald-300 hover:text-emerald-200">
            ← Search Command Centre
          </Link>
          <p className="eyebrow mt-6">Phase 5 · Evidence chronology</p>
          <h1 className="mt-2 text-4xl font-semibold tracking-[-0.04em] text-white md:text-5xl">
            Evidence timeline
          </h1>
          <p className="mt-4 max-w-3xl text-sm leading-6 text-slate-400">
            Read-only chronology assembled from canonical opportunity, indexation, alert and revenue evidence. Records with no timestamp remain visible but sort last.
          </p>
        </header>
        {gated ? (
          <section className="panel mt-7">
            <p className="eyebrow">Canonical evidence feeds</p>
            <h2 className="mt-1 text-lg font-semibold text-white">Repository gated</h2>
            <p className="mt-4 text-sm text-slate-400">
              Evidence chronology is ready, but the canonical Search reader is not activated in production yet.
            </p>
          </section>
        ) : timeline.length ? (
          <div className="mt-7 grid gap-3">
            {timeline.map((item, index) => (
              <section className="panel" key={`${item.kind}-${item.observedAt ?? "unknown"}-${index}`}>
                <div className="flex flex-col justify-between gap-4 md:flex-row md:items-start">
                  <div>
                    <p className="eyebrow">{item.kind}</p>
                    <h2 className="mt-1 text-lg font-semibold text-white">{item.label}</h2>
                    <p className="mt-2 text-sm text-slate-400">{item.detail}</p>
                  </div>
                  <time className="font-mono text-xs text-slate-500">
                    {item.observedAt ?? "Timestamp unknown"}
                  </time>
                </div>
              </section>
            ))}
          </div>
        ) : (
          <section className="panel mt-7">
            <p className="text-sm text-slate-500">No canonical evidence records observed yet.</p>
          </section>
        )}
      </div>
    </main>
  );
}
